"""
Web Connections module for websocket and Webhooks
"""
import json
from typing import Dict, List, Set
import uuid
from fastapi import APIRouter, BackgroundTasks, WebSocket
import httpx
from .models import WebhookSubscription

class ConnectionManager:
    """The Main connection Handler for websocket, Handles the complete lifecycle of websockets"""
    def __init__(self):
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



router = APIRouter()
webhook_subscriptions:  List[WebhookSubscription]= []

@router.post("/webhook/subscribe")
async def register_webhook(sub: WebhookSubscription):
    """Webhook endpoint for subscription"""
    webhook_subscriptions.append(sub)
    return {"status": "subscribed", "id": len(webhook_subscriptions)-1}

## Leave for now as it comes in handy for testing / Planned to be removed
@router.get("/webhook/subscriptions")
async def list_webhooks():
    """Debug endpoint"""
    return webhook_subscriptions


async def emit_event(git_url: str, payload: dict,
                     manager: ConnectionManager,
                     background_tasks: BackgroundTasks):
    """A helper that boardcast_events to both websocket and webhooks"""
    # 1. WebSockets
    background_tasks.add_task(manager.broadcast_event, git_url, payload)
    # 2. Webhooks (fire and forget with background task)
    for sub in webhook_subscriptions:
        if git_url in sub.git_urls:
            background_tasks.add_task(send_webhook, sub, git_url, payload)

async def send_webhook(sub: WebhookSubscription, git_url: str, payload: dict):
    """Boardcast to webhooks"""
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                sub.url.unicode_string(),
                json={"event": git_url, "data": payload, "timestamp": ...},
                headers=sub.headers,
                timeout=5
            )
        except httpx.ConnectError as e:
            print(f"{e}")
        except Exception as e:
            # Log error and maybe store for retry queue
            # log for now // Might have to add proper logging
            print(f"{e}")

async def periodic_scan():
    pass
