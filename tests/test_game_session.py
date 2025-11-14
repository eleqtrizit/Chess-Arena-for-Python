"""Tests for game session manager."""

import time

import pytest

from chess_arena.connection_manager import ConnectionManager
from chess_arena.game_session import GameSession, GameSessionManager


def test_game_session_initialization():
    """
    Test game session initialization.

    :return: None
    :rtype: None
    """
    player_connections = {"player1": "conn1", "player2": "conn2"}
    session = GameSession("game123", player_connections)

    assert session.game_id == "game123"
    assert session.player_connections == player_connections
    assert len(session.disconnected_players) == 0
    assert session.is_cancelled is False
    assert session.winner is None


def test_mark_disconnected():
    """
    Test marking a player as disconnected.

    :return: None
    :rtype: None
    """
    session = GameSession("game123", {"player1": "conn1", "player2": "conn2"})

    session.mark_disconnected("player1")

    assert "player1" in session.disconnected_players
    assert isinstance(session.disconnected_players["player1"], float)


def test_mark_reconnected():
    """
    Test marking a player as reconnected.

    :return: None
    :rtype: None
    """
    session = GameSession("game123", {"player1": "conn1", "player2": "conn2"})

    session.mark_disconnected("player1")
    assert "player1" in session.disconnected_players

    session.mark_reconnected("player1")
    assert "player1" not in session.disconnected_players


def test_check_forfeit_no_timeout():
    """
    Test forfeit check when no timeout has occurred.

    :return: None
    :rtype: None
    """
    session = GameSession("game123", {"player1": "conn1", "player2": "conn2"})
    session.mark_disconnected("player1")

    result = session.check_forfeit()

    assert result is None


def test_check_forfeit_with_timeout():
    """
    Test forfeit check when timeout has occurred.

    :return: None
    :rtype: None
    """
    session = GameSession("game123", {"player1": "conn1", "player2": "conn2"})
    session.forfeit_timeout = 0.1

    session.mark_disconnected("player1")
    time.sleep(0.15)

    result = session.check_forfeit()

    assert result == "player2"
    assert session.winner == "player2"


def test_check_forfeit_all_disconnected():
    """
    Test forfeit check when all players disconnected.

    :return: None
    :rtype: None
    """
    session = GameSession("game123", {"player1": "conn1", "player2": "conn2"})

    session.mark_disconnected("player1")
    session.mark_disconnected("player2")

    result = session.check_forfeit()

    assert result == "cancelled"
    assert session.is_cancelled is True


def test_get_connected_players():
    """
    Test getting connected players.

    :return: None
    :rtype: None
    """
    session = GameSession("game123", {"player1": "conn1", "player2": "conn2"})

    session.mark_disconnected("player1")

    connected = session.get_connected_players()

    assert connected == {"player2"}


def test_is_player_connected():
    """
    Test checking if a player is connected.

    :return: None
    :rtype: None
    """
    session = GameSession("game123", {"player1": "conn1", "player2": "conn2"})

    assert session.is_player_connected("player1") is True
    assert session.is_player_connected("player2") is True

    session.mark_disconnected("player1")

    assert session.is_player_connected("player1") is False
    assert session.is_player_connected("player2") is True


@pytest.mark.asyncio
async def test_session_manager_create_session():
    """
    Test creating a game session.

    :return: None
    :rtype: None
    """
    conn_manager = ConnectionManager()
    session_manager = GameSessionManager(conn_manager)

    player_connections = {"player1": "conn1", "player2": "conn2"}
    session = await session_manager.create_session("game123", player_connections)

    assert session.game_id == "game123"
    assert "game123" in session_manager.sessions
    assert session_manager.connection_to_game["conn1"] == "game123"
    assert session_manager.connection_to_game["conn2"] == "game123"


@pytest.mark.asyncio
async def test_session_manager_handle_disconnect():
    """
    Test handling a connection disconnect.

    :return: None
    :rtype: None
    """
    conn_manager = ConnectionManager()
    session_manager = GameSessionManager(conn_manager)

    player_connections = {"player1": "conn1", "player2": "conn2"}
    await session_manager.create_session("game123", player_connections)

    result = await session_manager.handle_disconnect("conn1")

    assert result is not None
    assert result["game_id"] == "game123"
    assert result["disconnected_player_id"] == "player1"
    assert result["status"] == "disconnected"


@pytest.mark.asyncio
async def test_session_manager_handle_disconnect_both_players():
    """
    Test handling both players disconnecting.

    :return: None
    :rtype: None
    """
    conn_manager = ConnectionManager()
    session_manager = GameSessionManager(conn_manager)

    player_connections = {"player1": "conn1", "player2": "conn2"}
    await session_manager.create_session("game123", player_connections)

    await session_manager.handle_disconnect("conn1")
    result = await session_manager.handle_disconnect("conn2")

    assert result is not None
    assert result["status"] == "cancelled"


@pytest.mark.asyncio
async def test_session_manager_handle_reconnect():
    """
    Test handling a player reconnection.

    :return: None
    :rtype: None
    """
    conn_manager = ConnectionManager()
    session_manager = GameSessionManager(conn_manager)

    player_connections = {"player1": "conn1", "player2": "conn2"}
    await session_manager.create_session("game123", player_connections)

    await session_manager.handle_disconnect("conn1")

    success = await session_manager.handle_reconnect("conn3", "game123", "player1")

    assert success is True

    session = session_manager.get_session("game123")
    assert session.player_connections["player1"] == "conn3"
    assert session.is_player_connected("player1") is True


@pytest.mark.asyncio
async def test_session_manager_remove_session():
    """
    Test removing a game session.

    :return: None
    :rtype: None
    """
    conn_manager = ConnectionManager()
    session_manager = GameSessionManager(conn_manager)

    player_connections = {"player1": "conn1", "player2": "conn2"}
    await session_manager.create_session("game123", player_connections)

    await session_manager.remove_session("game123")

    assert "game123" not in session_manager.sessions
    assert "conn1" not in session_manager.connection_to_game
    assert "conn2" not in session_manager.connection_to_game
