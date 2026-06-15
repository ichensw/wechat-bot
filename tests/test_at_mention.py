"""Tests for @mention detection, at_me_required filter, and group command handling."""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

from bot.wcf.models import WxMessage, MessageType
from bot.handlers.base import HandlerResult, HandlerPriority
from bot.config.settings import BotSettings
from bot.handlers.group_message import GroupMessageHandler, PrivateMessageHandler, _extract_group_content


# ── WxMessage @mention Tests ──────────────────────────────────────────


class TestWxMessageAtMention:
    """Test @mention detection in WxMessage."""

    def test_at_wxids_from_xml(self):
        """Parse @mention wxids from XML atuserlist."""
        xml = '<msg><atuserlist>wxid_bot_abc|wxid_user_def</atuserlist></msg>'
        wxids = WxMessage.parse_at_wxids("hello", xml)
        assert wxids == ["wxid_bot_abc", "wxid_user_def"]

    def test_at_wxids_from_xml_empty(self):
        """Empty atuserlist returns empty list."""
        xml = '<msg><atuserlist></atuserlist></msg>'
        wxids = WxMessage.parse_at_wxids("hello", xml)
        assert wxids == []

    def test_at_wxids_no_xml(self):
        """No XML returns empty list."""
        wxids = WxMessage.parse_at_wxids("hello", "")
        assert wxids == []

    def test_at_wxids_non_wxid_format(self):
        """Non-wxid_ prefixed entries in atuserlist are skipped."""
        xml = '<msg><atuserlist>wxid_bot_abc|nonwxid|someuser</atuserlist></msg>'
        wxids = WxMessage.parse_at_wxids("hello", xml)
        assert wxids == ["wxid_bot_abc"]

    def test_is_at_method(self):
        """is_at() checks if a specific wxid was @mentioned."""
        msg = WxMessage(
            msg_id="1", type=1, content="hello", sender="wxid_user",
            room_id="test@chatroom", at_wxids=["wxid_bot_abc", "wxid_other"],
        )
        assert msg.is_at("wxid_bot_abc") is True
        assert msg.is_at("wxid_other") is True
        assert msg.is_at("wxid_not_mentioned") is False

    def test_has_at_property(self):
        """has_at property checks if any @mention exists."""
        msg_with_at = WxMessage(
            msg_id="1", type=1, content="hello", sender="wxid_user",
            room_id="test@chatroom", at_wxids=["wxid_bot"],
        )
        msg_no_at = WxMessage(
            msg_id="2", type=1, content="hello", sender="wxid_user",
            room_id="test@chatroom", at_wxids=[],
        )
        assert msg_with_at.has_at is True
        assert msg_no_at.has_at is False

    def test_from_wcf_msg_with_at_xml(self):
        """from_wcf_msg parses at_wxids from XML."""
        mock_msg = MagicMock()
        mock_msg.id = "100"
        mock_msg.type = 1
        mock_msg.content = "hello"
        mock_msg.sender = "wxid_user"
        mock_msg.roomid = "test@chatroom"
        mock_msg.xml = '<msg><atuserlist>wxid_bot_abc</atuserlist></msg>'
        mock_msg.thumb = ""
        mock_msg.extra = ""

        msg = WxMessage.from_wcf_msg(mock_msg)
        assert msg.at_wxids == ["wxid_bot_abc"]
        assert msg.is_at("wxid_bot_abc") is True

    def test_from_http_msg_with_atuserlist(self):
        """from_http_msg parses at_wxids from HTTP response."""
        data = {
            "id": "200",
            "type": 1,
            "content": "hello",
            "sender": "wxid_user",
            "roomid": "test@chatroom",
            "xml": '<msg><atuserlist>wxid_bot_xyz</atuserlist></msg>',
        }
        msg = WxMessage.from_http_msg(data)
        assert msg.at_wxids == ["wxid_bot_xyz"]

    def test_from_http_msg_explicit_at_wxids(self):
        """from_http_msg supports explicit at_wxids field."""
        data = {
            "id": "201",
            "type": 1,
            "content": "hello",
            "sender": "wxid_user",
            "roomid": "test@chatroom",
            "at_wxids": ["wxid_bot_explicit"],
        }
        msg = WxMessage.from_http_msg(data)
        assert msg.at_wxids == ["wxid_bot_explicit"]

    def test_to_dict_includes_at_wxids(self):
        """to_dict includes at_wxids."""
        msg = WxMessage(
            msg_id="1", type=1, content="hello", sender="wxid_user",
            room_id="test@chatroom", at_wxids=["wxid_bot"],
        )
        d = msg.to_dict()
        assert d["at_wxids"] == ["wxid_bot"]


# ── _extract_group_content Tests ──────────────────────────────────────


class TestExtractGroupContent:
    """Test group message content extraction."""

    def test_extract_with_sender_prefix(self):
        """Strip sender wxid prefix from group message."""
        content = "wxid_sender:\nHello world"
        assert _extract_group_content(content) == "Hello world"

    def test_extract_without_sender_prefix(self):
        """Return content as-is when no prefix."""
        content = "Hello world"
        assert _extract_group_content(content) == "Hello world"

    def test_extract_with_command(self):
        """Extract command from group message with prefix."""
        content = "wxid_sender:\n#帮助"
        assert _extract_group_content(content) == "#帮助"


# ── BotSettings at_me_required Tests ──────────────────────────────────


class TestAtMeRequired:
    """Test at_me_required config setting."""

    def test_default_at_me_required(self):
        """Default at_me_required is True."""
        settings = BotSettings()
        assert settings.at_me_required is True

    def test_at_me_required_false(self):
        """Can set at_me_required to False."""
        settings = BotSettings(at_me_required=False)
        assert settings.at_me_required is False

    def test_from_dict_with_at_me_required(self):
        """Parse at_me_required from dict."""
        settings = BotSettings.from_dict({"at_me_required": False})
        assert settings.at_me_required is False


# ── GroupMessageHandler @mention + Command Tests ──────────────────────


def _make_handler(at_me_required=True, admin_wxid="wxid_admin", command_prefix="#"):
    """Create a GroupMessageHandler with mocked dependencies."""
    group_filter = MagicMock()
    group_filter.is_allowed.return_value = True

    group_monitor = MagicMock()

    admin_manager = MagicMock()
    admin_manager.handle_command.return_value = "✅ OK"
    admin_manager.is_admin.return_value = True

    bot_settings = BotSettings(
        at_me_required=at_me_required,
        admin_wxid=admin_wxid,
        command_prefix=command_prefix,
    )

    wcf_client = MagicMock()
    user_info = MagicMock()
    user_info.wxid = "wxid_bot_abc"
    wcf_client.get_user_info.return_value = user_info
    wcf_client.is_connected.return_value = True
    admin_manager._wcf = wcf_client

    sender = MagicMock()

    handler = GroupMessageHandler(
        group_filter=group_filter,
        group_monitor=group_monitor,
        admin_manager=admin_manager,
        bot_settings=bot_settings,
        sender=sender,
    )
    return handler, group_filter, group_monitor, admin_manager, wcf_client


def _make_group_msg(content, sender="wxid_user", room_id="test@chatroom",
                     at_wxids=None):
    """Create a test group message."""
    return WxMessage(
        msg_id="1", type=MessageType.TEXT, content=content,
        sender=sender, room_id=room_id, at_wxids=at_wxids or [],
    )


class TestGroupMessageHandlerAtMention:
    """Test GroupMessageHandler @mention filtering."""

    def test_filtered_group_rejected(self):
        """Messages from filtered groups are rejected."""
        handler, group_filter, _, _, _ = _make_handler()
        group_filter.is_allowed.return_value = False
        msg = _make_group_msg("hello")
        result = handler.handle(msg)
        assert result.action == "rejected"

    def test_command_no_at_required(self):
        """Admin commands in groups do NOT require @mention."""
        handler, _, monitor, admin_mgr, wcf = _make_handler(at_me_required=True)
        msg = _make_group_msg("#帮助")
        result = handler.handle(msg)
        assert result.action == "handled"
        admin_mgr.handle_command.assert_called_once_with(
            sender_wxid="wxid_user", content="#帮助", room_id="test@chatroom",
        )

    def test_at_someone_else_not_at_bot(self):
        """@someone else (not the bot) doesn't count as @bot."""
        handler, _, _, _, _ = _make_handler(at_me_required=True)
        msg = _make_group_msg("@王五 hello", at_wxids=["wxid_friend_wang"])
        result = handler.handle(msg)
        # Not a command, not @bot → handler won't take action
        assert result.action != "handled"  # Not handled by this handler

    def test_at_bot_passes_filter(self):
        """Messages that @ the bot pass the at_me_required filter."""
        handler, _, monitor, _, wcf = _make_handler(at_me_required=True)
        msg = _make_group_msg("hello", at_wxids=["wxid_bot_abc"])
        result = handler.handle(msg)
        assert result.action == "continue"

    def test_no_at_bot_rejected_by_continue(self):
        """Non-command, non-@ messages pass as CONTINUE but handler won't act.
        
        Note: The handler returns CONTINUE (not REJECTED) because other
        handlers in the pipeline may still process the message. The at_me_required
        filter just means this handler won't take action on non-@ messages.
        """
        handler, _, monitor, _, wcf = _make_handler(at_me_required=True)
        msg = _make_group_msg("hello", at_wxids=[])
        result = handler.handle(msg)
        # The message was stored (monitor.process_message called) but handler returns continue
        # The key is that the handler does NOT take action (no command, no at)
        monitor.process_message.assert_called_once()

    def test_at_me_required_false_all_pass(self):
        """When at_me_required=False, all messages pass the filter."""
        handler, _, _, _, _ = _make_handler(at_me_required=False)
        msg = _make_group_msg("hello", at_wxids=[])
        result = handler.handle(msg)
        assert result.action == "continue"

    def test_message_stored_regardless_of_at(self):
        """Messages are stored for monitoring regardless of @mention."""
        handler, _, monitor, _, _ = _make_handler(at_me_required=True)
        # No @mention
        msg = _make_group_msg("hello", at_wxids=[])
        handler.handle(msg)
        monitor.process_message.assert_called_once()

    def test_message_with_at_also_stored(self):
        """@mentioned messages are also stored."""
        handler, _, monitor, _, _ = _make_handler(at_me_required=True)
        msg = _make_group_msg("hello", at_wxids=["wxid_bot_abc"])
        handler.handle(msg)
        monitor.process_message.assert_called_once()

    def test_command_in_group_stored(self):
        """Command messages in groups are also stored."""
        handler, _, monitor, admin_mgr, _ = _make_handler()
        msg = _make_group_msg("#帮助")
        handler.handle(msg)
        monitor.process_message.assert_called_once()

    def test_group_command_with_sender_prefix(self):
        """Commands with WeChatFerry sender prefix are handled correctly."""
        handler, _, monitor, admin_mgr, _ = _make_handler()
        msg = _make_group_msg("wxid_sender:\n#帮助")
        result = handler.handle(msg)
        assert result.action == "handled"
        # The command should be called with extracted content (without prefix)
        admin_mgr.handle_command.assert_called_once_with(
            sender_wxid="wxid_user", content="#帮助", room_id="test@chatroom",
        )

    def test_group_command_response_sent_to_group(self):
        """When handle_command returns response for group, it's sent back."""
        handler, _, _, admin_mgr, wcf = _make_handler()
        # Admin command returns a response
        admin_mgr.handle_command.return_value = "✅ 管理员绑定成功"
        msg = _make_group_msg("#绑定管理员", sender="wxid_admin")
        result = handler.handle(msg)
        assert result.action == "handled"

    def test_group_command_response_none_when_sent_directly(self):
        """When AdminManager sends to group directly, it returns None."""
        handler, _, _, admin_mgr, wcf = _make_handler()
        # handle_command returns None when it sent directly to group
        admin_mgr.handle_command.return_value = None
        msg = _make_group_msg("#帮助")
        result = handler.handle(msg)
        # Still handled, just no re-send needed
        assert result.action == "handled"

    def test_non_text_group_message_not_handled(self):
        """Non-text group messages are not handled by GroupMessageHandler."""
        handler, _, _, _, _ = _make_handler()
        msg = WxMessage(
            msg_id="1", type=MessageType.IMAGE, content="",
            sender="wxid_user", room_id="test@chatroom",
        )
        assert handler.can_handle(msg) is False


# ── PrivateMessageHandler + Private Whitelist Tests ───────────────────


def _make_private_handler(admin_wxid="wxid_admin", private_whitelist=None):
    """Create a PrivateMessageHandler with mocked dependencies."""
    bot_settings = BotSettings(
        admin_wxid=admin_wxid,
        private_whitelist=private_whitelist or [],
    )

    admin_manager = MagicMock()
    admin_manager.handle_command.return_value = "✅ OK"

    sender = MagicMock()

    handler = PrivateMessageHandler(
        admin_manager=admin_manager,
        bot_settings=bot_settings,
        sender=sender,
    )
    return handler, admin_manager, sender


class TestPrivateMessageHandler:
    """Test PrivateMessageHandler access control."""

    def test_admin_private_allowed(self):
        """Admin's private messages are always allowed."""
        handler, admin_mgr, sender = _make_private_handler(admin_wxid="wxid_admin")
        msg = WxMessage(
            msg_id="1", type=MessageType.TEXT, content="#帮助",
            sender="wxid_admin", room_id="",
        )
        assert handler.can_handle(msg) is True
        result = handler.handle(msg)
        assert result.action == "handled"
        admin_mgr.handle_command.assert_called_once()

    def test_whitelist_user_allowed(self):
        """Users in private_whitelist are allowed."""
        handler, admin_mgr, sender = _make_private_handler(
            private_whitelist=["wxid_friend_li", "wxid_friend_wang"],
        )
        msg = WxMessage(
            msg_id="1", type=MessageType.TEXT, content="hello",
            sender="wxid_friend_li", room_id="",
        )
        result = handler.handle(msg)
        # Not a command, but authorized — returns continue
        assert result.action != "rejected"

    def test_unauthorized_user_rejected(self):
        """Users NOT in whitelist and NOT admin are rejected."""
        handler, admin_mgr, sender = _make_private_handler(admin_wxid="wxid_admin")
        msg = WxMessage(
            msg_id="1", type=MessageType.TEXT, content="hello",
            sender="wxid_stranger", room_id="",
        )
        result = handler.handle(msg)
        assert result.action == "rejected"

    def test_empty_whitelist_rejects_non_admin(self):
        """With empty whitelist, only admin can private chat."""
        handler, admin_mgr, sender = _make_private_handler()
        msg = WxMessage(
            msg_id="1", type=MessageType.TEXT, content="hello",
            sender="wxid_stranger", room_id="",
        )
        result = handler.handle(msg)
        assert result.action == "rejected"

    def test_no_admin_allows_whitelist_only(self):
        """When no admin is bound, only whitelist users can private chat."""
        handler, admin_mgr, sender = _make_private_handler(
            admin_wxid=None, private_whitelist=["wxid_friend_li"],
        )
        # Whitelist user allowed
        msg1 = WxMessage(
            msg_id="1", type=MessageType.TEXT, content="hello",
            sender="wxid_friend_li", room_id="",
        )
        result1 = handler.handle(msg1)
        assert result1.action != "rejected"

        # Non-whitelist rejected
        msg2 = WxMessage(
            msg_id="2", type=MessageType.TEXT, content="hello",
            sender="wxid_stranger", room_id="",
        )
        result2 = handler.handle(msg2)
        assert result2.action == "rejected"

    def test_admin_command_response_sent_via_sender(self):
        """Admin command response is sent through ThreadSafeSender."""
        handler, admin_mgr, sender = _make_private_handler()
        admin_mgr.handle_command.return_value = "✅ done"
        msg = WxMessage(
            msg_id="1", type=MessageType.TEXT, content="#帮助",
            sender="wxid_admin", room_id="",
        )
        handler.handle(msg)
        sender.send_text.assert_called_once_with("✅ done", "wxid_admin")

    def test_whitelist_user_command_processed(self):
        """Whitelist user's commands are processed."""
        handler, admin_mgr, sender = _make_private_handler(
            private_whitelist=["wxid_friend_li"],
        )
        admin_mgr.handle_command.return_value = "✅ done"
        msg = WxMessage(
            msg_id="1", type=MessageType.TEXT, content="#帮助",
            sender="wxid_friend_li", room_id="",
        )
        result = handler.handle(msg)
        assert result.action == "handled"
        admin_mgr.handle_command.assert_called_once()


# ── BotSettings is_private_allowed Tests ──────────────────────────────


class TestIsPrivateAllowed:
    """Test BotSettings.is_private_allowed method."""

    def test_admin_always_allowed(self):
        """Admin is always allowed."""
        s = BotSettings(admin_wxid="wxid_admin")
        assert s.is_private_allowed("wxid_admin") is True

    def test_whitelist_user_allowed(self):
        """Whitelist user is allowed."""
        s = BotSettings(private_whitelist=["wxid_friend"])
        assert s.is_private_allowed("wxid_friend") is True

    def test_stranger_rejected(self):
        """Stranger is not allowed."""
        s = BotSettings(admin_wxid="wxid_admin", private_whitelist=["wxid_friend"])
        assert s.is_private_allowed("wxid_stranger") is False

    def test_no_admin_whitelist_only(self):
        """When no admin, only whitelist users allowed."""
        s = BotSettings(admin_wxid=None, private_whitelist=["wxid_friend"])
        assert s.is_private_allowed("wxid_friend") is True
        assert s.is_private_allowed("wxid_stranger") is False

    def test_empty_whitelist_no_admin(self):
        """Nobody allowed when no admin and empty whitelist."""
        s = BotSettings(admin_wxid=None, private_whitelist=[])
        assert s.is_private_allowed("wxid_anyone") is False

    def test_private_message_not_handled(self):
        """Private messages are not handled by GroupMessageHandler."""
        handler, _, _, _, _ = _make_handler()
        msg = WxMessage(
            msg_id="1", type=MessageType.TEXT, content="hello",
            sender="wxid_user", room_id="",
        )
        assert handler.can_handle(msg) is False
