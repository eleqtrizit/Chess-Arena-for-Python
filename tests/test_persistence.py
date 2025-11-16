"""Tests for game state persistence module."""

import json
import shutil

import chess
import pytest

from chess_arena.board import ChessBoard
from chess_arena.persistence import PERSIST_DIR, PERSIST_FILE, ensure_persist_dir, load_games, save_games


@pytest.fixture
def clean_persist_dir():
    """Clean up persistence directory before and after tests."""
    if PERSIST_FILE.exists():
        PERSIST_FILE.unlink()
    if PERSIST_DIR.exists():
        shutil.rmtree(PERSIST_DIR)
    yield
    if PERSIST_FILE.exists():
        PERSIST_FILE.unlink()
    if PERSIST_DIR.exists():
        shutil.rmtree(PERSIST_DIR)


def test_ensure_persist_dir(clean_persist_dir):
    """Test that persistence directory is created."""
    assert not PERSIST_DIR.exists()
    ensure_persist_dir()
    assert PERSIST_DIR.exists()
    assert PERSIST_DIR.is_dir()


def test_ensure_persist_dir_idempotent(clean_persist_dir):
    """Test that ensure_persist_dir can be called multiple times."""
    ensure_persist_dir()
    ensure_persist_dir()
    assert PERSIST_DIR.exists()


def test_save_games_empty(clean_persist_dir):
    """Test saving empty games dictionary."""
    games = {}
    save_games(games)
    assert PERSIST_FILE.exists()

    with open(PERSIST_FILE, 'r') as f:
        data = json.load(f)
    assert data == {}


def test_save_games_single(clean_persist_dir):
    """Test saving a single game."""
    games = {"test-game-1": ChessBoard()}
    save_games(games)

    with open(PERSIST_FILE, 'r') as f:
        data = json.load(f)

    assert "test-game-1" in data
    assert data["test-game-1"]["fen"] == chess.Board().fen()
    assert "updated_at" in data["test-game-1"]


def test_save_games_multiple(clean_persist_dir):
    """Test saving multiple games."""
    board1 = ChessBoard()
    board1.make_move("e4")

    board2 = ChessBoard()
    board2.make_move("d4")

    games = {
        "game-1": board1,
        "game-2": board2
    }
    save_games(games)

    with open(PERSIST_FILE, 'r') as f:
        data = json.load(f)

    assert len(data) == 2
    assert "game-1" in data
    assert "game-2" in data


def test_load_games_no_file(clean_persist_dir):
    """Test loading when no persistence file exists."""
    games = load_games()
    assert games == {}


def test_load_games_empty_file(clean_persist_dir):
    """Test loading from empty games file."""
    ensure_persist_dir()
    with open(PERSIST_FILE, 'w') as f:
        json.dump({}, f)

    games = load_games()
    assert games == {}


def test_load_games_single(clean_persist_dir):
    """Test loading a single game."""
    board = ChessBoard()
    board.make_move("e4")
    save_games({"test-game": board})

    loaded_games = load_games()
    assert "test-game" in loaded_games
    assert loaded_games["test-game"].get_fen() == board.get_fen()


def test_load_games_multiple(clean_persist_dir):
    """Test loading multiple games."""
    board1 = ChessBoard()
    board1.make_move("e4")
    board1.make_move("e5")

    board2 = ChessBoard()
    board2.make_move("d4")

    games = {"game-1": board1, "game-2": board2}
    save_games(games)

    loaded_games = load_games()
    assert len(loaded_games) == 2
    assert loaded_games["game-1"].get_fen() == board1.get_fen()
    assert loaded_games["game-2"].get_fen() == board2.get_fen()


def test_save_and_load_preserves_position(clean_persist_dir):
    """Test that save/load cycle preserves exact board position."""
    board = ChessBoard()
    board.make_move("e4")
    board.make_move("e5")
    board.make_move("Nf3")
    board.make_move("Nc6")

    original_fen = board.get_fen()
    save_games({"game": board})

    loaded_games = load_games()
    loaded_fen = loaded_games["game"].get_fen()

    assert loaded_fen == original_fen


def test_load_games_corrupt_json(clean_persist_dir):
    """Test loading from corrupted JSON file."""
    ensure_persist_dir()
    with open(PERSIST_FILE, 'w') as f:
        f.write("{ invalid json }")

    games = load_games()
    assert games == {}


def test_load_games_invalid_fen(clean_persist_dir):
    """Test loading with invalid FEN notation."""
    ensure_persist_dir()
    with open(PERSIST_FILE, 'w') as f:
        json.dump({"game-1": {"fen": "invalid-fen", "updated_at": "2024-01-01"}}, f)

    games = load_games()
    assert games == {}
