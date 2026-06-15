"""Data models for WeChat messages, contacts, and groups.

These models provide a stable, typed interface regardless of the WCF client implementation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional


class MessageType(IntEnum):
    """WeChat message type enumeration."""

    MOMENTS = 0
    TEXT = 1
    IMAGE = 3
    VOICE = 34
    FRIEND_CONFIRM = 37
    POSSIBLE_FRIEND = 40
    CARD = 42
    VIDEO = 43
    EMOJI = 47
    LOCATION = 48
    FILE_LINK = 49
    VOIP = 50
    WECHAT_INIT = 51
    VOIP_NOTIFY = 52
    VOIP_INVITE = 53
    MINI_VIDEO = 62
    RED_PACKET = 66
    SYS_NOTICE = 9999
    SYSTEM = 10000
    REVOKE = 10002
    SOGOU_EMOJI = 1048625
    LINK = 16777265

    @classmethod
    def name_of(cls, msg_type: int) -> str:
        """Get human-readable name for a message type ID."""
        try:
            return cls(msg_type).name
        except ValueError:
            return f"UNKNOWN_{msg_type}"


@dataclass
class WxMessage:
    """Structured WeChat message model.

    This is a normalized representation that works across local and remote WCF clients.
    """

    msg_id: str
    type: int
    content: str
    sender: str
    room_id: str  # Empty string for non-group messages
    sender_name: str = ""
    xml: str = ""
    thumb: str = ""
    extra: str = ""
    timestamp: float = field(default_factory=time.time)

    @property
    def is_group(self) -> bool:
        """Check if this is a group message."""
        return bool(self.room_id) and self.room_id.endswith("@chatroom")

    @property
    def is_private(self) -> bool:
        """Check if this is a private (1-on-1) message."""
        return not self.is_group

    @property
    def is_text(self) -> bool:
        """Check if this is a text message."""
        return self.type == MessageType.TEXT

    @property
    def is_system(self) -> bool:
        """Check if this is a system message."""
        return self.type in (MessageType.SYSTEM, MessageType.SYS_NOTICE, MessageType.REVOKE)

    @property
    def type_name(self) -> str:
        """Get human-readable message type name."""
        return MessageType.name_of(self.type)

    @classmethod
    def from_wcf_msg(cls, msg: Any) -> "WxMessage":
        """Create from a wcferry WxMsg object."""
        return cls(
            msg_id=str(msg.id),
            type=msg.type,
            content=msg.content or "",
            sender=msg.sender or "",
            room_id=msg.roomid or "",
            xml=getattr(msg, "xml", "") or "",
            thumb=getattr(msg, "thumb", "") or "",
            extra=getattr(msg, "extra", "") or "",
        )

    @classmethod
    def from_http_msg(cls, data: Dict[str, Any]) -> "WxMessage":
        """Create from HTTP API response dict."""
        return cls(
            msg_id=str(data.get("id", "")),
            type=data.get("type", 0),
            content=data.get("content", ""),
            sender=data.get("sender", ""),
            room_id=data.get("roomid", ""),
            xml=data.get("xml", ""),
            thumb=data.get("thumb", ""),
            extra=data.get("extra", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for storage/API."""
        return {
            "msg_id": self.msg_id,
            "type": self.type,
            "type_name": self.type_name,
            "content": self.content,
            "sender": self.sender,
            "sender_name": self.sender_name,
            "room_id": self.room_id,
            "xml": self.xml,
            "timestamp": self.timestamp,
        }


@dataclass
class Contact:
    """WeChat contact model."""

    wxid: str
    name: str = ""
    alias: str = ""
    type: int = 0  # 0=friend, 1=group, 2=subscription, 3=service
    remark: str = ""

    @property
    def is_group(self) -> bool:
        """Check if this is a group contact."""
        return self.wxid.endswith("@chatroom")

    @property
    def is_official(self) -> bool:
        """Check if this is an official account."""
        return self.type in (2, 3)

    @classmethod
    def from_wcf_contact(cls, data: Dict[str, Any]) -> "Contact":
        """Create from wcferry contact dict."""
        return cls(
            wxid=data.get("wxid", ""),
            name=data.get("name", ""),
            alias=data.get("alias", ""),
            type=data.get("type", 0),
            remark=data.get("remark", ""),
        )

    @classmethod
    def from_http_contact(cls, data: Dict[str, Any]) -> "Contact":
        """Create from HTTP API response dict."""
        return cls(
            wxid=data.get("wxid", data.get("Wxid", "")),
            name=data.get("name", data.get("Name", "")),
            alias=data.get("alias", data.get("Alias", "")),
            type=data.get("type", 0),
        )


@dataclass
class UserInfo:
    """Logged-in user information."""

    wxid: str = ""
    name: str = ""
    mobile: str = ""
    home: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserInfo":
        """Create from a dict."""
        return cls(
            wxid=data.get("wxid", ""),
            name=data.get("name", ""),
            mobile=data.get("mobile", ""),
            home=data.get("home", ""),
        )


@dataclass
class GroupInfo:
    """Group information with metadata."""

    room_id: str
    room_name: str = ""
    member_count: int = 0
    owner_wxid: str = ""
    members: Dict[str, str] = field(default_factory=dict)  # wxid -> nickname

    @property
    def is_monitored(self) -> bool:
        """Placeholder - actual check is in GroupFilter."""
        return True

    @classmethod
    def from_contact(cls, contact: Contact) -> "GroupInfo":
        """Create from a Contact object (group type)."""
        return cls(
            room_id=contact.wxid,
            room_name=contact.name,
        )
