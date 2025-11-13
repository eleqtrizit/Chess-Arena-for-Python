"""Tests for chess board module."""

import chess

from chess_arena.board import ChessBoard


class TestChessBoard:
    """Test cases for ChessBoard class."""

    def test_initialization(self) -> None:
        """Test board initializes in starting position."""
        board = ChessBoard()
        assert board.get_fen() == chess.STARTING_FEN

    def test_reset(self) -> None:
        """Test board resets to starting position."""
        board = ChessBoard()
        board.make_move("e4")
        board.reset()
        assert board.get_fen() == chess.STARTING_FEN

    def test_valid_move(self) -> None:
        """Test making a valid move."""
        board = ChessBoard()
        assert board.make_move("e4") is True

    def test_invalid_move(self) -> None:
        """Test making an invalid move."""
        board = ChessBoard()
        assert board.make_move("e5") is False

    def test_get_current_turn(self) -> None:
        """Test getting current turn."""
        board = ChessBoard()
        assert board.get_current_turn() == "white"
        board.make_move("e4")
        assert board.get_current_turn() == "black"

    def test_get_legal_moves(self) -> None:
        """Test getting legal moves."""
        board = ChessBoard()
        legal_moves = board.get_legal_moves()
        assert len(legal_moves) == 20
        assert "e4" in legal_moves

    def test_get_all_coordinates(self) -> None:
        """Test getting all piece coordinates."""
        board = ChessBoard()
        coords = board.get_all_coordinates()
        assert coords["e1"] == "K"
        assert coords["e8"] == "k"
        assert "e4" not in coords

    def test_get_board_state(self) -> None:
        """Test getting board state."""
        board = ChessBoard()
        state = board.get_board_state()
        assert len(state) == 8
        assert len(state[0]) == 8
        assert state[0][4] == "k"

    def test_is_game_over_initial(self) -> None:
        """Test game is not over at start."""
        board = ChessBoard()
        assert board.is_game_over() is False

    def test_get_game_over_reason_not_over(self) -> None:
        """Test game over reason when game is not over."""
        board = ChessBoard()
        assert board.get_game_over_reason() == ""

    def test_get_game_over_reason_checkmate_white_wins(self) -> None:
        """Test game over reason for checkmate with white winning."""
        board = ChessBoard()
        board.board.set_fen("rnb1kbnr/pppp1ppp/8/4p3/5PPq/8/PPPPP2P/RNBQKBNR w KQkq - 1 3")
        assert board.is_game_over() is True
        assert board.get_game_over_reason() == "Checkmate - Black wins"

    def test_get_game_over_reason_checkmate_black_wins(self) -> None:
        """Test game over reason for checkmate with black winning."""
        board = ChessBoard()
        board.board.set_fen("r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4")
        assert board.is_game_over() is True
        assert board.get_game_over_reason() == "Checkmate - White wins"

    def test_get_game_over_reason_stalemate(self) -> None:
        """Test game over reason for stalemate."""
        board = ChessBoard()
        board.board.set_fen("k7/8/KQ6/8/8/8/8/8 b - - 0 1")
        assert board.is_game_over() is True
        assert board.get_game_over_reason() == "Stalemate - Draw"

    def test_get_game_over_reason_insufficient_material(self) -> None:
        """Test game over reason for insufficient material."""
        board = ChessBoard()
        board.board.set_fen("k7/8/8/8/8/8/8/K7 w - - 0 1")
        assert board.is_game_over() is True
        assert board.get_game_over_reason() == "Insufficient material - Draw"

    def test_replay_pgn_valid(self) -> None:
        """Test replaying valid PGN."""
        board = ChessBoard()
        assert board.replay_pgn("1.e4 e5 2.Nf3 Nc6") is True
        assert board.get_current_turn() == "white"

    def test_replay_pgn_invalid(self) -> None:
        """Test replaying invalid PGN."""
        board = ChessBoard()
        assert board.replay_pgn("1.e4 e5 2.Nf3 invalid") is False
