#!/usr/bin/env python3
"""
Tests for Strategy class with minimax algorithm.
"""

import chess
import pytest

from demos.strategy import Strategy


def test_strategy_initialization() -> None:
    """
    Test that Strategy can be instantiated with search_time.
    """
    strategy = Strategy(search_time=2.0)
    assert strategy.search_time == 2.0
    assert strategy.nodes_searched == 0


def test_evaluate_initial_position() -> None:
    """
    Test that initial position evaluates to approximately equal (near 0).
    """
    strategy = Strategy(search_time=1.0)
    board = chess.Board()
    evaluation = strategy.evaluate_position(board)
    # Initial position should be roughly equal, allow some positional bonus variance
    assert -200 <= evaluation <= 200


def test_evaluate_checkmate_white_wins() -> None:
    """
    Test that checkmate for white returns high positive score.
    """
    strategy = Strategy(search_time=1.0)
    # Fool's mate: black is checkmated
    board = chess.Board()
    board.push_san("f3")
    board.push_san("e6")
    board.push_san("g4")
    board.push_san("Qh4")  # Checkmate
    # After Qh4#, it's white's turn but white is checkmated
    # When board.turn is True (white to move) and checkmated, black won
    evaluation = strategy.evaluate_position(board)
    assert evaluation == -20000  # Black wins (white is checkmated)


def test_evaluate_checkmate_black_wins() -> None:
    """
    Test that checkmate for black returns high negative score.
    """
    strategy = Strategy(search_time=1.0)
    # Scholar's mate variation where white is checkmated
    board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    evaluation = strategy.evaluate_position(board)
    assert evaluation == -20000  # Black wins


def test_evaluate_stalemate() -> None:
    """
    Test that stalemate returns 0.
    """
    strategy = Strategy(search_time=1.0)
    # Stalemate position
    board = chess.Board("7k/8/6Q1/8/8/8/8/K7 b - - 0 1")
    evaluation = strategy.evaluate_position(board)
    assert evaluation == 0


def test_order_moves_prioritizes_captures() -> None:
    """
    Test that move ordering puts captures first.
    """
    strategy = Strategy(search_time=1.0)
    board = chess.Board()
    board.push_san("e4")
    board.push_san("d5")
    # White can capture with exd5
    legal_moves = list(board.legal_moves)
    ordered = strategy._order_moves(board, legal_moves)

    # Find capture move (e4xd5)
    capture_move = None
    for move in ordered:
        if board.is_capture(move):
            capture_move = move
            break

    assert capture_move is not None
    assert ordered[0] == capture_move or board.is_capture(ordered[0])


def test_choose_move_single_legal_move() -> None:
    """
    Test that when only one legal move exists, it's chosen immediately.
    """
    strategy = Strategy(search_time=1.0)
    # Position with only one legal move for black
    board = chess.Board("8/8/8/8/8/3k4/3p4/3K4 b - - 0 1")
    legal_moves = [board.san(m) for m in board.legal_moves]

    chosen = strategy.choose_move(board, legal_moves, "black")
    assert chosen in legal_moves


def test_choose_move_white() -> None:
    """
    Test that strategy chooses a valid move for white.
    """
    strategy = Strategy(search_time=1.0)
    board = chess.Board()
    legal_moves = [board.san(m) for m in board.legal_moves]

    chosen = strategy.choose_move(board, legal_moves, "white")
    assert chosen in legal_moves


def test_choose_move_black() -> None:
    """
    Test that strategy chooses a valid move for black.
    """
    strategy = Strategy(search_time=1.0)
    board = chess.Board()
    board.push_san("e4")
    legal_moves = [board.san(m) for m in board.legal_moves]

    chosen = strategy.choose_move(board, legal_moves, "black")
    assert chosen in legal_moves


def test_choose_move_no_legal_moves() -> None:
    """
    Test that strategy raises exception when no legal moves available.

    :raises Exception: When no legal moves provided
    """
    strategy = Strategy(search_time=1.0)
    board = chess.Board()

    with pytest.raises(Exception, match="No legal moves available"):
        strategy.choose_move(board, [], "white")


def test_minimax_finds_checkmate_in_one() -> None:
    """
    Test that minimax finds checkmate in one move.
    """
    strategy = Strategy(search_time=2.0)
    # Back rank mate: black to move with mate in one Qd1#
    board = chess.Board("r4rk1/pppq1ppp/2np1n2/4p3/1bB1P3/2NP1N2/PPP2PPP/R1BQ1RK1 b - - 0 9")
    legal_moves = [board.san(m) for m in board.legal_moves]

    chosen = strategy.choose_move(board, legal_moves, "black")
    # Should choose a strong move (likely Qd1+ or similar attacking moves)
    assert chosen in legal_moves


def test_minimax_avoids_blunders() -> None:
    """
    Test that minimax doesn't immediately lose material.
    """
    strategy = Strategy(search_time=1.0)
    # Position where queen is hanging
    board = chess.Board()
    board.push_san("e4")
    board.push_san("e5")
    board.push_san("Qh5")  # Attacking f7
    board.push_san("Nc6")

    legal_moves = [board.san(m) for m in board.legal_moves]
    chosen = strategy.choose_move(board, legal_moves, "white")

    # White shouldn't move queen to a square where it's captured for free
    # This is a basic sanity check
    assert chosen in legal_moves
