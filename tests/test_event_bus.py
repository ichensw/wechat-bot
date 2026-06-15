"""Tests for event bus."""

import time
from bot.core.event_bus import EventBus, Event, EventTypes


class TestEventBus:
    """Tests for EventBus."""

    def test_publish_and_receive(self):
        bus = EventBus()
        received = []

        def handler(event: Event):
            received.append(event)

        bus.subscribe("test.event", handler)
        bus.publish("test.event", data={"key": "value"}, source="test")

        assert len(received) == 1
        assert received[0].type == "test.event"
        assert received[0].data == {"key": "value"}

    def test_prefix_matching(self):
        bus = EventBus()
        received = []

        def handler(event: Event):
            received.append(event)

        bus.subscribe("group.", handler)
        bus.publish("group.member_change", data={"room": "test"}, source="test")
        bus.publish("other.event", data={}, source="test")

        assert len(received) == 1
        assert received[0].type == "group.member_change"

    def test_multiple_subscribers(self):
        bus = EventBus()
        count = [0]

        def handler1(event: Event):
            count[0] += 1

        def handler2(event: Event):
            count[0] += 10

        bus.subscribe("test", handler1)
        bus.subscribe("test", handler2)
        bus.publish("test", source="test")

        assert count[0] == 11  # Both handlers called

    def test_unsubscribe(self):
        bus = EventBus()
        received = []

        def handler(event: Event):
            received.append(event)

        bus.subscribe("test", handler)
        bus.unsubscribe("test", handler)
        bus.publish("test", source="test")

        assert len(received) == 0

    def test_async_handler(self):
        bus = EventBus(max_workers=2)
        result = []

        def async_handler(event: Event):
            import time
            time.sleep(0.1)
            result.append(event.type)

        bus.subscribe_async("test.async", async_handler)
        bus.publish("test.async", source="test")
        time.sleep(0.3)  # Wait for async handler
        assert len(result) == 1

    def test_event_history(self):
        bus = EventBus()
        bus.publish("event.a", source="test")
        bus.publish("event.b", source="test")
        bus.publish("event.a", source="test")

        history = bus.get_history()
        assert len(history) == 3

        filtered = bus.get_history(event_type="event.a")
        assert len(filtered) == 2

    def test_disabled_bus(self):
        bus = EventBus()
        received = []

        def handler(event: Event):
            received.append(event)

        bus.subscribe("test", handler)
        bus.shutdown()
        bus.publish("test", source="test")

        assert len(received) == 0

    def test_event_types_constants(self):
        assert EventTypes.MSG_GROUP == "msg.group"
        assert EventTypes.BOT_STARTED == "bot.started"
        assert EventTypes.ADMIN_BOUND == "admin.bound"
