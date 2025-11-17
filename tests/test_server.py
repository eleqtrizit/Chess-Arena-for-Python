"""Tests for FastAPI server module."""

import asyncio
import json
import os
from unittest.mock import patch

import pytest
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


@pytest.mark.asyncio
class TestTimeLimitEnforcement:
    """Test cases for server-side time limit enforcement."""

    async def test_time_limit_disqualification(self) -> None:
        """Test that exceeding time limit results in disqualification."""
        # Set server search time to 1 second
        with patch.dict(os.environ, {"SEARCH_TIME": "1.0"}):
            # Need to reload the module to pick up the env variable
            import importlib

            from chess_arena import server
            importlib.reload(server)

            client = TestClient(server.app)

            # Create a matchmade game with two players
            with client.websocket_connect("/ws") as ws1:
                with client.websocket_connect("/ws") as ws2:
                    # Player 1 joins queue
                    ws1.send_json({"type": "join_queue"})

                    # Player 2 joins queue - this should create a match
                    ws2.send_json({"type": "join_queue"})

                    # Receive match_found messages
                    msg1 = ws1.receive_json()
                    msg2 = ws2.receive_json()

                    assert msg1["type"] == "match_found"
                    assert msg2["type"] == "match_found"

                    game_id = msg1["game_id"]
                    player1_id = msg1["player_id"]
                    player1_token = msg1["auth_token"]
                    first_move_player = msg1["first_move"]

                    player2_id = msg2["player_id"]
                    player2_token = msg2["auth_token"]

                    # Determine who moves first
                    if first_move_player == player1_id:
                        first_ws = ws1
                        first_player_id = player1_id
                        first_token = player1_token
                        second_ws = ws2
                    else:
                        first_ws = ws2
                        first_player_id = player2_id
                        first_token = player2_token
                        second_ws = ws1

                    # Simulate taking too long (sleep for 1.5 seconds > 1.0 second limit)
                    await asyncio.sleep(1.5)

                    # First player makes a move (should be disqualified for taking too long)
                    first_ws.send_json({
                        "type": "make_move",
                        "data": {
                            "game_id": game_id,
                            "player_id": first_player_id,
                            "auth_token": first_token,
                            "move": "e4"
                        }
                    })

                    # Both players should receive game_over message with disqualified status
                    response1 = first_ws.receive_json()
                    assert response1["type"] == "game_over"
                    assert response1["status"] == "disqualified"
                    assert response1["disqualified_player"] == first_player_id
                    assert "Time limit exceeded" in response1["reason"]

                    response2 = second_ws.receive_json()
                    assert response2["type"] == "game_over"
                    assert response2["status"] == "disqualified"

    async def test_time_limit_within_bounds(self) -> None:
        """Test that moves within time limit are accepted."""
        # Set server search time to 2 seconds
        with patch.dict(os.environ, {"SEARCH_TIME": "2.0"}):
            import importlib

            from chess_arena import server
            importlib.reload(server)

            client = TestClient(server.app)

            with client.websocket_connect("/ws") as ws1:
                with client.websocket_connect("/ws") as ws2:
                    # Player 1 joins queue
                    ws1.send_json({"type": "join_queue"})

                    # Player 2 joins queue
                    ws2.send_json({"type": "join_queue"})

                    # Receive match_found messages
                    msg1 = ws1.receive_json()
                    msg2 = ws2.receive_json()

                    game_id = msg1["game_id"]
                    player1_id = msg1["player_id"]
                    player1_token = msg1["auth_token"]
                    first_move_player = msg1["first_move"]

                    player2_id = msg2["player_id"]
                    player2_token = msg2["auth_token"]

                    # Determine who moves first
                    if first_move_player == player1_id:
                        first_ws = ws1
                        first_player_id = player1_id
                        first_token = player1_token
                    else:
                        first_ws = ws2
                        first_player_id = player2_id
                        first_token = player2_token

                    # Wait less than time limit (1 second < 2 second limit)
                    await asyncio.sleep(1.0)

                    # First player makes a move (should be accepted)
                    first_ws.send_json({
                        "type": "make_move",
                        "data": {
                            "game_id": game_id,
                            "player_id": first_player_id,
                            "auth_token": first_token,
                            "move": "e4"
                        }
                    })

                    # Should receive move_made, not game_over
                    response1 = first_ws.receive_json()
                    assert response1["type"] == "move_made"
                    assert response1["game_over"] is False


@pytest.mark.asyncio
class TestHealthCheck:
    """Test cases for health check functionality."""

    async def test_healthy_players_can_match(self) -> None:
        """Test that healthy players can be matched successfully."""
        client = TestClient(app)

        # Create a matchmade game with two players
        with client.websocket_connect("/ws") as ws1:
            with client.websocket_connect("/ws") as ws2:
                # Player 1 joins queue
                ws1.send_json({"type": "join_queue"})

                # Player 2 joins queue - this should create a match
                ws2.send_json({"type": "join_queue"})

                # Receive match_found messages
                msg1 = ws1.receive_json()
                msg2 = ws2.receive_json()

                # Both players should be matched successfully
                assert msg1["type"] == "match_found"
                assert msg2["type"] == "match_found"

                # Both should have the same game_id
                assert msg1["game_id"] == msg2["game_id"]

                # Players should have different colors
                assert msg1["assigned_color"] != msg2["assigned_color"]
                assert msg1["assigned_color"] in ["white", "black"]
                assert msg2["assigned_color"] in ["white", "black"]
