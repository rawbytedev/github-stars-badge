"""Unit tests for ConnectionManager and SubscriptionManager."""

import asyncio
import json
from unittest.mock import AsyncMock, patch
import pytest
from fastapi import WebSocket
from pydantic import HttpUrl
from src.web_connections import ConnectionManager, SubscriptionManager
from src.services import GitHubService
from src.models import WebhookSubscription



class TestConnectionManager:
    """Test WebSocket connection manager."""

    @pytest.mark.asyncio
    async def test_connect(self):
        manager = ConnectionManager()
        mock_ws = AsyncMock(spec=WebSocket)

        conn_id = await manager.connect(mock_ws)

        assert conn_id in manager.active_connections
        assert conn_id in manager.conn_subscriptions
        mock_ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect(self):
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        conn_id = await manager.connect(mock_ws)

        manager.disconnect(conn_id)

        assert conn_id not in manager.active_connections
        assert conn_id not in manager.conn_subscriptions

    @pytest.mark.asyncio
    async def test_subscribe_and_unsubscribe(self):
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        conn_id = await manager.connect(mock_ws)
        events = ["user1", "user2"]

        await manager.subscribe(conn_id, events)

        assert manager.event_subscribers["user1"] == {conn_id}
        assert manager.event_subscribers["user2"] == {conn_id}
        assert manager.conn_subscriptions[conn_id] == set(events)

        await manager.unsubscribe(conn_id, ["user1"])

        assert "user1" not in manager.event_subscribers
        assert manager.conn_subscriptions[conn_id] == {"user2"}

    @pytest.mark.asyncio
    async def test_broadcast_event(self):
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        conn_id = await manager.connect(mock_ws)
        await manager.subscribe(conn_id, ["test_event"])

        await manager.broadcast_event("test_event", {"stars": 42})

        mock_ws.send_text.assert_awaited_once()
        sent = json.loads(mock_ws.send_text.call_args[0][0])
        assert sent == {"event": "test_event", "data": {"stars": 42}}

    @pytest.mark.asyncio
    async def test_broadcast_event_no_subscribers(self):
        manager = ConnectionManager()
        # No subscribers
        await manager.broadcast_event("nonexistent", {})  # Should not raise

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connection(self):
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        mock_ws.send_text.side_effect = Exception("Dead socket")
        conn_id = await manager.connect(mock_ws)
        await manager.subscribe(conn_id, ["event"])

        await manager.broadcast_event("event", {})

        assert conn_id not in manager.active_connections
        assert "event" not in manager.event_subscribers


class TestSubscriptionManager:
    """Test SubscriptionManager with queue and worker."""

    @pytest.fixture
    def mock_service(self):
        service = AsyncMock(spec=GitHubService)
        return service

    @pytest.fixture
    def manager(self, mock_service):
        return SubscriptionManager(service=mock_service)

    @pytest.mark.asyncio
    async def test_emit_event_puts_into_queue(self, manager):
        await manager.emit_event("user1", {"stars": 10})
        assert manager.event_queue.qsize() == 1
        git_url, payload = await manager.event_queue.get()
        assert git_url == "user1"
        assert payload == {"stars": 10}

    @pytest.mark.asyncio
    async def test_worker_processes_event(self, manager):
        # Mock the worker's dependencies
        manager.conn.broadcast_event = AsyncMock()
        manager.webhook_subscriptions = []
        await manager.start_worker()

        await manager.emit_event("user1", {"stars": 20})
        # Give worker a moment
        await asyncio.sleep(0.1)

        manager.conn.broadcast_event.assert_awaited_once_with("user1", {"stars": 20})

    @pytest.mark.asyncio
    async def test_worker_sends_webhooks(self, manager):
        manager.conn.broadcast_event = AsyncMock()
        sub = WebhookSubscription(
            url=HttpUrl("https://example.com/hook"),
            git_urls=["user1"],
            headers={"X-Test": "abc"},
        )
        manager.webhook_subscriptions = [sub]
        manager.send_webhook = AsyncMock()

        await manager.start_worker()
        await manager.emit_event("user1", {"stars": 5})
        await asyncio.sleep(0.1)

        manager.send_webhook.assert_awaited_once_with(sub, "user1", {"stars": 5})

    @pytest.mark.asyncio
    async def test_register_webhook(self, manager):
        sub = WebhookSubscription(
            url=HttpUrl("https://example.com/hook"), git_urls=["test"]
        )
        result = await manager.register_webhook(sub)
        assert result["status"] == "subscribed"
        assert result["id"] == 0
        assert len(manager.webhook_subscriptions) == 1

    @pytest.mark.asyncio
    async def test_send_webhook_success(self, manager):
        sub = WebhookSubscription(
            url=HttpUrl("https://httpbin.org/post"),
            git_urls=["test"],
            headers={"User-Agent": "test"},
        )
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock()
            await manager.send_webhook(sub, "test", {"stars": 100})

            mock_post.assert_awaited_once()
            args = mock_post.call_args
            assert args[0][0] == "https://httpbin.org/post"
            assert args[1]["json"]["event"] == "test"
            assert args[1]["json"]["data"]["stars"] == 100
            assert args[1]["headers"]["User-Agent"] == "test"

    @pytest.mark.asyncio
    async def test_send_webhook_failure_logs_error(self, manager):
        sub = WebhookSubscription(
            url=HttpUrl("https://nonexistent.example.com"), git_urls=["test"]
        )
        with patch("httpx.AsyncClient.post", side_effect=Exception("Network error")):
            await manager.send_webhook(sub, "test", {})
            # Should not raise, just log
            assert True  # No exception
