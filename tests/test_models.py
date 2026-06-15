"""Tests for WCF models."""

from bot.wcf.models import WxMessage, Contact, UserInfo, GroupInfo, MessageType


class TestWxMessage:
    """Tests for WxMessage model."""

    def test_is_group(self):
        msg = WxMessage(msg_id="1", type=1, content="hello", sender="wxid_test", room_id="test@chatroom")
        assert msg.is_group is True
        assert msg.is_private is False

    def test_is_private(self):
        msg = WxMessage(msg_id="1", type=1, content="hello", sender="wxid_test", room_id="")
        assert msg.is_group is False
        assert msg.is_private is True

    def test_is_text(self):
        msg = WxMessage(msg_id="1", type=1, content="hello", sender="wxid_test", room_id="")
        assert msg.is_text is True

    def test_is_not_text(self):
        msg = WxMessage(msg_id="1", type=3, content="", sender="wxid_test", room_id="")
        assert msg.is_text is False

    def test_is_system(self):
        msg = WxMessage(msg_id="1", type=10000, content="revoked", sender="system", room_id="")
        assert msg.is_system is True

    def test_type_name(self):
        msg = WxMessage(msg_id="1", type=1, content="", sender="", room_id="")
        assert msg.type_name == "TEXT"

    def test_unknown_type_name(self):
        msg = WxMessage(msg_id="1", type=99999, content="", sender="", room_id="")
        assert "UNKNOWN" in msg.type_name

    def test_to_dict(self):
        msg = WxMessage(msg_id="1", type=1, content="hello", sender="wxid_test", room_id="test@chatroom")
        d = msg.to_dict()
        assert d["msg_id"] == "1"
        assert d["type"] == 1
        assert "is_group" not in d  # Properties are not serialized


class TestContact:
    """Tests for Contact model."""

    def test_is_group(self):
        c = Contact(wxid="test@chatroom", name="TestGroup")
        assert c.is_group is True

    def test_is_not_group(self):
        c = Contact(wxid="wxid_test", name="TestUser")
        assert c.is_group is False


class TestMessageType:
    """Tests for MessageType enum."""

    def test_name_of_known(self):
        assert MessageType.name_of(1) == "TEXT"
        assert MessageType.name_of(3) == "IMAGE"

    def test_name_of_unknown(self):
        name = MessageType.name_of(99999)
        assert "UNKNOWN" in name


class TestGroupInfo:
    """Tests for GroupInfo model."""

    def test_from_contact(self):
        c = Contact(wxid="test@chatroom", name="Test Group")
        gi = GroupInfo.from_contact(c)
        assert gi.room_id == "test@chatroom"
        assert gi.room_name == "Test Group"
