"""
Web Connections module for websocket and Webhooks
"""

import asyncio
import json
from typing import Dict, List, Optional, Set
import uuid
import time
from fastapi import WebSocket
from fastapi.logger import logger
import httpx

from .services import GitHubService
from .models import StarsRequests, WebhookSubscription


class ConnectionManager:
    """The Main connection Handler for websocket, Handles the complete lifecycle of websockets"""

    def __init__(self) -> None:
        # active connections: id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        # event name -> set of connection ids
        self.event_subscribers: Dict[str, Set[str]] = {}
        # connection id -> set of event names it subscribed to
        self.conn_subscriptions: Dict[str, Set[str]] = {}

    async def connect(self, websocket: WebSocket) -> str:
        """Add a websocket to Connection manager"""
        await websocket.accept()
        conn_id = str(uuid.uuid4())
        self.active_connections[conn_id] = websocket
        self.conn_subscriptions[conn_id] = set()
        return conn_id

    def disconnect(self, conn_id: str):
        """remove a websocket from Connection manager, the websocket won't receive anymore events"""
        # remove from all event subscriptions
        if conn_id in self.conn_subscriptions:
            for event in self.conn_subscriptions[conn_id]:
                if event in self.event_subscribers:
                    self.event_subscribers[event].discard(conn_id)
                    if not self.event_subscribers[event]:
                        del self.event_subscribers[event]
            del self.conn_subscriptions[conn_id]
        # delete the websocket reference
        if conn_id in self.active_connections:
            del self.active_connections[conn_id]

    async def subscribe(self, conn_id: str, git_urls: list):
        """
        Subcribe a websocket to specific events
        Map websocket to events
        """
        if conn_id not in self.conn_subscriptions:
            return
        for event in git_urls:
            # add to event -> subscribers mapping
            if event not in self.event_subscribers:
                self.event_subscribers[event] = set()
            self.event_subscribers[event].add(conn_id)
            # add to connection -> subscriptions mapping
            self.conn_subscriptions[conn_id].add(event)

    async def unsubscribe(self, conn_id: str, git_urls: list):
        """
        Unsubscribe webscoket from specific events
        """
        if conn_id not in self.conn_subscriptions:
            return
        for event in git_urls:
            if event in self.event_subscribers:
                self.event_subscribers[event].discard(conn_id)
                if not self.event_subscribers[event]:
                    del self.event_subscribers[event]
            self.conn_subscriptions[conn_id].discard(event)

    async def broadcast_event(self, event: str, data: dict):
        """Send an event to all subscribers of that event type."""
        if event not in self.event_subscribers:
            return  # no subscribers
        message = json.dumps({"event": event, "data": data})
        dead_connections = []
        for conn_id in self.event_subscribers[event]:
            ws = self.active_connections.get(conn_id)
            if not ws:
                dead_connections.append(conn_id)
                continue
            try:
                await ws.send_text(message)
            except Exception:
                dead_connections.append(conn_id)
        # clean up dead connections
        for conn_id in dead_connections:
            self.disconnect(conn_id)


class SubscriptionManager:
    """
    This is the Main Manager for webhook and websocket
    It handle the complete lifecycle for webhooks and websocket
    """

    def __init__(
        self, service: GitHubService, conn: Optional[ConnectionManager] = None
    ):
        self.conn: ConnectionManager = conn or ConnectionManager()
        self.watch_list: List[StarsRequests] = []
        self.webhook_subscriptions: List[WebhookSubscription] = []
        self.service = service
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.worker_task = None

    async def start_worker(self):
        """Start a background worker that processes events from the queue."""
        self.worker_task = asyncio.create_task(self._process_events())

    async def _process_events(self):
        while True:
            git_url, payload = await self.event_queue.get()
            try:
                # WebSocket broadcast
                await self.conn.broadcast_event(git_url, payload)
                # Webhooks
                for sub in self.webhook_subscriptions:
                    if git_url in sub.git_urls:
                        await self.send_webhook(sub, git_url, payload)
            except Exception as e:
                logger.error("Failed to process event %s: %s", git_url, e)
            finally:
                self.event_queue.task_done()

    async def register_webhook(self, sub: WebhookSubscription):
        """Webhook endpoint for subscription"""
        self.webhook_subscriptions.append(sub)
        return {"status": "subscribed", "id": len(self.webhook_subscriptions) - 1}

    ## to remove
    async def list_webhooks(self):
        """Debug endpoint"""
        return self.webhook_subscriptions

    async def emit_event(self, git_url: str, payload: dict):
        """Put event into queue for processing (non-blocking)."""
        await self.event_queue.put((git_url, payload))

    async def send_webhook(self, sub: WebhookSubscription, git_url: str, payload: dict):
        """Boardcast to webhooks"""
        async with httpx.AsyncClient() as client:
            try:
                await client.post(
                    sub.url.unicode_string(),
                    json={"event": git_url, "data": payload, "timestamp": time.time()},
                    headers=sub.headers,
                    timeout=5,
                )
            except httpx.ConnectError as e:
                logger.error("%s", e)
            except Exception as e:
                logger.error("%s", e)

    async def periodic_scan(self, time_ms: float):
        """
        Periodically query active subscrition urls
        Not implemented yet
        """
        while True:
            await asyncio.sleep(time_ms)
            for url in self.watch_list:
                star = await self._refresh(url.owner, url.repo, url.exclude_fork)
                if url.stars != star:
                    url.stars = star
                    await self.emit_event(f"{url.owner}:{url.repo}", {"stars": star})

    async def _refresh(self, owner: str, repo: Optional[str], exclude_fork=False):
        return await self.service.fetch_star_count(owner, repo, exclude_fork)
