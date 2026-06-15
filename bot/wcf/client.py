"""WeChatFerry client — Windows local mode only.

This project runs exclusively on Windows with WeChat installed.
The LocalWcfClient connects to a running WeChat instance via the wcferry SDK.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from queue import Empty
from typing import Any, Dict, List, Optional

from bot.core.exceptions import WcfConnectionError, WcfSendError
from bot.wcf.models import Contact, GroupInfo, UserInfo, WxMessage

logger = logging.getLogger("WeChatBot.Wcf")


class WcfClient(ABC):
    """Abstract WeChatFerry client interface.

    All methods that interact with WeChat go through this interface.
    Currently only LocalWcfClient is supported (Windows only).
    """

    # ── Connection Lifecycle ──────────────────────────────────────────

    @abstractmethod
    def connect(self) -> None:
        """Initialize the WCF connection."""

    @abstractmethod
    def disconnect(self) -> None:
        """Cleanup and disconnect."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if the client is connected and functional."""

    # ── Authentication ────────────────────────────────────────────────

    @abstractmethod
    def is_login(self) -> bool:
        """Check if WeChat is logged in."""

    @abstractmethod
    def get_user_info(self) -> UserInfo:
        """Get the logged-in user's info."""

    @abstractmethod
    def get_qrcode(self) -> str:
        """Get the login QR code string (empty if already logged in)."""

    # ── Message Receiving ─────────────────────────────────────────────

    @abstractmethod
    def enable_receiving_msg(self) -> bool:
        """Start receiving messages."""

    @abstractmethod
    def disable_receiving_msg(self) -> bool:
        """Stop receiving messages."""

    @abstractmethod
    def is_receiving_msg(self) -> bool:
        """Check if message receiving is active."""

    @abstractmethod
    def get_msg(self, timeout: float = 1.0) -> Optional[WxMessage]:
        """Get the next message from the queue.

        Args:
            timeout: Max seconds to wait. Returns None if no message.

        Returns:
            WxMessage or None if queue is empty.
        """

    # ── Message Sending ──────────────────────────────────────────────

    @abstractmethod
    def send_text(self, msg: str, receiver: str, at_list: Optional[List[str]] = None) -> int:
        """Send a text message.

        Args:
            msg: Message content.
            receiver: Receiver wxid or roomid.
            at_list: Optional list of wxids to @mention (group only).

        Returns:
            Result code (0 = success).
        """

    @abstractmethod
    def send_image(self, path: str, receiver: str) -> int:
        """Send an image message."""

    @abstractmethod
    def send_file(self, path: str, receiver: str) -> int:
        """Send a file message."""

    # ── Contacts ──────────────────────────────────────────────────────

    @abstractmethod
    def get_contacts(self) -> List[Contact]:
        """Get all contacts."""

    @abstractmethod
    def get_friends(self) -> List[Contact]:
        """Get all friends."""

    @abstractmethod
    def get_info_by_wxid(self, wxid: str) -> Optional[Contact]:
        """Get contact info by wxid."""

    # ── Groups ────────────────────────────────────────────────────────

    @abstractmethod
    def get_chatroom_members(self, room_id: str) -> Dict[str, str]:
        """Get group member dict {wxid: nickname}."""

    @abstractmethod
    def get_chatroom_info(self, room_id: str) -> Optional[GroupInfo]:
        """Get group info by roomid."""

    # ── Database ──────────────────────────────────────────────────────

    @abstractmethod
    def query_sql(self, db: str, sql: str) -> List[Dict[str, Any]]:
        """Execute a SQL query on a WeChat internal database."""


class LocalWcfClient(WcfClient):
    """Direct WeChatFerry connection (Windows only).

    Connects to a running WeChat instance via the wcferry SDK.
    Requires WeChat 3.9.12.51 to be running on the same Windows machine.
    """

    def __init__(self) -> None:
        self._wcf: Optional[Any] = None
        self._connected = False

    def connect(self) -> None:
        """Initialize wcferry and connect to WeChat."""
        try:
            from wcferry import Wcf
            self._wcf = Wcf()
            self._connected = True
            logger.info("LocalWcfClient: Connected to WeChat via wcferry")
        except ImportError:
            raise WcfConnectionError("wcferry package not installed. Run: pip install wcferry")
        except Exception as e:
            raise WcfConnectionError(f"Failed to connect to WeChat: {e}")

    def disconnect(self) -> None:
        """Cleanup wcferry connection."""
        if self._wcf:
            try:
                if self.is_receiving_msg():
                    self.disable_receiving_msg()
                self._wcf.cleanup()
            except Exception as e:
                logger.warning("Error during WCF cleanup: %s", e)
            finally:
                self._wcf = None
                self._connected = False

    def is_connected(self) -> bool:
        """Check if wcferry is connected."""
        return self._wcf is not None and self._connected

    def is_login(self) -> bool:
        """Check if WeChat is logged in."""
        if not self._wcf:
            return False
        return self._wcf.is_login()

    def get_user_info(self) -> UserInfo:
        """Get the logged-in user's info."""
        if not self._wcf:
            raise WcfConnectionError("Not connected")
        data = self._wcf.get_user_info()
        return UserInfo.from_dict(data)

    def get_qrcode(self) -> str:
        """Get login QR code."""
        if not self._wcf:
            raise WcfConnectionError("Not connected")
        return self._wcf.get_qrcode()

    def enable_receiving_msg(self) -> bool:
        """Enable message receiving."""
        if not self._wcf:
            raise WcfConnectionError("Not connected")
        return self._wcf.enable_receiving_msg()

    def disable_receiving_msg(self) -> bool:
        """Disable message receiving."""
        if not self._wcf:
            return False
        try:
            return self._wcf.disable_recv_msg()
        except Exception as e:
            logger.error("Failed to disable receiving: %s", e)
            return False

    def is_receiving_msg(self) -> bool:
        """Check if message receiving is active."""
        if not self._wcf:
            return False
        return self._wcf.is_receiving_msg()

    def get_msg(self, timeout: float = 1.0) -> Optional[WxMessage]:
        """Get next message from the queue."""
        if not self._wcf:
            return None
        try:
            raw_msg = self._wcf.get_msg()
            return WxMessage.from_wcf_msg(raw_msg)
        except Empty:
            return None
        except Exception as e:
            logger.error("Error getting message: %s", e)
            return None

    def send_text(self, msg: str, receiver: str, at_list: Optional[List[str]] = None) -> int:
        """Send a text message."""
        if not self._wcf:
            raise WcfSendError(receiver, "Not connected")
        try:
            if at_list:
                return self._wcf.send_text(msg, receiver, at_list)
            return self._wcf.send_text(msg, receiver)
        except Exception as e:
            raise WcfSendError(receiver, str(e))

    def send_image(self, path: str, receiver: str) -> int:
        """Send an image message."""
        if not self._wcf:
            raise WcfSendError(receiver, "Not connected")
        try:
            return self._wcf.send_image(path, receiver)
        except Exception as e:
            raise WcfSendError(receiver, str(e))

    def send_file(self, path: str, receiver: str) -> int:
        """Send a file message."""
        if not self._wcf:
            raise WcfSendError(receiver, "Not connected")
        try:
            return self._wcf.send_file(path, receiver)
        except Exception as e:
            raise WcfSendError(receiver, str(e))

    def get_contacts(self) -> List[Contact]:
        """Get all contacts."""
        if not self._wcf:
            raise WcfConnectionError("Not connected")
        raw = self._wcf.get_contacts()
        return [Contact.from_wcf_contact(c) for c in raw]

    def get_friends(self) -> List[Contact]:
        """Get all friends."""
        if not self._wcf:
            raise WcfConnectionError("Not connected")
        raw = self._wcf.get_friends()
        return [Contact.from_wcf_contact(c) for c in raw]

    def get_info_by_wxid(self, wxid: str) -> Optional[Contact]:
        """Get contact info by wxid."""
        if not self._wcf:
            return None
        try:
            data = self._wcf.get_info_by_wxid(wxid)
            return Contact.from_wcf_contact(data) if data else None
        except Exception as e:
            logger.error("Failed to get info for %s: %s", wxid, e)
            return None

    def get_chatroom_members(self, room_id: str) -> Dict[str, str]:
        """Get group members as {wxid: nickname}."""
        if not self._wcf:
            return {}
        try:
            return self._wcf.get_chatroom_members(room_id)
        except Exception as e:
            logger.error("Failed to get members for %s: %s", room_id, e)
            return {}

    def get_chatroom_info(self, room_id: str) -> Optional[GroupInfo]:
        """Get group info."""
        if not self._wcf:
            return None
        try:
            contact = self.get_info_by_wxid(room_id)
            if contact:
                info = GroupInfo.from_contact(contact)
                members = self.get_chatroom_members(room_id)
                info.member_count = len(members)
                info.members = members
                return info
            return None
        except Exception as e:
            logger.error("Failed to get chatroom info for %s: %s", room_id, e)
            return None

    def query_sql(self, db: str, sql: str) -> List[Dict[str, Any]]:
        """Execute SQL on WeChat database."""
        if not self._wcf:
            raise WcfConnectionError("Not connected")
        return self._wcf.query_sql(db, sql)


def create_wcf_client() -> WcfClient:
    """Create a LocalWcfClient instance.

    Returns:
        A LocalWcfClient connected to the local WeChat instance.
    """
    logger.info("Using local WCF client (wcferry on Windows)")
    return LocalWcfClient()
