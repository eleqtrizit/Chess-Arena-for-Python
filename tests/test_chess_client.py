#!/usr/bin/env python3
"""
Tests for the standalone chess client demo.

Since this is a demo/example file that integrates with the server,
we test the core logic components rather than full integration.
"""

import importlib.util
import sys
from pathlib import Path

# Add demos directory to path and import chess_client dynamically
demos_path = Path(__file__).parent.parent / 'demos'
chess_client_path = demos_path / 'chess_client.py'
strategy_base_path = demos_path / 'strategy_base.py'
strategy_path = demos_path / 'strategy.py'

# Load strategy_base first (dependency of strategy)
strategy_base_spec = importlib.util.spec_from_file_location("strategy_base", strategy_base_path)
strategy_base_module = importlib.util.module_from_spec(strategy_base_spec)
sys.modules['strategy_base'] = strategy_base_module
strategy_base_spec.loader.exec_module(strategy_base_module)

# Load strategy
strategy_spec = importlib.util.spec_from_file_location("strategy", strategy_path)
strategy_module = importlib.util.module_from_spec(strategy_spec)
sys.modules['strategy'] = strategy_module
strategy_spec.loader.exec_module(strategy_module)

# Load chess_client
spec = importlib.util.spec_from_file_location("chess_client", chess_client_path)
chess_client_module = importlib.util.module_from_spec(spec)
sys.modules['chess_client'] = chess_client_module  # Add to sys.modules for patch decorator
spec.loader.exec_module(chess_client_module)

ChessClient = chess_client_module.ChessClient
Strategy = strategy_module.Strategy


class TestChessClient:
    """Test suite for ChessClient demo."""

    def test_client_initialization(self):
        """
        Test client initializes with correct parameters.

        :raises AssertionError: If initialization fails
        """
        strategy = Strategy(search_time=5.0)
        client = ChessClient("http://localhost:9002", strategy)
        assert client.server_url == "ws://localhost:9002"  # HTTP converted to WebSocket
        assert client.player_color is None  # Set by server after joining queue
        assert client.player_id is None  # Set by server after joining queue
        assert client.strategy.search_time == 5.0

    def test_client_with_strategy_dependency(self):
        """
        Test client properly uses injected strategy.

        :raises AssertionError: If strategy is not properly injected
        """
        strategy = Strategy(search_time=3.0)
        client = ChessClient("http://localhost:9002", strategy)
        assert client.strategy is strategy
        assert client.strategy.search_time == 3.0
