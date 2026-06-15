"""WeChatFerry client abstraction with local and remote modes.

- LocalWcfClient: Direct wcferry connection (requires Windows + WeChat running)
- RemoteWcfClient: HTTP API connection to a remote wcfhttp server (Linux compatible)

Both implement the same WcfClient protocol, allowing transparent mode switching.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from queue import Empty, Queue
from threading import Event, Thread
from typing import Any, Dict, List, Optional

from bot.config.settings import BotSettings
from bot.core.exceptions import WcfConnectionError, WcfNotLoggedInError, WcfSendError
from bot.wcf.models import Contact, GroupInfo, UserInfo, WxMessage

logger = logging.getLogger("WeChatBot.Wcf")


class WcfClient(ABC):
    """Abstract WeChatFerry client interface.

    All methods that interact with WeChat go through this interface,
    enabling transparent switching between local and remote modes.
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
    Requires WeChat to be running on the same Windows machine.
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


class RemoteWcfClient(WcfClient):
    """Remote WeChatFerry HTTP API client (Linux compatible).

    Connects to a wcfhttp server running on a Windows machine.
    This enables deploying the bot on Linux while the WeChat client runs elsewhere.

    The wcfhttp server can be started with:
      - wcfrust (Rust): https://github.com/lich0821/wcf-client-rust
      - go_wcf_http (Go): https://github.com/lzb112/WeChatFerryX/clients/go_wcf_http

    Default API base URL: http://<host>:<port>
    """

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._connected = False
        self._msg_queue: Queue[WxMessage] = Queue(maxsize=10000)
        self._receiving = False
        self._poll_thread: Optional[Thread] = None
        self._stop_event = Event()

    def _request(self, method: str, path: str, json_data: Optional[Dict] = None, params: Optional[Dict] = None) -> Any:
        """Make an HTTP request to the wcfhttp server."""
        import requests

        url = f"{self._base_url}{path}"
        try:
            resp = requests.request(method, url, json=json_data, params=params, timeout=self._timeout)
            resp.raise_for_status()
            return resp.json() if resp.content else None
        except requests.RequestException as e:
            raise WcfConnectionError(f"HTTP request failed: {method} {url} - {e}")

    def connect(self) -> None:
        """Verify connectivity to the remote wcfhttp server."""
        try:
            result = self._request("GET", "/api/islogin")
            self._connected = True
            logger.info("RemoteWcfClient: Connected to %s", self._base_url)
        except Exception as e:
            raise WcfConnectionError(f"Cannot connect to remote WCF server at {self._base_url}: {e}")

    def disconnect(self) -> None:
        """Stop polling and cleanup."""
        self._receiving = False
        self._stop_event.set()
        if self._poll_thread:
            self._poll_thread.join(timeout=5.0)
            self._poll_thread = None
        self._connected = False

    def is_connected(self) -> bool:
        """Check if the remote server is reachable."""
        if not self._connected:
            return False
        try:
            self._request("GET", "/api/islogin")
            return True
        except Exception:
            return False

    def is_login(self) -> bool:
        """Check if WeChat is logged in on the remote server."""
        try:
            result = self._request("GET", "/api/islogin")
            return bool(result)
        except Exception:
            return False

    def get_user_info(self) -> UserInfo:
        """Get logged-in user info."""
        data = self._request("GET", "/api/user_info")
        return UserInfo.from_dict(data or {})

    def get_qrcode(self) -> str:
        """Get login QR code."""
        result = self._request("GET", "/api/qrcode")
        return str(result) if result else ""

    def enable_receiving_msg(self) -> bool:
        """Start polling messages from the remote server."""
        self._receiving = True
        self._stop_event.clear()
        self._poll_thread = Thread(target=self._poll_messages, name="RemoteWcfPollThread", daemon=True)
        self._poll_thread.start()
        logger.info("RemoteWcfClient: Started message polling")
        return True

    def disable_receiving_msg(self) -> bool:
        """Stop polling messages."""
        self._receiving = False
        self._stop_event.set()
        if self._poll_thread:
            self._poll_thread.join(timeout=5.0)
            self._poll_thread = None
        return True

    def is_receiving_msg(self) -> bool:
        """Check if message polling is active."""
        return self._receiving

    def get_msg(self, timeout: float = 1.0) -> Optional[WxMessage]:
        """Get next message from the local queue."""
        try:
            return self._msg_queue.get(timeout=timeout)
        except Empty:
            return None

    def _poll_messages(self) -> None:
        """Background thread that polls the remote WCF server for messages."""
        import requests

        url = f"{self._base_url}/api/msg"
        while not self._stop_event.is_set():
            try:
                resp = requests.get(url, timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        # The HTTP API may return a list of messages
                        messages = data if isinstance(data, list) else [data]
                        for msg_data in messages:
                            try:
                                msg = WxMessage.from_http_msg(msg_data)
                                self._msg_queue.put_nowait(msg)
                            except Exception as e:
                                logger.error("Failed to parse remote message: %s", e)
            except requests.RequestException:
                pass  # Will retry on next poll
            except Exception as e:
                logger.error("Error polling remote messages: %s", e)

            self._stop_event.wait(timeout=0.5)

    def send_text(self, msg: str, receiver: str, at_list: Optional[List[str]] = None) -> int:
        """Send a text message via the remote API."""
        payload = {"msg": msg, "receiver": receiver}
        if at_list:
            payload["aters"] = at_list
        try:
            result = self._request("POST", "/api/send_text", json_data=payload)
            return 0 if result else -1
        except Exception as e:
            raise WcfSendError(receiver, str(e))

    def send_image(self, path: str, receiver: str) -> int:
        """Send an image message via the remote API."""
        payload = {"path": path, "receiver": receiver}
        try:
            result = self._request("POST", "/api/send_image", json_data=payload)
            return 0 if result else -1
        except Exception as e:
            raise WcfSendError(receiver, str(e))

    def send_file(self, path: str, receiver: str) -> int:
        """Send a file message via the remote API."""
        payload = {"path": path, "receiver": receiver}
        try:
            result = self._request("POST", "/api/send_file", json_data=payload)
            return 0 if result else -1
        except Exception as e:
            raise WcfSendError(receiver, str(e))

    def get_contacts(self) -> List[Contact]:
        """Get all contacts from the remote server."""
        data = self._request("GET", "/api/contacts")
        if isinstance(data, list):
            return [Contact.from_http_contact(c) for c in data]
        return []

    def get_friends(self) -> List[Contact]:
        """Get friends from the remote server."""
        data = self._request("GET", "/api/friends")
        if isinstance(data, list):
            return [Contact.from_http_contact(c) for c in data]
        return []

    def get_info_by_wxid(self, wxid: str) -> Optional[Contact]:
        """Get contact info by wxid."""
        try:
            data = self._request("GET", f"/api/info_by_wxid", params={"wxid": wxid})
            return Contact.from_http_contact(data) if data else None
        except Exception:
            return None

    def get_chatroom_members(self, room_id: str) -> Dict[str, str]:
        """Get group members from the remote server."""
        try:
            data = self._request("GET", "/api/chatroom_members", params={"roomid": room_id})
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def get_chatroom_info(self, room_id: str) -> Optional[GroupInfo]:
        """Get group info from the remote server."""
        contact = self.get_info_by_wxid(room_id)
        if contact:
            info = GroupInfo.from_contact(contact)
            members = self.get_chatroom_members(room_id)
            info.member_count = len(members)
            info.members = members
            return info
        return None

    def query_sql(self, db: str, sql: str) -> List[Dict[str, Any]]:
        """Execute SQL on the remote WeChat database."""
        payload = {"db": db, "sql": sql}
        result = self._request("POST", "/api/query_sql", json_data=payload)
        return result if isinstance(result, list) else []


def create_wcf_client(bot_settings: BotSettings) -> WcfClient:
    """Factory function to create the appropriate WCF client.

    Args:
        bot_settings: Bot settings with wcf_mode and wcf_remote_url.

    Returns:
        A WcfClient instance (LocalWcfClient, RemoteWcfClient, or MockWcfClient).
    """
    if bot_settings.wcf_mode == "mock":
        from bot.wcf.mock_client import MockWcfClient
        logger.info("Using MOCK WCF client (development/debug mode)")
        return MockWcfClient(auto_message_interval=10.0, interactive=True)
    elif bot_settings.wcf_mode == "remote":
        logger.info("Using remote WCF client: %s", bot_settings.wcf_remote_url)
        return RemoteWcfClient(base_url=bot_settings.wcf_remote_url)
    else:
        logger.info("Using local WCF client (wcferry)")
        return LocalWcfClient()
