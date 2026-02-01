"""WebSocket connection manager for real-time chat and progress updates."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections for real-time communication.

    Supports:
    - Multiple concurrent connections per session
    - Broadcasting to all connections
    - Sending to specific sessions
    - Progress updates during generation
    """

    def __init__(self):
        # Map session_id -> list of WebSocket connections
        self.active_connections: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()

        async with self._lock:
            if session_id not in self.active_connections:
                self.active_connections[session_id] = []
            self.active_connections[session_id].append(websocket)

        logger.info(f"WebSocket connected: session={session_id}")

    async def disconnect(self, websocket: WebSocket, session_id: str) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            if session_id in self.active_connections:
                try:
                    self.active_connections[session_id].remove(websocket)
                    if not self.active_connections[session_id]:
                        del self.active_connections[session_id]
                except ValueError:
                    pass

        logger.info(f"WebSocket disconnected: session={session_id}")

    async def send_to_session(self, session_id: str, message: dict[str, Any]) -> None:
        """Send a message to all connections in a session."""
        async with self._lock:
            connections = self.active_connections.get(session_id, [])

        if not connections:
            logger.warning(f"No connections for session: {session_id}")
            return

        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.now().isoformat()

        json_message = json.dumps(message)

        # Send to all connections in session
        disconnected = []
        for websocket in connections:
            try:
                await websocket.send_text(json_message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.append(websocket)

        # Clean up disconnected
        for ws in disconnected:
            await self.disconnect(ws, session_id)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast a message to all connected sessions."""
        async with self._lock:
            all_sessions = list(self.active_connections.keys())

        for session_id in all_sessions:
            await self.send_to_session(session_id, message)

    async def send_chat_message(
        self,
        session_id: str,
        role: str,
        content: str,
        plan: dict | None = None,
    ) -> None:
        """Send a chat message to a session."""
        await self.send_to_session(
            session_id,
            {
                "type": "chat",
                "data": {
                    "role": role,
                    "content": content,
                    "plan": plan,
                },
            },
        )

    async def send_progress(
        self,
        session_id: str,
        plan_id: str,
        item_id: str,
        status: str,
        progress: int,
        message: str | None = None,
    ) -> None:
        """Send generation progress update."""
        await self.send_to_session(
            session_id,
            {
                "type": "progress",
                "data": {
                    "plan_id": plan_id,
                    "item_id": item_id,
                    "status": status,
                    "progress": progress,
                    "message": message,
                },
            },
        )

    async def send_error(self, session_id: str, error: str) -> None:
        """Send an error message to a session."""
        await self.send_to_session(
            session_id,
            {
                "type": "error",
                "data": {"message": error},
            },
        )

    def get_active_sessions(self) -> list[str]:
        """Get list of active session IDs."""
        return list(self.active_connections.keys())

    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return sum(len(conns) for conns in self.active_connections.values())


# Global connection manager instance
manager = ConnectionManager()
