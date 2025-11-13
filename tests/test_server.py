"""Tests for FastAPI server module."""

import json

from fastapi.testclient import TestClient

from chess_arena.persistence import PERSIST_FILE
from chess_arena.server import app


class TestServer:
    """Test cases for FastAPI server endpoints."""

    def test_root(self) -> None:
        """Test root endpoint."""
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        assert "Chess Arena API" in response.json()["message"]

    def test_create_new_game(self) -> None:
        """Test creating a new game."""
        client = TestClient(app)
        response = client.post("/newgame")
        assert response.status_code == 200
        data = response.json()
        assert "game_id" in data
        assert len(data["game_id"]) > 0

    def test_get_board(self) -> None:
        """Test getting board state."""
        client = TestClient(app)
        new_game = client.post("/newgame")
        game_id = new_game.json()["game_id"]
        response = client.get(f"/board?game_id={game_id}")
        assert response.status_code == 200
        data = response.json()
        assert "board" in data
        assert "rendered" in data
        assert "fen" in data
        assert "game_over" in data
        assert "game_over_reason" in data
        assert len(data["board"]) == 8

    def test_get_coordinates(self) -> None:
        """Test getting piece coordinates."""
        client = TestClient(app)
        new_game = client.post("/newgame")
        game_id = new_game.json()["game_id"]
        response = client.get(f"/coordinates?game_id={game_id}")
        assert response.status_code == 200
        data = response.json()
        assert "coordinates" in data
        assert "e1" in data["coordinates"]

    def test_get_turn(self) -> None:
        """Test getting current turn."""
        client = TestClient(app)
        new_game = client.post("/newgame")
        game_id = new_game.json()["game_id"]
        response = client.get(f"/turn?game_id={game_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["turn"] == "white"

    def test_get_legal_moves(self) -> None:
        """Test getting legal moves."""
        client = TestClient(app)
        new_game = client.post("/newgame")
        game_id = new_game.json()["game_id"]
        response = client.get(f"/legal-moves?game_id={game_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["legal_moves"]) == 20

    def test_make_valid_move(self) -> None:
        """Test making a valid move."""
        client = TestClient(app)
        new_game = client.post("/newgame")
        game_id = new_game.json()["game_id"]
        response = client.post("/move", json={"game_id": game_id, "move": "e4", "player": "white"})
        assert response.status_code == 200
        data = response.json()
        assert data["game_over"] is False
        assert data["game_over_reason"] == ""

    def test_make_invalid_move(self) -> None:
        """Test making an invalid move."""
        client = TestClient(app)
        new_game = client.post("/newgame")
        game_id = new_game.json()["game_id"]
        response = client.post("/move", json={"game_id": game_id, "move": "e5", "player": "white"})
        assert response.status_code == 400

    def test_make_move_wrong_turn(self) -> None:
        """Test making a move on wrong turn."""
        client = TestClient(app)
        new_game = client.post("/newgame")
        game_id = new_game.json()["game_id"]
        response = client.post("/move", json={"game_id": game_id, "move": "e5", "player": "black"})
        assert response.status_code == 403

    def test_replay_pgn(self) -> None:
        """Test replaying PGN."""
        client = TestClient(app)
        new_game = client.post("/newgame")
        game_id = new_game.json()["game_id"]
        response = client.post("/replay", json={"game_id": game_id, "pgn": "1.e4 e5 2.Nf3"})
        assert response.status_code == 200
        data = response.json()
        assert data["game_over"] is False
        assert data["game_over_reason"] == ""

    def test_replay_invalid_pgn(self) -> None:
        """Test replaying invalid PGN."""
        client = TestClient(app)
        new_game = client.post("/newgame")
        game_id = new_game.json()["game_id"]
        response = client.post("/replay", json={"game_id": game_id, "pgn": "1.e4 invalid"})
        assert response.status_code == 400

    def test_reset_board(self) -> None:
        """Test resetting the board."""
        client = TestClient(app)
        new_game = client.post("/newgame")
        game_id = new_game.json()["game_id"]
        client.post("/move", json={"game_id": game_id, "move": "e4", "player": "white"})
        response = client.post("/reset", json={"game_id": game_id})
        assert response.status_code == 200
        data = response.json()
        assert data["game_over"] is False
        assert data["game_over_reason"] == ""
        turn_response = client.get(f"/turn?game_id={game_id}")
        assert turn_response.json()["turn"] == "white"

    def test_game_not_found(self) -> None:
        """Test accessing a non-existent game."""
        client = TestClient(app)
        response = client.get("/board?game_id=nonexistent")
        assert response.status_code == 404

    def test_multiple_games_isolation(self) -> None:
        """Test that multiple games are isolated from each other."""
        client = TestClient(app)
        game1 = client.post("/newgame").json()["game_id"]
        game2 = client.post("/newgame").json()["game_id"]

        # Make move in game1
        client.post("/move", json={"game_id": game1, "move": "e4", "player": "white"})

        # Verify game2 is unaffected
        turn2 = client.get(f"/turn?game_id={game2}").json()
        assert turn2["turn"] == "white"

        # Verify game1 has progressed
        turn1 = client.get(f"/turn?game_id={game1}").json()
        assert turn1["turn"] == "black"

    def test_persistence_new_game(self) -> None:
        """Test that new games are persisted to disk."""
        client = TestClient(app)
        game_id = client.post("/newgame").json()["game_id"]

        assert PERSIST_FILE.exists()
        with open(PERSIST_FILE, 'r') as f:
            data = json.load(f)

        assert game_id in data
        assert "fen" in data[game_id]
        assert "updated_at" in data[game_id]

    def test_persistence_after_move(self) -> None:
        """Test that game state is persisted after moves."""
        client = TestClient(app)
        game_id = client.post("/newgame").json()["game_id"]
        client.post("/move", json={"game_id": game_id, "move": "e4", "player": "white"})

        with open(PERSIST_FILE, 'r') as f:
            data = json.load(f)

        assert "b KQkq" in data[game_id]["fen"]

    def test_persistence_after_reset(self) -> None:
        """Test that game state is persisted after reset."""
        client = TestClient(app)
        game_id = client.post("/newgame").json()["game_id"]
        client.post("/move", json={"game_id": game_id, "move": "e4", "player": "white"})
        client.post("/reset", json={"game_id": game_id})

        with open(PERSIST_FILE, 'r') as f:
            data = json.load(f)

        assert "w KQkq - 0 1" in data[game_id]["fen"]
