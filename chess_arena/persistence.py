"""Game state persistence module."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import chess

from chess_arena.board import ChessBoard

PERSIST_DIR = Path("/tmp/chess_arena")
PERSIST_FILE = PERSIST_DIR / "games.json"
GAME_STATES_FILE = PERSIST_DIR / "game_states.jsonl"


def ensure_persist_dir() -> None:
    """
    Ensure the persistence directory exists.

    :raises OSError: If directory creation fails
    """
    PERSIST_DIR.mkdir(parents=True, exist_ok=True)


def save_games(games: Dict[str, ChessBoard]) -> None:
    """
    Save all game states to disk.

    :param games: Dictionary mapping game IDs to ChessBoard instances
    :type games: Dict[str, ChessBoard]
    """
    ensure_persist_dir()

    game_data = {}
    for game_id, board in games.items():
        game_data[game_id] = {
            "fen": board.get_fen(),
            "player_mappings": board.player_mappings,
            "updated_at": datetime.now().isoformat()
        }

    with open(PERSIST_FILE, 'w') as f:
        json.dump(game_data, f, indent=2)


def load_games() -> Dict[str, ChessBoard]:
    """
    Load all game states from disk.

    :return: Dictionary mapping game IDs to ChessBoard instances
    :rtype: Dict[str, ChessBoard]
    """
    if not PERSIST_FILE.exists():
        return {}

    try:
        with open(PERSIST_FILE, 'r') as f:
            game_data = json.load(f)

        games = {}
        for game_id, data in game_data.items():
            player_mappings = data.get("player_mappings", {})
            board = ChessBoard(player_mappings=player_mappings)
            board.board = chess.Board(data["fen"])
            games[game_id] = board

        return games
    except (json.JSONDecodeError, KeyError, ValueError):
        return {}


def log_game_state(board: chess.Board, legal_moves: List[str], player_color: str) -> None:
    """
    Log game state, legal moves, and player color to JSONL file.

    :param board: Current chess board state
    :type board: chess.Board
    :param legal_moves: List of legal moves in algebraic notation
    :type legal_moves: List[str]
    :param player_color: Color of the player to move ('white' or 'black')
    :type player_color: str
    """
    ensure_persist_dir()

    log_entry = {
        "fen": board.fen(),
        "legal_moves": legal_moves,
        "player_color": player_color,
        "timestamp": datetime.now().isoformat()
    }

    with open(GAME_STATES_FILE, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')
