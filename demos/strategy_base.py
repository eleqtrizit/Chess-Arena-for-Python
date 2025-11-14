#!/usr/bin/env python3
"""
Base class for chess playing strategies.

Developers should inherit from StrategyBase and implement choose_move()
to create their own chess AI.
"""

from abc import ABC, abstractmethod
from typing import List

import chess


class StrategyBase(ABC):
    """
    Abstract base class for chess playing strategies.

    Subclasses must implement choose_move() to define their move selection logic.
    The ChessClient handles all connection and game management, allowing strategy
    implementations to focus purely on move selection.

    :param search_time: Maximum time in seconds for move search
    :type search_time: float
    """

    def __init__(self, search_time: float):
        self.search_time = search_time

    @abstractmethod
    def choose_move(self, board: chess.Board, legal_moves: List[str], player_color: str) -> str:
        """
        Choose the best move for the current position.

        :param board: Current board position (python-chess Board object)
        :type board: chess.Board
        :param legal_moves: List of legal moves in SAN notation (e.g., ["e4", "Nf3"])
        :type legal_moves: List[str]
        :param player_color: Color of the player ("white" or "black")
        :type player_color: str
        :return: Selected move in SAN notation
        :rtype: str
        :raises Exception: If no legal moves available or move selection fails
        """
        pass
