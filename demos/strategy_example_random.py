#!/usr/bin/env python3
"""
Example: Random Move Strategy

This is a simple demonstration strategy that randomly selects moves.
It serves as a minimal working example for developers learning to create
their own chess AI strategies.

WARNING: This strategy has no chess logic - it's purely for demonstration!
"""

import random
from typing import List

import chess
from strategy_base import StrategyBase


class RandomStrategy(StrategyBase):
    """
    A naive strategy that randomly selects from available legal moves.

    This implementation demonstrates the minimum requirements for a Strategy:
    1. Inherit from StrategyBase
    2. Implement the choose_move() method
    3. Return a valid move in SAN notation

    The strategy intentionally ignores the board position, player color, and
    search_time parameter - it simply picks a random legal move instantly.

    :param search_time: Maximum time for move search (unused in this example)
    :type search_time: float
    """

    def choose_move(self, board: chess.Board, legal_moves: List[str], player_color: str) -> str:
        """
        Randomly select one move from the list of legal moves.

        This method receives three pieces of information:
        - board: The current chess position (unused in this naive example)
        - legal_moves: All valid moves we can make (e.g., ["e4", "Nf3", "d4"])
        - player_color: Whether we're playing "white" or "black" (unused here)

        The python-chess library has already validated these moves, so we can
        safely pick any of them without additional checking.

        :param board: Current board position (ignored in this simple example)
        :type board: chess.Board
        :param legal_moves: Pre-validated list of legal moves in SAN notation
        :type legal_moves: List[str]
        :param player_color: Our assigned color, "white" or "black" (ignored here)
        :type player_color: str
        :return: One randomly selected move from legal_moves
        :rtype: str
        :raises Exception: If legal_moves is empty (should never happen in practice)
        """
        # Safety check: Ensure we have at least one legal move
        # In a real game, this should never be empty unless the game is over
        if not legal_moves:
            raise Exception("No legal moves available - game should be over!")

        # Use Python's random.choice() to pick one move from the list
        # This gives equal probability to every move (uniform distribution)
        selected_move = random.choice(legal_moves)

        # Optional: Print what we chose (useful for debugging/learning)
        print(f"RandomStrategy selected: {selected_move} from {len(legal_moves)} options")

        # Return the move in SAN notation (e.g., "e4", "Nf3", "O-O")
        # The ChessClient will send this to the server
        return selected_move
