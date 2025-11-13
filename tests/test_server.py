"""Tests for FastAPI server module."""

from fastapi.testclient import TestClient

from chess_arena.server import app


class TestServer:
    """Test cases for FastAPI server endpoints."""

    def test_root(self) -> None:
        """Test root endpoint."""
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        assert "Chess Arena API" in response.json()["message"]

    def test_get_board(self) -> None:
        """Test getting board state."""
        client = TestClient(app)
        client.post("/reset")
        response = client.get("/board")
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
        client.post("/reset")
        response = client.get("/coordinates")
        assert response.status_code == 200
        data = response.json()
        assert "coordinates" in data
        assert "e1" in data["coordinates"]

    def test_get_turn(self) -> None:
        """Test getting current turn."""
        client = TestClient(app)
        client.post("/reset")
        response = client.get("/turn")
        assert response.status_code == 200
        data = response.json()
        assert data["turn"] == "white"

    def test_get_legal_moves(self) -> None:
        """Test getting legal moves."""
        client = TestClient(app)
        client.post("/reset")
        response = client.get("/legal-moves")
        assert response.status_code == 200
        data = response.json()
        assert len(data["legal_moves"]) == 20

    def test_make_valid_move(self) -> None:
        """Test making a valid move."""
        client = TestClient(app)
        client.post("/reset")
        response = client.post("/move", json={"move": "e4", "player": "white"})
        assert response.status_code == 200
        data = response.json()
        assert data["game_over"] is False
        assert data["game_over_reason"] == ""

    def test_make_invalid_move(self) -> None:
        """Test making an invalid move."""
        client = TestClient(app)
        client.post("/reset")
        response = client.post("/move", json={"move": "e5", "player": "white"})
        assert response.status_code == 400

    def test_make_move_wrong_turn(self) -> None:
        """Test making a move on wrong turn."""
        client = TestClient(app)
        client.post("/reset")
        response = client.post("/move", json={"move": "e5", "player": "black"})
        assert response.status_code == 403

    def test_replay_pgn(self) -> None:
        """Test replaying PGN."""
        client = TestClient(app)
        response = client.post("/replay", json={"pgn": "1.e4 e5 2.Nf3"})
        assert response.status_code == 200
        data = response.json()
        assert data["game_over"] is False
        assert data["game_over_reason"] == ""

    def test_replay_invalid_pgn(self) -> None:
        """Test replaying invalid PGN."""
        client = TestClient(app)
        response = client.post("/replay", json={"pgn": "1.e4 invalid"})
        assert response.status_code == 400

    def test_reset_board(self) -> None:
        """Test resetting the board."""
        client = TestClient(app)
        client.post("/move", json={"move": "e4", "player": "white"})
        response = client.post("/reset")
        assert response.status_code == 200
        data = response.json()
        assert data["game_over"] is False
        assert data["game_over_reason"] == ""
        turn_response = client.get("/turn")
        assert turn_response.json()["turn"] == "white"
