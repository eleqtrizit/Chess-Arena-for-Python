"""Matchmaking queue for chess games."""

import asyncio
import random
import uuid
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class PlayerMatchResult:
    """
    Match result from a specific player's perspective.

    :param game_id: Unique identifier for the created game
    :type game_id: str
    :param player_id: This player's unique identifier
    :type player_id: str
    :param assigned_color: Color assigned to this player ('white' or 'black')
    :type assigned_color: str
    :param first_move: Player ID of the player who moves first (white)
    :type first_move: str
    :param player_mappings: Full mapping of all player_ids to colors
    :type player_mappings: Dict[str, str]
    """

    game_id: str
    player_id: str
    assigned_color: str
    first_move: str
    player_mappings: Dict[str, str]


class MatchmakingQueue:
    """
    Manages matchmaking queue for chess games.

    Pairs waiting players and creates games with randomly assigned colors.
    """

    def __init__(self) -> None:
        """Initialize the matchmaking queue."""
        self.waiting_player: Optional[asyncio.Future] = None
        self.lock = asyncio.Lock()

    async def join_queue(self, timeout: float = 60.0) -> Optional[PlayerMatchResult]:
        """
        Join the matchmaking queue and wait for an opponent.

        :param timeout: Maximum time to wait in seconds
        :type timeout: float
        :return: PlayerMatchResult if matched with player-specific info, None if timeout occurred
        :rtype: Optional[PlayerMatchResult]
        """
        future: Optional[asyncio.Future] = None

        async with self.lock:
            if self.waiting_player is None:
                # First player - create future and wait
                self.waiting_player = asyncio.Future()
                future = self.waiting_player
            elif self.waiting_player and not self.waiting_player.done():
                # Second player - create match and notify both players with their specific info
                player1_result, player2_result = self._create_match()

                # Notify waiting player with their result
                self.waiting_player.set_result(player1_result)
                self.waiting_player = None

                # Return result for second player
                return player2_result
            else:
                # Race condition - waiting player left, become waiting player
                self.waiting_player = asyncio.Future()
                future = self.waiting_player

        # Wait for another player
        if future:
            try:
                result = await asyncio.wait_for(future, timeout=timeout)
                return result
            except asyncio.TimeoutError:
                async with self.lock:
                    if self.waiting_player is future:
                        self.waiting_player = None
                return None

        return None

    def _create_match(self) -> tuple[PlayerMatchResult, PlayerMatchResult]:
        """
        Create a new match between two players.

        :return: Tuple of (player1_result, player2_result) with each player's specific info
        :rtype: tuple[PlayerMatchResult, PlayerMatchResult]
        """
        game_id = str(uuid.uuid4())
        player1_id = str(uuid.uuid4())
        player2_id = str(uuid.uuid4())

        # Randomly assign colors
        colors = ['white', 'black']
        random.shuffle(colors)

        player_mappings = {
            player1_id: colors[0],
            player2_id: colors[1]
        }

        # First move is always white
        first_move = player1_id if colors[0] == 'white' else player2_id

        player1_result = PlayerMatchResult(
            game_id=game_id,
            player_id=player1_id,
            assigned_color=colors[0],
            first_move=first_move,
            player_mappings=player_mappings
        )

        player2_result = PlayerMatchResult(
            game_id=game_id,
            player_id=player2_id,
            assigned_color=colors[1],
            first_move=first_move,
            player_mappings=player_mappings
        )

        return player1_result, player2_result
