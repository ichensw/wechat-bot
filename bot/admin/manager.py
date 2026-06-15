"""Admin manager - handles admin binding and command delegation.

The bot supports binding exactly one admin. The admin can issue commands
to manage groups, filters, monitoring, and bot configuration.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, Optional, Tuple

from bot.admin.commands import CommandContext, CommandRegistry
from bot.config.loader import ConfigLoader
from bot.core.event_bus import EventBus, EventTypes
from bot.core.exceptions import AdminAlreadyBoundError, AdminNotBoundError, AdminPermissionDeniedError
from bot.core.sender import ThreadSafeSender
from bot.db.repository import Repository
from bot.group.filter import GroupFilter
from bot.group.monitor import GroupMonitor
from bot.wcf.client import WcfClient

logger = logging.getLogger("WeChatBot.Admin")


class AdminManager:
    """Admin manager with command delegation.

    Responsibilities:
      - Admin binding/unbinding (single admin constraint)
      - Command registration and delegation
      - Permission checking
      - Event publishing for admin actions
    """

    def __init__(
        self,
        config_loader: ConfigLoader,
        db: Repository,
        group_filter: GroupFilter,
        group_monitor: GroupMonitor,
        wcf_client: WcfClient,
        event_bus: EventBus,
        sender: ThreadSafeSender,
    ):
        self._config_loader = config_loader
        self._db = db
        self._group_filter = group_filter
        self._group_monitor = group_monitor
        self._wcf = wcf_client
        self._event_bus = event_bus
        self._sender = sender

        # Initialize command registry
        prefix = self._config_loader.settings.bot.command_prefix
        self._registry = CommandRegistry(prefix=prefix)
        self._register_default_commands()

    @property
    def admin_wxid(self) -> Optional[str]:
        """Get current admin wxid."""
        return self._config_loader.settings.bot.admin_wxid

    @property
    def is_bound(self) -> bool:
        """Check if an admin is currently bound."""
        return self._config_loader.settings.bot.admin_wxid is not None

    def is_admin(self, wxid: str) -> bool:
        """Check if a wxid is the bound admin."""
        return wxid == self.admin_wxid

    def bind_admin(self, wxid: str) -> Tuple[bool, str]:
        """Bind a user as admin. Only one admin is supported.

        Returns:
            Tuple of (success, message).
        """
        if self.is_bound:
            current = self.admin_wxid
            return False, f"管理员已绑定（{current}），请先解绑当前管理员"

        # Update config
        self._config_loader.update_section("bot", "admin_wxid", wxid)

        # Get user name
        contact = self._wcf.get_info_by_wxid(wxid)
        name = contact.name if contact else wxid

        # Publish event
        self._event_bus.publish(
            EventTypes.ADMIN_BOUND,
            data={"wxid": wxid, "name": name},
            source="AdminManager",
        )

        logger.info("Admin bound: %s (%s)", name, wxid)
        return True, f"✅ 管理员绑定成功: {name} ({wxid})"

    def unbind_admin(self, wxid: str) -> Tuple[bool, str]:
        """Unbind the current admin. Only the current admin can unbind.

        Returns:
            Tuple of (success, message).
        """
        if not self.is_admin(wxid):
            return False, "只有当前管理员才能解绑"

        self._config_loader.update_section("bot", "admin_wxid", None)
        self._event_bus.publish(EventTypes.ADMIN_UNBOUND, data={"wxid": wxid}, source="AdminManager")
        logger.info("Admin unbound by %s", wxid)
        return True, "✅ 管理员已解绑"

    def handle_command(self, sender_wxid: str, content: str, room_id: str = "") -> Optional[str]:
        """Handle a potential admin command from a message.

        Args:
            sender_wxid: The wxid of the message sender.
            content: The raw message content.
            room_id: The room_id if this is a group message (empty for private).

        Returns:
            Response string if a command was executed, None if not a command.
            When room_id is provided, the response is sent directly to the group
            (with @mention for non-admin), and None is returned to avoid double-sending.
        """
        # Build context
        sender_name = ""
        contact = self._wcf.get_info_by_wxid(sender_wxid)
        if contact:
            sender_name = contact.name

        ctx = CommandContext(
            sender_wxid=sender_wxid,
            sender_name=sender_name,
            raw_content=content,
            command_name="",
            args="",
            is_admin=self.is_admin(sender_wxid),
            services={
                "admin_manager": self,
                "group_filter": self._group_filter,
                "group_monitor": self._group_monitor,
                "db": self._db,
                "wcf": self._wcf,
                "config_loader": self._config_loader,
            },
        )

        response = self._registry.execute(content, ctx)
        if not response:
            return None

        # For group messages, send response back to the group
        if room_id:
            if self.is_admin(sender_wxid):
                # Admin: send directly to group (thread-safe)
                self._sender.send_text(response, room_id)
            else:
                # Non-admin: @mention the sender (thread-safe)
                at_nickname = sender_name or sender_wxid
                self._sender.send_text(f"@{at_nickname} {response}", room_id, at_list=[sender_wxid])
            return None  # Already sent, don't double-send

        return response

    def _register_default_commands(self) -> None:
        """Register all built-in admin commands."""
        registry = self._registry

        @registry.command("绑定管理员", description="绑定自己为管理员", admin_only=False)
        def cmd_bind(ctx: CommandContext) -> str:
            success, msg = self.bind_admin(ctx.sender_wxid)
            return msg

        @registry.command("解绑管理员", description="解绑当前管理员")
        def cmd_unbind(ctx: CommandContext) -> str:
            success, msg = self.unbind_admin(ctx.sender_wxid)
            return msg

        @registry.command("帮助", description="显示命令帮助", admin_only=False, aliases=["help"])
        def cmd_help(ctx: CommandContext) -> str:
            return registry.format_help()

        @registry.command("状态", description="查看机器人状态", aliases=["status"])
        def cmd_status(ctx: CommandContext) -> str:
            admin = self.admin_wxid or "未绑定"
            filter_status = self._group_filter.get_status()
            total_msgs = self._db.get_message_count()
            total_groups = len(self._db.get_all_groups())
            return (
                f"🤖 WeChatBot 状态\n"
                f"{'=' * 20}\n"
                f"管理员: {admin}\n"
                f"群聊数: {total_groups}\n"
                f"消息总数: {total_msgs}\n"
                f"过滤: {filter_status}"
            )

        @registry.command("群列表", description="查看所有群聊")
        def cmd_list_groups(ctx: CommandContext) -> str:
            return self._group_monitor.get_all_groups_summary()

        @registry.command("监控列表", description="查看监控状态")
        def cmd_filter_status(ctx: CommandContext) -> str:
            return self._group_filter.get_status()

        @registry.command("群概要", description="查看群聊概要", usage="<群ID>")
        def cmd_group_summary(ctx: CommandContext) -> str:
            if not ctx.args:
                return "❌ 用法: #群概要 <群ID>"
            return self._group_monitor.get_group_summary(ctx.args.strip())

        @registry.command("刷新群", description="从微信刷新群信息")
        def cmd_refresh_groups(ctx: CommandContext) -> str:
            groups = self._group_monitor.refresh_groups()
            return f"✅ 已刷新 {len(groups)} 个群聊"

        @registry.command("添加白名单", description="添加群到白名单", usage="<群ID>")
        def cmd_add_whitelist(ctx: CommandContext) -> str:
            if not ctx.args:
                return "❌ 用法: #添加白名单 <群ID>"
            room_id = ctx.args.strip()
            if self._group_filter.add_to_whitelist(room_id):
                return f"✅ 已将 {room_id} 添加到白名单"
            return f"⚠️ {room_id} 已在白名单中或格式无效"

        @registry.command("移除白名单", description="从白名单移除群", usage="<群ID>")
        def cmd_remove_whitelist(ctx: CommandContext) -> str:
            if not ctx.args:
                return "❌ 用法: #移除白名单 <群ID>"
            room_id = ctx.args.strip()
            if self._group_filter.remove_from_whitelist(room_id):
                return f"✅ 已将 {room_id} 从白名单移除"
            return f"⚠️ {room_id} 不在白名单中"

        @registry.command("添加黑名单", description="添加群到黑名单", usage="<群ID>")
        def cmd_add_blacklist(ctx: CommandContext) -> str:
            if not ctx.args:
                return "❌ 用法: #添加黑名单 <群ID>"
            room_id = ctx.args.strip()
            if self._group_filter.add_to_blacklist(room_id):
                return f"✅ 已将 {room_id} 添加到黑名单"
            return f"⚠️ {room_id} 已在黑名单中或格式无效"

        @registry.command("移除黑名单", description="从黑名单移除群", usage="<群ID>")
        def cmd_remove_blacklist(ctx: CommandContext) -> str:
            if not ctx.args:
                return "❌ 用法: #移除黑名单 <群ID>"
            room_id = ctx.args.strip()
            if self._group_filter.remove_from_blacklist(room_id):
                return f"✅ 已将 {room_id} 从黑名单移除"
            return f"⚠️ {room_id} 不在黑名单中"

        @registry.command("过滤模式", description="设置过滤模式", usage="<whitelist/blacklist/all>")
        def cmd_set_filter_mode(ctx: CommandContext) -> str:
            if not ctx.args:
                return "❌ 用法: #过滤模式 <whitelist/blacklist/all>"
            try:
                self._group_filter.mode = ctx.args.strip()
                return f"✅ 过滤模式已设为: {ctx.args.strip()}"
            except Exception as e:
                return f"❌ {e}"

        # ── Private Chat Whitelist Commands ────────────────────────

        @registry.command("添加私聊白名单", description="添加用户到私聊白名单", usage="<wxid>")
        def cmd_add_private_whitelist(ctx: CommandContext) -> str:
            if not ctx.args:
                return "❌ 用法: #添加私聊白名单 <wxid>"
            wxid = ctx.args.strip()
            settings = self._config_loader.settings.bot
            if wxid in settings.private_whitelist:
                return f"⚠️ {wxid} 已在私聊白名单中"
            settings.private_whitelist.append(wxid)
            self._config_loader.save()
            return f"✅ 已将 {wxid} 添加到私聊白名单\n当前白名单: {', '.join(settings.private_whitelist)}"

        @registry.command("移除私聊白名单", description="从私聊白名单移除用户", usage="<wxid>")
        def cmd_remove_private_whitelist(ctx: CommandContext) -> str:
            if not ctx.args:
                return "❌ 用法: #移除私聊白名单 <wxid>"
            wxid = ctx.args.strip()
            settings = self._config_loader.settings.bot
            if wxid not in settings.private_whitelist:
                return f"⚠️ {wxid} 不在私聊白名单中"
            settings.private_whitelist.remove(wxid)
            self._config_loader.save()
            return f"✅ 已将 {wxid} 从私聊白名单移除\n当前白名单: {', '.join(settings.private_whitelist) or '(空)'}"

        @registry.command("私聊白名单", description="查看私聊白名单")
        def cmd_list_private_whitelist(ctx: CommandContext) -> str:
            settings = self._config_loader.settings.bot
            wl = settings.private_whitelist
            admin = settings.admin_wxid or "未绑定"
            lines = [f"📋 私聊白名单", "=" * 20, f"管理员: {admin} (自动允许)"]
            if wl:
                for i, wxid in enumerate(wl, 1):
                    name = ""
                    contact = self._wcf.get_info_by_wxid(wxid)
                    if contact:
                        name = f" ({contact.name})"
                    lines.append(f"  {i}. {wxid}{name}")
            else:
                lines.append("  (无其他白名单用户)")
            return "\n".join(lines)

        logger.info("Registered %d admin commands", registry.count)
