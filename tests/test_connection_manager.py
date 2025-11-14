"""Tests for WebSocket connection manager."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from chess_arena.connection_manager import ConnectionManager


@pytest.mark.asyncio
async def test_connect():
    """
    Test connecting a new WebSocket.

    :return: None
    :rtype: None
    """
    manager = ConnectionManager()
    websocket = AsyncMock()

    connection_id = await manager.connect(websocket)

    assert connection_id is not None
    assert connection_id in manager.active_connections
    assert connection_id in manager.connection_metadata
    websocket.accept.assert_called_once()


@pytest.mark.asyncio
async def test_disconnect():
    """
    Test disconnecting a WebSocket.

    :return: None
    :rtype: None
    """
    manager = ConnectionManager()
    websocket = AsyncMock()

    connection_id = await manager.connect(websocket)
    await manager.disconnect(connection_id)

    assert connection_id not in manager.active_connections
    assert connection_id not in manager.connection_metadata


@pytest.mark.asyncio
async def test_send_message_success():
    """
    Test sending a message to an active connection.

    :return: None
    :rtype: None
    """
    manager = ConnectionManager()
    websocket = AsyncMock()

    connection_id = await manager.connect(websocket)
    message = {"type": "test", "data": "hello"}

    result = await manager.send_message(connection_id, message)

    assert result is True
    websocket.send_json.assert_called_once_with(message)


@pytest.mark.asyncio
async def test_send_message_not_found():
    """
    Test sending a message to a non-existent connection.

    :return: None
    :rtype: None
    """
    manager = ConnectionManager()
    message = {"type": "test"}

    result = await manager.send_message("invalid-id", message)

    assert result is False


@pytest.mark.asyncio
async def test_send_message_broken_connection():
    """
    Test sending a message to a broken connection.

    :return: None
    :rtype: None
    """
    manager = ConnectionManager()
    websocket = AsyncMock()
    websocket.send_json.side_effect = Exception("Connection broken")

    connection_id = await manager.connect(websocket)
    message = {"type": "test"}

    result = await manager.send_message(connection_id, message)

    assert result is False
    assert connection_id not in manager.active_connections


@pytest.mark.asyncio
async def test_send_to_game():
    """
    Test sending a message to all connections in a game.

    :return: None
    :rtype: None
    """
    manager = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    ws3 = AsyncMock()

    conn1 = await manager.connect(ws1)
    conn2 = await manager.connect(ws2)
    conn3 = await manager.connect(ws3)

    manager.set_game_info(conn1, "game1", "player1")
    manager.set_game_info(conn2, "game1", "player2")
    manager.set_game_info(conn3, "game2", "player3")

    message = {"type": "update"}
    await manager.send_to_game("game1", message)

    assert ws1.send_json.called
    assert ws2.send_json.called
    assert not ws3.send_json.called


@pytest.mark.asyncio
async def test_send_to_game_exclude_connection():
    """
    Test sending a message to game connections, excluding one.

    :return: None
    :rtype: None
    """
    manager = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    conn1 = await manager.connect(ws1)
    conn2 = await manager.connect(ws2)

    manager.set_game_info(conn1, "game1", "player1")
    manager.set_game_info(conn2, "game1", "player2")

    message = {"type": "update"}
    await manager.send_to_game("game1", message, exclude_connection=conn1)

    assert not ws1.send_json.called
    assert ws2.send_json.called


def test_set_game_info():
    """
    Test setting game information for a connection.

    :return: None
    :rtype: None
    """
    manager = ConnectionManager()
    manager.connection_metadata["test-conn"] = {
        "connected_at": 0.0,
        "game_id": None,
        "player_id": None
    }

    manager.set_game_info("test-conn", "game123", "player456")

    metadata = manager.connection_metadata["test-conn"]
    assert metadata["game_id"] == "game123"
    assert metadata["player_id"] == "player456"


def test_get_game_connections():
    """
    Test getting all connections for a specific game.

    :return: None
    :rtype: None
    """
    manager = ConnectionManager()
    manager.connection_metadata = {
        "conn1": {"game_id": "game1", "player_id": "p1"},
        "conn2": {"game_id": "game1", "player_id": "p2"},
        "conn3": {"game_id": "game2", "player_id": "p3"}
    }

    connections = manager.get_game_connections("game1")

    assert len(connections) == 2
    assert connections["conn1"] == "p1"
    assert connections["conn2"] == "p2"
    assert "conn3" not in connections


def test_is_connected():
    """
    Test checking if a connection is active.

    :return: None
    :rtype: None
    """
    manager = ConnectionManager()
    manager.active_connections["conn1"] = MagicMock()

    assert manager.is_connected("conn1") is True
    assert manager.is_connected("conn2") is False
