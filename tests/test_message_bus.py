"""Tests for MessageBus (bus/queue.py)."""

import asyncio

import pytest

from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus


@pytest.fixture
def bus() -> MessageBus:
    return MessageBus()


# --- Tests ---


@pytest.mark.asyncio
async def test_publish_consume_inbound(bus: MessageBus) -> None:
    msg = InboundMessage(
        channel="telegram",
        sender_id="user1",
        chat_id="chat1",
        content="hello",
    )
    await bus.publish_inbound(msg)
    assert bus.inbound_size == 1
    received = await bus.consume_inbound()
    assert received.content == "hello"
    assert received.channel == "telegram"
    assert bus.inbound_size == 0


@pytest.mark.asyncio
async def test_publish_consume_outbound(bus: MessageBus) -> None:
    msg = OutboundMessage(
        channel="discord",
        chat_id="ch42",
        content="response text",
    )
    await bus.publish_outbound(msg)
    assert bus.outbound_size == 1
    received = await bus.consume_outbound()
    assert received.content == "response text"
    assert received.channel == "discord"
    assert bus.outbound_size == 0


@pytest.mark.asyncio
async def test_consume_timeout(bus: MessageBus) -> None:
    """Consuming from an empty queue should block; with a timeout it raises."""
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(bus.consume_inbound(), timeout=0.05)
