"""Command registry - extensible admin command system with decorators.

Instead of a giant if/elif chain, commands are self-registering via decorators.
New commands can be added by defining a function and decorating it.

Usage:
    registry = CommandRegistry()

    @registry.command("帮助", description="Show help", admin_only=False)
    def help_cmd(ctx: CommandContext) -> str:
        return registry.format_help()

    @registry.command("群列表", description="List groups")
    def list_groups(ctx: CommandContext) -> str:
        ...
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from bot.config.settings import BotSettings

logger = logging.getLogger("WeChatBot.Commands")


@dataclass
class CommandContext:
    """Context passed to command handlers.

    Contains all the information a command handler needs:
    - Who sent the command
    - The raw command text
    - Parsed arguments
    - Access to bot services
    """

    sender_wxid: str
    sender_name: str = ""
    raw_content: str = ""
    command_name: str = ""
    args: str = ""  # Everything after the command name
    is_admin: bool = False
    services: Dict[str, Any] = field(default_factory=dict)  # DI container


@dataclass
class Command:
    """Registered command metadata."""

    name: str
    handler: Callable[[CommandContext], str]
    description: str = ""
    admin_only: bool = True
    aliases: List[str] = field(default_factory=list)
    usage: str = ""


class CommandRegistry:
    """Self-registering command system.

    Commands register themselves via the @command decorator.
    The registry resolves commands by name or alias.
    """

    def __init__(self, prefix: str = "#"):
        self._prefix = prefix
        self._commands: Dict[str, Command] = {}
        self._aliases: Dict[str, str] = {}  # alias -> command name

    def command(
        self,
        name: str,
        description: str = "",
        admin_only: bool = True,
        aliases: Optional[List[str]] = None,
        usage: str = "",
    ) -> Callable:
        """Decorator to register a command handler.

        Args:
            name: Command name (without prefix).
            description: Help text description.
            admin_only: Whether the command requires admin.
            aliases: Alternative command names.
            usage: Usage string (e.g., "<群ID>").
        """

        def decorator(func: Callable[[CommandContext], str]) -> Callable[[CommandContext], str]:
            cmd = Command(
                name=name,
                handler=func,
                description=description,
                admin_only=admin_only,
                aliases=aliases or [],
                usage=usage,
            )
            self._commands[name] = cmd
            for alias in cmd.aliases:
                self._aliases[alias] = name
            logger.debug("Registered command: %s%s", self._prefix, name)
            return func

        return decorator

    def resolve(self, content: str) -> Optional[tuple]:
        """Resolve a message to a command and arguments.

        Args:
            content: Raw message content.

        Returns:
            Tuple of (Command, args_str) or None if not a command.
        """
        stripped = content.strip()
        if not stripped.startswith(self._prefix):
            return None

        # Remove prefix
        cmd_text = stripped[len(self._prefix):].strip()
        if not cmd_text:
            return None

        # Parse command name and arguments
        parts = cmd_text.split(maxsplit=1)
        cmd_name = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        # Look up command
        cmd = self._commands.get(cmd_name)
        if not cmd:
            # Check aliases
            resolved_name = self._aliases.get(cmd_name)
            if resolved_name:
                cmd = self._commands.get(resolved_name)

        if cmd:
            return (cmd, args)
        return None

    def execute(self, content: str, ctx: CommandContext) -> Optional[str]:
        """Parse and execute a command from message content.

        Args:
            content: Raw message content.
            ctx: Command execution context.

        Returns:
            Response string, or None if not a command.
        """
        result = self.resolve(content)
        if not result:
            return None

        cmd, args = result
        ctx.command_name = cmd.name
        ctx.args = args

        # Check admin permission
        if cmd.admin_only and not ctx.is_admin:
            return "❌ 仅管理员可执行此命令"

        try:
            response = cmd.handler(ctx)
            logger.info("Command %s executed by %s", cmd.name, ctx.sender_wxid)
            return response
        except Exception as e:
            logger.error("Command %s error: %s", cmd.name, e)
            return f"❌ 命令执行出错: {e}"

    def format_help(self) -> str:
        """Generate a formatted help text listing all commands."""
        lines = [f"📖 WeChatBot 命令帮助 (前缀: {self._prefix})", "=" * 40]

        # Group by admin_only
        public_cmds = [c for c in self._commands.values() if not c.admin_only]
        admin_cmds = [c for c in self._commands.values() if c.admin_only]

        if public_cmds:
            lines.append("\n🔑 公开命令:")
            for cmd in sorted(public_cmds, key=lambda c: c.name):
                usage = f" {cmd.usage}" if cmd.usage else ""
                lines.append(f"  {self._prefix}{cmd.name}{usage}  — {cmd.description}")
                if cmd.aliases:
                    lines.append(f"    别名: {', '.join(cmd.aliases)}")

        if admin_cmds:
            lines.append("\n👑 管理员命令:")
            for cmd in sorted(admin_cmds, key=lambda c: c.name):
                usage = f" {cmd.usage}" if cmd.usage else ""
                lines.append(f"  {self._prefix}{cmd.name}{usage}  — {cmd.description}")
                if cmd.aliases:
                    lines.append(f"    别名: {', '.join(cmd.aliases)}")

        return "\n".join(lines)

    @property
    def count(self) -> int:
        """Number of registered commands."""
        return len(self._commands)

    @property
    def command_names(self) -> Set[str]:
        """All registered command names."""
        return set(self._commands.keys())
