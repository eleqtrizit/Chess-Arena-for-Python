#!/usr/bin/env python3
"""
Tests for StrategyBase abstract class.
"""

from typing import List

import chess
import pytest

from demos.strategy_base import StrategyBase


class DummyStrategy(StrategyBase):
    """
    Concrete test implementation of StrategyBase that always returns the first legal move.

    :param search_time: Maximum time in seconds for move search
    :type search_time: float
    """

    def choose_move(self, board: chess.Board, legal_moves: List[str], player_color: str) -> str:
        """
        Choose the first legal move (dummy implementation for testing).

        :param board: Current board position
        :type board: chess.Board
        :param legal_moves: List of legal moves in SAN notation
        :type legal_moves: List[str]
        :param player_color: Color of the player ("white" or "black")
        :type player_color: str
        :return: First legal move
        :rtype: str
        :raises Exception: If no legal moves available
        """
        if not legal_moves:
            raise Exception("No legal moves available")
        return legal_moves[0]


def test_strategy_base_abstract() -> None:
    """
    Test that StrategyBase cannot be instantiated directly.

    :raises TypeError: When attempting to instantiate abstract class
    """
    with pytest.raises(TypeError):
        StrategyBase(search_time=5.0)  # type: ignore


def test_dummy_strategy_initialization() -> None:
    """
    Test that concrete strategy can be instantiated.
    """
    strategy = DummyStrategy(search_time=5.0)
    assert strategy.search_time == 5.0


def test_dummy_strategy_choose_move() -> None:
    """
    Test that dummy strategy returns first legal move.
    """
    strategy = DummyStrategy(search_time=5.0)
    board = chess.Board()
    legal_moves = [board.san(m) for m in board.legal_moves]

    chosen_move = strategy.choose_move(board, legal_moves, "white")
    assert chosen_move in legal_moves


def test_dummy_strategy_no_legal_moves() -> None:
    """
    Test that strategy raises exception when no legal moves available.

    :raises Exception: When no legal moves provided
    """
    strategy = DummyStrategy(search_time=5.0)
    board = chess.Board()

    with pytest.raises(Exception, match="No legal moves available"):
        strategy.choose_move(board, [], "white")


def test_strategy_interface_with_black() -> None:
    """
    Test that strategy works for black player.
    """
    strategy = DummyStrategy(search_time=3.0)
    board = chess.Board()
    board.push_san("e4")  # White moves first
    legal_moves = [board.san(m) for m in board.legal_moves]

    chosen_move = strategy.choose_move(board, legal_moves, "black")
    assert chosen_move in legal_moves
