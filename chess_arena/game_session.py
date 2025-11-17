"""Game session manager for tracking active games and disconnections."""

import asyncio
import logging
import time
from typing import Dict, Optional, Set

from chess_arena.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)


class GameSession:
    """
    Tracks connection state for a single game.

    :param game_id: Unique game identifier
    :type game_id: str
    :param player_connections: Mapping of player_id to connection_id
    :type player_connections: Dict[str, str]
    """

    def __init__(self, game_id: str, player_connections: Dict[str, str]):
        self.game_id = game_id
        self.player_connections = player_connections
        self.disconnected_players: Dict[str, float] = {}
        self.forfeit_timeout = 60.0
        self.is_cancelled = False
        self.winner: Optional[str] = None

    def mark_disconnected(self, player_id: str) -> None:
        """
        Mark a player as disconnected and start forfeit timer.

        :param player_id: Player identifier that disconnected
        :type player_id: str
        """
        if player_id not in self.disconnected_players:
            self.disconnected_players[player_id] = time.time()

    def mark_reconnected(self, player_id: str) -> None:
        """
        Mark a player as reconnected and cancel forfeit timer.

        :param player_id: Player identifier that reconnected
        :type player_id: str
        """
        self.disconnected_players.pop(player_id, None)

    def check_forfeit(self) -> Optional[str]:
        """
        Check if any player should forfeit due to disconnect timeout.

        :return: Player ID of winner if forfeit occurred, None otherwise
        :rtype: Optional[str]
        """
        current_time = time.time()

        for player_id, disconnect_time in list(self.disconnected_players.items()):
            if current_time - disconnect_time >= self.forfeit_timeout:
                # This player forfeits
                other_players = [pid for pid in self.player_connections.keys() if pid != player_id]
                if other_players:
                    self.winner = other_players[0]
                    return self.winner

        # Check if all players disconnected
        if len(self.disconnected_players) == len(self.player_connections):
            self.is_cancelled = True
            return "cancelled"

        return None

    def get_connected_players(self) -> Set[str]:
        """
        Get set of currently connected player IDs.

        :return: Set of connected player IDs
        :rtype: Set[str]
        """
        return set(self.player_connections.keys()) - set(self.disconnected_players.keys())

    def is_player_connected(self, player_id: str) -> bool:
        """
        Check if a specific player is connected.

        :param player_id: Player identifier
        :type player_id: str
        :return: True if player is connected
        :rtype: bool
        """
        return player_id not in self.disconnected_players


class GameSessionManager:
    """
    Manages all active game sessions and handles disconnections.

    Tracks which connections belong to which games and monitors
    disconnect timeouts for forfeit logic.
    """

    def __init__(self, connection_manager: ConnectionManager):
        """
        Initialize the game session manager.

        :param connection_manager: Connection manager instance
        :type connection_manager: ConnectionManager
        """
        self.connection_manager = connection_manager
        self.sessions: Dict[str, GameSession] = {}
        self.connection_to_game: Dict[str, str] = {}
        self.lock = asyncio.Lock()

    async def create_session(self, game_id: str, player_connections: Dict[str, str]) -> GameSession:
        """
        Create a new game session.

        :param game_id: Unique game identifier
        :type game_id: str
        :param player_connections: Mapping of player_id to connection_id
        :type player_connections: Dict[str, str]
        :return: Created game session
        :rtype: GameSession
        """
        logger.debug(f"[GameSession:{game_id}] Creating session with player connections: {player_connections}")
        async with self.lock:
            session = GameSession(game_id, player_connections)
            self.sessions[game_id] = session
            logger.debug(f"[GameSession:{game_id}] Session created and stored")

            # Track reverse mapping
            for connection_id in player_connections.values():
                self.connection_to_game[connection_id] = game_id
                logger.debug(f"[GameSession:{game_id}] Connection {connection_id} mapped to game")

            logger.debug(f"[GameSession:{game_id}] Session creation completed")
            return session

    async def handle_disconnect(self, connection_id: str) -> Optional[Dict[str, Optional[str]]]:
        """
        Handle a connection disconnect and check for forfeit.

        :param connection_id: Connection identifier that disconnected
        :type connection_id: str
        :return: Dict with game_id, player_id, and status if forfeit/cancel occurred
        :rtype: Optional[Dict[str, Optional[str]]]
        """
        logger.debug(f"[GameSession] Handling disconnect for connection {connection_id}")
        async with self.lock:
            game_id = self.connection_to_game.get(connection_id)
            if not game_id:
                logger.debug(f"[GameSession] No game found for connection {connection_id}")
                return None

            logger.debug(f"[GameSession:{game_id}] Found game for connection {connection_id}")
            session = self.sessions.get(game_id)
            if not session:
                logger.debug(f"[GameSession:{game_id}] No session found")
                return None

            # Find which player disconnected
            player_id = None
            for pid, cid in session.player_connections.items():
                if cid == connection_id:
                    player_id = pid
                    break

            if not player_id:
                logger.debug(f"[GameSession:{game_id}] No player found for connection {connection_id}")
                return None

            logger.debug(f"[GameSession:{game_id}] Player {player_id} disconnected from connection {connection_id}")
            # Mark player as disconnected
            session.mark_disconnected(player_id)

            # Check for immediate forfeit/cancel
            logger.debug(f"[GameSession:{game_id}] Checking for forfeit")
            result = session.check_forfeit()
            if result:
                logger.debug(f"[GameSession:{game_id}] Forfeit detected: {result}")
                return {
                    "game_id": game_id,
                    "disconnected_player_id": player_id,
                    "status": "cancelled" if result == "cancelled" else "forfeit",
                    "winner": result if result != "cancelled" else None
                }

            logger.debug(f"[GameSession:{game_id}] Player marked as disconnected, no immediate forfeit")
            return {
                "game_id": game_id,
                "disconnected_player_id": player_id,
                "status": "disconnected"
            }

    async def handle_reconnect(self, connection_id: str, game_id: str, player_id: str) -> bool:
        """
        Handle a player reconnection.

        :param connection_id: New connection identifier
        :type connection_id: str
        :param game_id: Game identifier
        :type game_id: str
        :param player_id: Player identifier
        :type player_id: str
        :return: True if reconnection successful
        :rtype: bool
        """
        async with self.lock:
            session = self.sessions.get(game_id)
            if not session:
                return False

            # Update connection mapping
            old_connection = session.player_connections.get(player_id)
            if old_connection:
                self.connection_to_game.pop(old_connection, None)

            session.player_connections[player_id] = connection_id
            self.connection_to_game[connection_id] = game_id

            # Mark as reconnected
            session.mark_reconnected(player_id)

            return True

    async def check_session_forfeits(self) -> list[Dict[str, Optional[str]]]:
        """
        Check all sessions for forfeit timeouts.

        :return: List of forfeit/cancel events
        :rtype: list[Dict[str, Optional[str]]]
        """
        forfeits = []

        async with self.lock:
            for game_id, session in list(self.sessions.items()):
                result = session.check_forfeit()
                if result:
                    forfeits.append({
                        "game_id": game_id,
                        "status": "cancelled" if result == "cancelled" else "forfeit",
                        "winner": result if result != "cancelled" else None
                    })

        return forfeits

    def get_session(self, game_id: str) -> Optional[GameSession]:
        """
        Get a game session by ID.

        :param game_id: Game identifier
        :type game_id: str
        :return: Game session if found
        :rtype: Optional[GameSession]
        """
        return self.sessions.get(game_id)

    async def remove_session(self, game_id: str) -> None:
        """
        Remove a game session.

        :param game_id: Game identifier
        :type game_id: str
        """
        logger.debug(f"[GameSession:{game_id}] Removing session")
        async with self.lock:
            session = self.sessions.pop(game_id, None)
            if session:
                logger.debug(f"[GameSession:{game_id}] Session found, removing connection mappings")
                for connection_id in session.player_connections.values():
                    self.connection_to_game.pop(connection_id, None)
                    logger.debug(f"[GameSession:{game_id}] Removed connection {connection_id} mapping")
                logger.debug(f"[GameSession:{game_id}] Session removed successfully")
            else:
                logger.debug(f"[GameSession:{game_id}] No session found to remove")
