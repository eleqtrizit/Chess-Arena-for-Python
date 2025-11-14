#!/usr/bin/env python3
"""
Tests for the RandomStrategy example.
"""

import importlib.util
import sys
from pathlib import Path

import chess
import pytest

# Add demos directory to path and import dynamically
demos_path = Path(__file__).parent.parent / "demos"
strategy_base_path = demos_path / "strategy_base.py"
strategy_example_random_path = demos_path / "strategy_example_random.py"

# Load strategy_base first (dependency)
strategy_base_spec = importlib.util.spec_from_file_location("strategy_base", strategy_base_path)
strategy_base_module = importlib.util.module_from_spec(strategy_base_spec)
sys.modules["strategy_base"] = strategy_base_module
strategy_base_spec.loader.exec_module(strategy_base_module)

# Load strategy_example_random
spec = importlib.util.spec_from_file_location("strategy_example_random", strategy_example_random_path)
strategy_example_random_module = importlib.util.module_from_spec(spec)
sys.modules["strategy_example_random"] = strategy_example_random_module
spec.loader.exec_module(strategy_example_random_module)

RandomStrategy = strategy_example_random_module.Strategy


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
