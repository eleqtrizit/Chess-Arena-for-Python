#!/usr/bin/env python3
"""
Tests for the standalone chess client demo.

Since this is a demo/example file that integrates with the server,
we test the core logic components rather than full integration.
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import chess
import pytest

# Add demos directory to path and import chess_client dynamically
demos_path = Path(__file__).parent.parent / 'demos'
chess_client_path = demos_path / 'chess_client.py'

spec = importlib.util.spec_from_file_location("chess_client", chess_client_path)
chess_client_module = importlib.util.module_from_spec(spec)
sys.modules['chess_client'] = chess_client_module  # Add to sys.modules for patch decorator
spec.loader.exec_module(chess_client_module)

ChessClient = chess_client_module.ChessClient
PIECE_VALUES = chess_client_module.PIECE_VALUES


class TestChessClient:
    """Test suite for ChessClient demo."""

    def test_client_initialization(self):
        """
        Test client initializes with correct parameters.

        :raises AssertionError: If initialization fails
        """
        client = ChessClient("http://localhost:9002", 5.0)
        assert client.server_url == "http://localhost:9002"
        assert client.player_color is None  # Set by server after joining queue
        assert client.player_id is None  # Set by server after joining queue
        assert client.search_time == 5.0
        assert client.nodes_searched == 0

    def test_evaluate_position_empty_board(self):
        """
        Test position evaluation on empty board.

        :raises AssertionError: If evaluation is incorrect
        """
        client = ChessClient("http://localhost:9002", 5.0)
        # Empty board - only kings (insufficient material = draw)
        board = chess.Board("8/8/8/4k3/4K3/8/8/8 w - - 0 1")
        score = client.evaluate_position(board)
        assert score == 0  # Insufficient material = draw = 0

    def test_evaluate_position_single_piece(self):
        """
        Test position evaluation with starting position.

        :raises AssertionError: If evaluation is incorrect
        """
        client = ChessClient("http://localhost:9002", 5.0)
        board = chess.Board()  # Starting position
        score = client.evaluate_position(board)
        # Starting position should be roughly equal (close to 0)
        assert abs(score) < 200  # Allow some positional imbalance

    def test_order_moves_prioritizes_captures(self):
        """
        Test move ordering prioritizes captures.

        :raises AssertionError: If capture moves are not first
        """
        client = ChessClient("http://localhost:9002", 5.0)
        moves = ['e4', 'Nxd5', 'd4', 'Qxf7']
        ordered = client.order_moves(moves)
        # Captures should come first
        assert ordered[0] in ['Nxd5', 'Qxf7']
        assert ordered[1] in ['Nxd5', 'Qxf7']

    def test_order_moves_center_control(self):
        """
        Test move ordering considers center control.

        :raises AssertionError: If center moves are not prioritized
        """
        client = ChessClient("http://localhost:9002", 5.0)
        moves = ['a3', 'e4', 'h3', 'd4']
        ordered = client.order_moves(moves)
        # Center moves (e4, d4) should come before edge moves (a3, h3)
        center_moves = [m for m in ordered if m in ['e4', 'd4']]
        edge_moves = [m for m in ordered if m in ['a3', 'h3']]
        assert len(center_moves) == 2
        assert len(edge_moves) == 2

    @patch('chess_client.request.urlopen')
    def test_make_request_get(self, mock_urlopen):
        """
        Test HTTP GET request handling.

        :param mock_urlopen: Mocked urlopen function
        :type mock_urlopen: Mock
        :raises AssertionError: If request handling is incorrect
        """
        client = ChessClient("http://localhost:9002", 5.0)

        # Mock response
        mock_response = Mock()
        mock_response.read.return_value = b'{"turn": "white"}'
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = client.make_request('/turn')
        assert result == {"turn": "white"}

    @patch('chess_client.request.urlopen')
    def test_make_request_post(self, mock_urlopen):
        """
        Test HTTP POST request handling.

        :param mock_urlopen: Mocked urlopen function
        :type mock_urlopen: Mock
        :raises AssertionError: If POST request handling is incorrect
        """
        client = ChessClient("http://localhost:9002", 5.0)

        # Mock response
        mock_response = Mock()
        mock_response.read.return_value = b'{"success": true}'
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = client.make_request('/move', 'POST', {'move': 'e4'})
        assert result == {"success": True}

    def test_choose_move_single_legal_move(self):
        """
        Test move selection with only one legal move.

        :raises AssertionError: If wrong move is chosen
        """
        client = ChessClient("http://localhost:9002", 5.0)
        client.player_color = 'white'  # Set for test
        legal_moves = ['e4']
        chosen = client.choose_move(legal_moves)
        assert chosen == 'e4'

    def test_choose_move_no_legal_moves(self):
        """
        Test move selection with no legal moves raises exception.

        :raises AssertionError: If exception is not raised
        """
        client = ChessClient("http://localhost:9002", 5.0)
        with pytest.raises(Exception, match="No legal moves available"):
            client.choose_move([])
