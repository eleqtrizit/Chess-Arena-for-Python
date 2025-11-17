"""WebSocket connection manager for chess games."""

import asyncio
import secrets
import uuid
from typing import Any, Dict, Optional

from fastapi import WebSocket


class ConnectionManager:
    """
    Manages WebSocket connections for chess games.

    Tracks active connections and handles message broadcasting.
    """

    def __init__(self) -> None:
        """Initialize the connection manager."""
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        self.auth_tokens: Dict[str, Dict[str, str]] = {}  # game_id -> {player_id: auth_token}
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> str:
        """
        Accept and register a new WebSocket connection.

        :param websocket: WebSocket instance to register
        :type websocket: WebSocket
        :return: Unique connection ID
        :rtype: str
        """
        await websocket.accept()
        connection_id = str(uuid.uuid4())

        async with self.lock:
            self.active_connections[connection_id] = websocket
            self.connection_metadata[connection_id] = {
                "connected_at": asyncio.get_event_loop().time(),
                "game_id": None,
                "player_id": None
            }

        return connection_id

    async def disconnect(self, connection_id: str) -> None:
        """
        Unregister a WebSocket connection.

        :param connection_id: Connection identifier to remove
        :type connection_id: str
        """
        async with self.lock:
            self.active_connections.pop(connection_id, None)
            self.connection_metadata.pop(connection_id, None)

    async def send_message(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """
        Send a message to a specific connection.

        :param connection_id: Target connection ID
        :type connection_id: str
        :param message: Message dictionary to send
        :type message: Dict[str, Any]
        :return: True if sent successfully, False if connection not found
        :rtype: bool
        """
        websocket = self.active_connections.get(connection_id)
        if websocket is None:
            return False

        try:
            await websocket.send_json(message)
            return True
        except Exception:
            # Connection is broken, remove it
            await self.disconnect(connection_id)
            return False

    async def send_to_game(
        self, game_id: str, message: Dict[str, Any], exclude_connection: Optional[str] = None
    ) -> None:
        """
        Send a message to all connections in a specific game.

        :param game_id: Game identifier
        :type game_id: str
        :param message: Message dictionary to broadcast
        :type message: Dict[str, Any]
        :param exclude_connection: Optional connection ID to exclude from broadcast
        :type exclude_connection: Optional[str]
        """
        async with self.lock:
            connections_to_notify = [
                conn_id for conn_id, metadata in self.connection_metadata.items()
                if metadata.get("game_id") == game_id and conn_id != exclude_connection
            ]

        for conn_id in connections_to_notify:
            await self.send_message(conn_id, message)

    def set_game_info(self, connection_id: str, game_id: str, player_id: str) -> None:
        """
        Associate a connection with a game and player.

        :param connection_id: Connection identifier
        :type connection_id: str
        :param game_id: Game identifier
        :type game_id: str
        :param player_id: Player identifier
        :type player_id: str
        """
        metadata = self.connection_metadata.get(connection_id)
        if metadata:
            metadata["game_id"] = game_id
            metadata["player_id"] = player_id

    def get_game_connections(self, game_id: str) -> Dict[str, str]:
        """
        Get all connection IDs and their player IDs for a specific game.

        :param game_id: Game identifier
        :type game_id: str
        :return: Dictionary mapping connection_id to player_id
        :rtype: Dict[str, str]
        """
        return {
            conn_id: metadata["player_id"]
            for conn_id, metadata in self.connection_metadata.items()
            if metadata.get("game_id") == game_id and metadata.get("player_id")
        }

    def is_connected(self, connection_id: str) -> bool:
        """
        Check if a connection is still active.

        :param connection_id: Connection identifier
        :type connection_id: str
        :return: True if connection is active
        :rtype: bool
        """
        return connection_id in self.active_connections

    def generate_auth_token(self, game_id: str, player_id: str) -> str:
        """
        Generate and store an auth token for a player in a game.

        :param game_id: Game identifier
        :type game_id: str
        :param player_id: Player identifier
        :type player_id: str
        :return: Generated auth token
        :rtype: str
        """
        auth_token = secrets.token_urlsafe(32)
        if game_id not in self.auth_tokens:
            self.auth_tokens[game_id] = {}
        self.auth_tokens[game_id][player_id] = auth_token
        return auth_token

    def validate_auth_token(self, game_id: str, player_id: str, auth_token: str) -> bool:
        """
        Validate an auth token for a player in a game.

        :param game_id: Game identifier
        :type game_id: str
        :param player_id: Player identifier
        :type player_id: str
        :param auth_token: Auth token to validate
        :type auth_token: str
        :return: True if token is valid
        :rtype: bool
        """
        game_tokens = self.auth_tokens.get(game_id, {})
        return game_tokens.get(player_id) == auth_token

    async def health_check_connection(self, connection_id: str) -> bool:
        """
        Perform a health check on a connection by sending a ping and checking if it's still active.

        :param connection_id: Connection identifier to check
        :type connection_id: str
        :return: True if connection is healthy and responsive, False otherwise
        :rtype: bool
        """
        websocket = self.active_connections.get(connection_id)
        if websocket is None:
            return False

        try:
            # Send ping message to test responsiveness
            await websocket.send_json({"type": "ping"})

            # Check if connection is still active
            # In a real implementation, we would wait for a pong response
            # But for now, we'll just check if the connection is still registered
            return self.is_connected(connection_id)
        except Exception:
            # Connection is broken
            await self.disconnect(connection_id)
            return False
