#!/usr/bin/env python3
"""
Tests for the RandomStrategy example.
"""

import sys
from pathlib import Path

import chess
import pytest
from strategy_example_random import RandomStrategy

# Add demos directory to path for imports
demos_path = Path(__file__).parent.parent / "demos"
sys.path.insert(0, str(demos_path))


class TestRandomStrategy:
    """Test suite for RandomStrategy example."""

    def test_init(self):
        """Test that RandomStrategy initializes with search_time."""
        strategy = RandomStrategy(search_time=5.0)
        assert strategy.search_time == 5.0

    def test_choose_move_returns_legal_move(self):
        """Test that choose_move returns one of the legal moves."""
        strategy = RandomStrategy(search_time=1.0)
        board = chess.Board()
        legal_moves = ["e4", "d4", "Nf3", "c4"]
        player_color = "white"

        chosen_move = strategy.choose_move(board, legal_moves, player_color)

        assert chosen_move in legal_moves

    def test_choose_move_with_single_option(self):
        """Test that choose_move works when only one legal move exists."""
        strategy = RandomStrategy(search_time=1.0)
        board = chess.Board()
        legal_moves = ["e4"]
        player_color = "white"

        chosen_move = strategy.choose_move(board, legal_moves, player_color)

        assert chosen_move == "e4"

    def test_choose_move_raises_on_empty_moves(self):
        """Test that choose_move raises exception when no legal moves provided."""
        strategy = RandomStrategy(search_time=1.0)
        board = chess.Board()
        legal_moves = []
        player_color = "white"

        with pytest.raises(Exception, match="No legal moves available"):
            strategy.choose_move(board, legal_moves, player_color)

    def test_choose_move_distribution(self):
        """Test that different moves are selected over multiple calls."""
        strategy = RandomStrategy(search_time=1.0)
        board = chess.Board()
        legal_moves = ["e4", "d4", "Nf3", "c4", "e3"]
        player_color = "white"

        # Run 50 times and collect results
        results = set()
        for _ in range(50):
            chosen_move = strategy.choose_move(board, legal_moves, player_color)
            results.add(chosen_move)

        # With 50 iterations and 5 options, we should see multiple different moves
        # (statistically very unlikely to only see 1 move)
        assert len(results) > 1
