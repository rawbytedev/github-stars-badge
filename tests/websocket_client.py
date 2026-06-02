import json
import asyncio
import websockets


async def test_client(subscribe_events: list):
    """
    client test - Ensure a client can connect
    """
    uri = "ws://localhost:8000/ws"
    try:
        async with websockets.connect(uri) as websocket:
            print(f"Connected to {uri}")

            # Subscribe to events
            subscribe_msg = {"action": "subscribe", "events": subscribe_events}
            await websocket.send(json.dumps(subscribe_msg))
            print(f"Sent subscription: {subscribe_events}")

            # Wait for subscription confirmation
            response = await websocket.recv()
            print(f"Server response: {response!r}")

            # Listen for incoming events forever
            print("Listening for events... (Press Ctrl+C to stop)")
            while True:
                msg = await websocket.recv()
                data = json.loads(msg)
                print(f"Received event: {data['event']} -> {data['data']}")
    except websockets.exceptions.ConnectionClosed:
        print("Connection closed by server")
    except KeyboardInterrupt:
        print("\nClient stopped")


asyncio.run(test_client(["rawbytedev:zerokv", "rawbytedev"]))
