"""Mock WCF client for local development and debugging on macOS/Linux.

This client simulates WeChatFerry behavior without requiring a real WeChat instance.
It supports:
  - Simulated contacts (groups + friends)
  - Interactive message injection via CLI
  - Message queue for testing handlers
  - Auto-generated periodic test messages (optional)

Usage in config.yaml:
  bot:
    wcf_mode: mock

Or via environment variable:
  BOT_WCF_MODE=mock python main.py
"""

from __future__ import annotations

import logging
import random
import threading
import time
from queue import Empty, Queue
from typing import Any, Dict, List, Optional

from bot.wcf.client import WcfClient
from bot.wcf.models import Contact, GroupInfo, UserInfo, WxMessage, MessageType

logger = logging.getLogger("WeChatBot.Wcf.Mock")


# ── Simulated Data ────────────────────────────────────────────────────

MOCK_USER = UserInfo(
    wxid="wxid_mock_bot",
    name="调试机器人",
    mobile="13800138000",
    home="",
)

MOCK_CONTACTS: List[Contact] = [
    # Groups
    Contact(wxid="test_group_a@chatroom", name="测试群A-产品讨论", alias="", type=0, remark=""),
    Contact(wxid="test_group_b@chatroom", name="测试群B-技术交流", alias="", type=0, remark=""),
    Contact(wxid="test_group_c@chatroom", name="测试群C-运营数据", alias="", type=0, remark=""),
    # Friends
    Contact(wxid="wxid_admin_user", name="管理员张三", alias="zhangsan", type=0, remark="管理员"),
    Contact(wxid="wxid_friend_li", name="李四", alias="lisi", type=0, remark=""),
    Contact(wxid="wxid_friend_wang", name="王五", alias="wangwu", type=0, remark=""),
]

MOCK_GROUP_MEMBERS: Dict[str, Dict[str, str]] = {
    "test_group_a@chatroom": {
        "wxid_admin_user": "张三",
        "wxid_friend_li": "李四",
        "wxid_friend_wang": "王五",
        "wxid_mock_member_1": "赵六",
        "wxid_mock_member_2": "孙七",
    },
    "test_group_b@chatroom": {
        "wxid_admin_user": "张三",
        "wxid_friend_li": "李四",
        "wxid_mock_member_3": "周八",
    },
    "test_group_c@chatroom": {
        "wxid_friend_wang": "王五",
        "wxid_mock_member_4": "吴九",
        "wxid_mock_member_5": "郑十",
        "wxid_mock_member_6": "钱十一",
    },
}

# Simulated messages that auto-generate periodically
MOCK_MESSAGE_TEMPLATES = [
    ("test_group_a@chatroom", "wxid_friend_li", "今天的产品需求大家看了吗？"),
    ("test_group_a@chatroom", "wxid_friend_wang", "看了，感觉改动挺大的"),
    ("test_group_b@chatroom", "wxid_friend_li", "这个接口性能有点问题，大家帮忙看看"),
    ("test_group_b@chatroom", "wxid_mock_member_3", "我来排查一下"),
    ("test_group_c@chatroom", "wxid_mock_member_4", "本周数据报表已出"),
    ("test_group_a@chatroom", "wxid_admin_user", "下午3点开会讨论方案"),
]


class MockWcfClient(WcfClient):
    """Mock WeChatFerry client for development and debugging.

    Features:
      - Simulated contacts, groups, and members
      - Auto-generates periodic test messages (simulates real chat)
      - Thread-safe message queue for injection
      - Interactive CLI input (type messages directly in terminal)
      - Works on macOS/Linux without WeChat

    All "send" operations are logged but not actually delivered.
    """

    def __init__(self, auto_message_interval: float = 10.0, interactive: bool = True):
        self._connected = False
        self._receiving = False
        self._msg_queue: Queue[WxMessage] = Queue(maxsize=10000)
        self._auto_interval = auto_message_interval
        self._interactive = interactive
        self._auto_thread: Optional[threading.Thread] = None
        self._input_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._msg_counter = 0

    # ── Connection Lifecycle ──────────────────────────────────────────

    def connect(self) -> None:
        """Initialize mock connection (no-op)."""
        self._connected = True
        logger.info("MockWcfClient: Connected (simulated)")

    def disconnect(self) -> None:
        """Stop all threads and cleanup."""
        self.disable_receiving_msg()
        self._connected = False
        logger.info("MockWcfClient: Disconnected")

    def is_connected(self) -> bool:
        """Always returns True when mock is active."""
        return self._connected

    # ── Authentication ────────────────────────────────────────────────

    def is_login(self) -> bool:
        """Mock is always logged in."""
        return True

    def get_user_info(self) -> UserInfo:
        """Return mock user info."""
        return MOCK_USER

    def get_qrcode(self) -> str:
        """No QR code needed for mock."""
        return ""

    # ── Message Receiving ─────────────────────────────────────────────

    def enable_receiving_msg(self) -> bool:
        """Start auto-message generation and interactive input threads."""
        if self._receiving:
            return True

        self._receiving = True
        self._stop_event.clear()

        # Start auto-message thread
        if self._auto_interval > 0:
            self._auto_thread = threading.Thread(
                target=self._auto_message_loop,
                name="MockAutoMsgThread",
                daemon=True,
            )
            self._auto_thread.start()
            logger.info("MockWcfClient: Auto messages every %.1fs", self._auto_interval)

        # Start interactive input thread
        if self._interactive:
            self._input_thread = threading.Thread(
                target=self._interactive_input_loop,
                name="MockInputThread",
                daemon=True,
            )
            self._input_thread.start()
            logger.info("MockWcfClient: Interactive input enabled (type messages in terminal)")

        return True

    def disable_receiving_msg(self) -> bool:
        """Stop all message generation threads."""
        self._receiving = False
        self._stop_event.set()
        if self._auto_thread:
            self._auto_thread.join(timeout=3.0)
            self._auto_thread = None
        if self._input_thread:
            self._input_thread.join(timeout=1.0)
            self._input_thread = None
        return True

    def is_receiving_msg(self) -> bool:
        """Check if mock message generation is active."""
        return self._receiving

    def get_msg(self, timeout: float = 1.0) -> Optional[WxMessage]:
        """Get next message from the mock queue."""
        try:
            return self._msg_queue.get(timeout=timeout)
        except Empty:
            return None

    # ── Message Sending ──────────────────────────────────────────────

    def send_text(self, msg: str, receiver: str, at_list: Optional[List[str]] = None) -> int:
        """Log the send operation (no real delivery)."""
        at_str = f" (AT: {at_list})" if at_list else ""
        logger.info("📨 [MOCK SEND] To: %s | Content: %s%s", receiver, msg[:100], at_str)
        print(f"\n  📤 [MOCK] -> {receiver}: {msg[:200]}")
        return 0

    def send_image(self, path: str, receiver: str) -> int:
        """Log the image send (no real delivery)."""
        logger.info("📨 [MOCK SEND IMAGE] To: %s | Path: %s", receiver, path)
        print(f"\n  📤 [MOCK IMAGE] -> {receiver}: {path}")
        return 0

    def send_file(self, path: str, receiver: str) -> int:
        """Log the file send (no real delivery)."""
        logger.info("📨 [MOCK SEND FILE] To: %s | Path: %s", receiver, path)
        print(f"\n  📤 [MOCK FILE] -> {receiver}: {path}")
        return 0

    # ── Contacts ──────────────────────────────────────────────────────

    def get_contacts(self) -> List[Contact]:
        """Return mock contacts."""
        return list(MOCK_CONTACTS)

    def get_friends(self) -> List[Contact]:
        """Return mock friends (non-group contacts)."""
        return [c for c in MOCK_CONTACTS if not c.is_group]

    def get_info_by_wxid(self, wxid: str) -> Optional[Contact]:
        """Look up mock contact by wxid."""
        # Check in predefined contacts
        for c in MOCK_CONTACTS:
            if c.wxid == wxid:
                return c
        # Check in group members
        for members in MOCK_GROUP_MEMBERS.values():
            if wxid in members:
                return Contact(wxid=wxid, name=members[wxid], alias="", type=0, remark="")
        # Generate a generic contact for unknown wxids
        if wxid.startswith("wxid_"):
            return Contact(wxid=wxid, name=f"用户_{wxid[-4:]}", alias="", type=0, remark="")
        return None

    # ── Groups ────────────────────────────────────────────────────────

    def get_chatroom_members(self, room_id: str) -> Dict[str, str]:
        """Return mock group members."""
        members = MOCK_GROUP_MEMBERS.get(room_id, {})
        if not members:
            logger.debug("Mock: Unknown group %s, returning empty members", room_id)
        return dict(members)

    def get_chatroom_info(self, room_id: str) -> Optional[GroupInfo]:
        """Return mock group info."""
        contact = self.get_info_by_wxid(room_id)
        if contact and contact.is_group:
            info = GroupInfo.from_contact(contact)
            members = self.get_chatroom_members(room_id)
            info.member_count = len(members)
            info.members = members
            return info
        return None

    # ── Database ──────────────────────────────────────────────────────

    def query_sql(self, db: str, sql: str) -> List[Dict[str, Any]]:
        """Not supported in mock mode."""
        logger.warning("MockWcfClient: query_sql not supported in mock mode")
        return []

    # ── Message Injection ─────────────────────────────────────────────

    def inject_message(
        self,
        content: str,
        sender: str = "wxid_friend_li",
        room_id: str = "",
        msg_type: int = 1,
        at_wxids: Optional[List[str]] = None,
    ) -> WxMessage:
        """Inject a message into the mock queue.

        Useful for testing handlers programmatically.

        Args:
            content: Message content.
            sender: Sender wxid.
            room_id: Room ID (empty for private message).
            msg_type: Message type (1=text, 3=image, etc.).
            at_wxids: List of wxids that were @mentioned.

        Returns:
            The created WxMessage.
        """
        self._msg_counter += 1
        sender_name = ""
        contact = self.get_info_by_wxid(sender)
        if contact:
            sender_name = contact.name

        # Generate XML with atuserlist if at_wxids provided
        xml = ""
        if at_wxids:
            at_list_str = "|".join(at_wxids)
            xml = f'<msg><atuserlist>{at_list_str}</atuserlist></msg>'

        msg = WxMessage(
            msg_id=f"mock_{self._msg_counter}",
            type=msg_type,
            content=content,
            sender=sender,
            room_id=room_id,
            sender_name=sender_name,
            xml=xml,
            thumb="",
            extra="",
            at_wxids=at_wxids or [],
            timestamp=time.time(),
        )
        self._msg_queue.put(msg)
        logger.debug("Injected mock message: %s -> %s (at=%s)", sender, content[:50], at_wxids)
        return msg

    # ── Background Threads ───────────────────────────────────────────

    def _auto_message_loop(self) -> None:
        """Periodically generate simulated group messages."""
        while not self._stop_event.is_set():
            try:
                # Pick a random message template
                room_id, sender, content = random.choice(MOCK_MESSAGE_TEMPLATES)
                # Add some variation
                variations = [
                    content,
                    content + " [变异1]",
                    content + " [变异2]",
                    f"@所有人 {content}",
                ]
                chosen = random.choice(variations)

                # Occasionally add @bot for testing at_me_required
                at_bot = random.random() < 0.15  # 15% chance
                at_wxids = ["wxid_mock_bot"] if at_bot else None

                self.inject_message(content=chosen, sender=sender, room_id=room_id, at_wxids=at_wxids)
            except Exception as e:
                logger.error("Auto-message error: %s", e)

            self._stop_event.wait(timeout=self._auto_interval)

    def _interactive_input_loop(self) -> None:
        """Read messages from stdin for interactive testing.

        Input format:
          - Plain text: private message from admin
          - g:<room_id> <text>: group message from admin
          - s:<wxid> <text>: private message from specific wxid
          - sg:<room_id> <wxid> <text>: group message from specific sender
          - quit: stop the bot
        """
        print("\n" + "=" * 60)
        print("  🧪 MockWcfClient - 交互式调试模式")
        print("=" * 60)
        print("  输入格式:")
        print("    <文本>                     私聊消息(来自管理员)")
        print("    g:<群ID> <文本>            群聊消息(来自管理员)")
        print("    s:<wxid> <文本>            私聊消息(来自指定用户)")
        print("    sg:<群ID> <wxid> <文本>    群聊消息(来自指定用户)")
        print("    @:<群ID> <wxid> <文本>     群聊@机器人消息")
        print("    quit                       退出")
        print("-" * 60)
        print("  示例:")
        print("    #帮助                          → 发送命令")
        print("    g:test_group_a@chatroom 你好   → 在测试群A发消息")
        print("    s:wxid_friend_li #帮助         → 模拟李四私聊发命令")
        print("    @:test_group_a@chatroom wxid_friend_li 你好  → 李四在群A@机器人")
        print("=" * 60 + "\n")

        while not self._stop_event.is_set():
            try:
                line = input("🔧 MockInput> ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not line:
                continue
            if line.lower() == "quit":
                self._stop_event.set()
                break

            # Parse input format
            if line.startswith("@:"):
                # @:<room_id> <wxid> <text> — group message @mentioning the bot
                parts = line[2:].split(maxsplit=2)
                if len(parts) >= 3:
                    self.inject_message(
                        content=parts[2], sender=parts[1], room_id=parts[0],
                        at_wxids=["wxid_mock_bot"],
                    )
                else:
                    print("  ⚠️ 格式: @:<群ID> <wxid> <文本>")
            elif line.startswith("sg:"):
                # sg:<room_id> <wxid> <text>
                parts = line[3:].split(maxsplit=2)
                if len(parts) >= 3:
                    self.inject_message(content=parts[2], sender=parts[1], room_id=parts[0])
                else:
                    print("  ⚠️ 格式: sg:<群ID> <wxid> <文本>")
            elif line.startswith("g:"):
                # g:<room_id> <text>
                parts = line[2:].split(maxsplit=1)
                if len(parts) >= 2:
                    self.inject_message(content=parts[1], sender="wxid_admin_user", room_id=parts[0])
                else:
                    print("  ⚠️ 格式: g:<群ID> <文本>")
            elif line.startswith("s:"):
                # s:<wxid> <text>
                parts = line[2:].split(maxsplit=1)
                if len(parts) >= 2:
                    self.inject_message(content=parts[1], sender=parts[0], room_id="")
                else:
                    print("  ⚠️ 格式: s:<wxid> <文本>")
            else:
                # Default: private message from admin
                self.inject_message(content=line, sender="wxid_admin_user", room_id="")
