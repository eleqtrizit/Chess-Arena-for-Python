"""Game state persistence module."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict

import chess

from chess_arena.board import ChessBoard

PERSIST_DIR = Path("/tmp/chess_arena")
PERSIST_FILE = PERSIST_DIR / "games.json"


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
