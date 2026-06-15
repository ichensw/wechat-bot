"""Tests for MockWcfClient."""

import time

from bot.wcf.mock_client import MockWcfClient, MOCK_CONTACTS, MOCK_GROUP_MEMBERS


class TestMockWcfClient:
    """Tests for MockWcfClient."""

    def test_connect_and_login(self):
        client = MockWcfClient(auto_message_interval=0, interactive=False)
        client.connect()
        assert client.is_connected() is True
        assert client.is_login() is True

    def test_get_user_info(self):
        client = MockWcfClient(auto_message_interval=0, interactive=False)
        user = client.get_user_info()
        assert user.wxid == "wxid_mock_bot"
        assert user.name == "调试机器人"

    def test_get_contacts(self):
        client = MockWcfClient(auto_message_interval=0, interactive=False)
        contacts = client.get_contacts()
        assert len(contacts) > 0
        groups = [c for c in contacts if c.is_group]
        friends = [c for c in contacts if not c.is_group]
        assert len(groups) >= 3  # At least 3 mock groups
        assert len(friends) >= 3  # At least 3 mock friends

    def test_get_friends(self):
        client = MockWcfClient(auto_message_interval=0, interactive=False)
        friends = client.get_friends()
        for f in friends:
            assert not f.is_group

    def test_get_info_by_wxid_known(self):
        client = MockWcfClient(auto_message_interval=0, interactive=False)
        contact = client.get_info_by_wxid("wxid_admin_user")
        assert contact is not None
        assert contact.name == "管理员张三"

    def test_get_info_by_wxid_group(self):
        client = MockWcfClient(auto_message_interval=0, interactive=False)
        contact = client.get_info_by_wxid("test_group_a@chatroom")
        assert contact is not None
        assert contact.is_group

    def test_get_info_by_wxid_unknown(self):
        client = MockWcfClient(auto_message_interval=0, interactive=False)
        contact = client.get_info_by_wxid("wxid_nonexistent")
        assert contact is not None  # Generates generic contact
        assert "用户" in contact.name

    def test_get_chatroom_members(self):
        client = MockWcfClient(auto_message_interval=0, interactive=False)
        members = client.get_chatroom_members("test_group_a@chatroom")
        assert len(members) > 0
        assert "wxid_admin_user" in members

    def test_get_chatroom_info(self):
        client = MockWcfClient(auto_message_interval=0, interactive=False)
        info = client.get_chatroom_info("test_group_a@chatroom")
        assert info is not None
        assert info.room_id == "test_group_a@chatroom"
        assert info.member_count > 0

    def test_inject_message(self):
        client = MockWcfClient(auto_message_interval=0, interactive=False)
        client.connect()
        msg = client.inject_message(
            content="Hello test",
            sender="wxid_friend_li",
            room_id="test_group_a@chatroom",
        )
        assert msg.content == "Hello test"
        assert msg.sender == "wxid_friend_li"
        assert msg.is_group is True

        # Should be retrievable from queue
        received = client.get_msg(timeout=1.0)
        assert received is not None
        assert received.content == "Hello test"

    def test_inject_private_message(self):
        client = MockWcfClient(auto_message_interval=0, interactive=False)
        client.connect()
        msg = client.inject_message(
            content="#帮助",
            sender="wxid_admin_user",
            room_id="",
        )
        assert msg.is_private is True

    def test_send_text(self):
        client = MockWcfClient(auto_message_interval=0, interactive=False)
        result = client.send_text("Test message", "wxid_admin_user")
        assert result == 0  # Success

    def test_send_image(self):
        client = MockWcfClient(auto_message_interval=0, interactive=False)
        result = client.send_image("/tmp/test.png", "wxid_admin_user")
        assert result == 0

    def test_send_file(self):
        client = MockWcfClient(auto_message_interval=0, interactive=False)
        result = client.send_file("/tmp/test.pdf", "wxid_admin_user")
        assert result == 0

    def test_disconnect(self):
        client = MockWcfClient(auto_message_interval=0, interactive=False)
        client.connect()
        client.enable_receiving_msg()
        client.disconnect()
        assert client.is_connected() is False
        assert client.is_receiving_msg() is False

    def test_query_sql_returns_empty(self):
        client = MockWcfClient(auto_message_interval=0, interactive=False)
        result = client.query_sql("MicroMsg.db", "SELECT * FROM Contact")
        assert result == []
