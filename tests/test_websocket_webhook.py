import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from src.main import app
from src.web_connections import SubscriptionManager, ConnectionManager


@pytest.fixture
def client():
    return TestClient(app)


def test_websocket_subscribe_and_unsubscribe(client):
    """Test WebSocket subscription lifecycle."""
    with client.websocket_connect("/ws") as websocket:
        # Subscribe
        subscribe_msg = {"action": "subscribe", "events": ["torvalds"]}
        websocket.send_text(json.dumps(subscribe_msg))
        response = websocket.receive_text()
        assert json.loads(response) == {"status": "subscribed", "events": ["torvalds"]}

        # Unsubscribe
        unsubscribe_msg = {"action": "unsubscribe", "events": ["torvalds"]}
        websocket.send_text(json.dumps(unsubscribe_msg))
        response = websocket.receive_text()
        assert json.loads(response) == {
            "status": "unsubscribed",
            "events": ["torvalds"],
        }


def test_websocket_invalid_json(client):
    with client.websocket_connect("/ws") as websocket:
        websocket.send_text("not json")
        response = websocket.receive_text()
        assert "Invalid JSON" in response


def test_websocket_unknown_action(client):
    with client.websocket_connect("/ws") as websocket:
        websocket.send_text(json.dumps({"action": "pounce"}))
        response = websocket.receive_text()
        assert "unknown action" in response


@pytest.mark.asyncio
async def test_broadcast_event_to_subscribed_websocket():
    """Integration test: call an API endpoint, verify WebSocket receives event."""
    manager = ConnectionManager()
    subscription_manager = SubscriptionManager(service=AsyncMock())  # mock service
    # We would need to inject this manager into the app – this test requires refactoring.
    # Below is a simplified unit test for the manager itself.

    # Create a mock websocket
    mock_ws = AsyncMock()
    conn_id = await manager.connect(mock_ws)
    await manager.subscribe(conn_id, ["testuser"])

    # Broadcast an event
    await manager.broadcast_event("testuser", {"stars": 42})

    # The mock should have received one send_text call
    mock_ws.send_text.assert_awaited_once()
    sent = json.loads(mock_ws.send_text.call_args[0][0])
    assert sent == {"event": "testuser", "data": {"stars": 42}}


@pytest.mark.asyncio
async def test_webhook_delivery():
    """Test that a registered webhook receives the payload."""
    from src.models import WebhookSubscription
    from src.web_connections import SubscriptionManager
    from pydantic import HttpUrl

    mock_http = AsyncMock()
    sub = WebhookSubscription(
        url=HttpUrl("https://example.com/hook"), git_urls=["testuser"]
    )
    manager = SubscriptionManager(service=AsyncMock())
    await manager.start_worker()
    manager.webhook_subscriptions.append(sub)

    with patch("httpx.AsyncClient.post", mock_http):
        await manager.emit_event("testuser", {"stars": 99})
        # Give background task a moment to run
        await asyncio.sleep(0.1)
        mock_http.assert_awaited_once()
        call_args = mock_http.call_args
        assert call_args[0][0] == "https://example.com/hook"
        # Verify payload contains the event and data
        sent_json = call_args.kwargs["json"]
        assert sent_json["event"] == "testuser"
        assert sent_json["data"]["stars"] == 99
