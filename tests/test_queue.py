"""Tests for matchmaking queue module."""

import asyncio

import pytest

from chess_arena.queue import MatchmakingQueue


@pytest.mark.asyncio
async def test_two_players_match_successfully() -> None:
    """Test that two players joining the queue get matched."""
    queue = MatchmakingQueue()

    # Start two players joining simultaneously
    task1 = asyncio.create_task(queue.join_queue(timeout=5.0))
    task2 = asyncio.create_task(queue.join_queue(timeout=5.0))

    results = await asyncio.gather(task1, task2)

    # Both should get match results
    assert results[0] is not None
    assert results[1] is not None

    # Both should have the same game_id
    assert results[0].game_id == results[1].game_id

    # Player mappings should contain both player IDs
    assert len(results[0].player_mappings) == 2
    assert len(results[1].player_mappings) == 2

    # One player should be white, one should be black
    colors = list(results[0].player_mappings.values())
    assert 'white' in colors
    assert 'black' in colors

    # First move should be the white player
    white_player = [pid for pid, color in results[0].player_mappings.items() if color == 'white'][0]
    assert results[0].first_move == white_player


@pytest.mark.asyncio
async def test_single_player_timeout() -> None:
    """Test that a single player times out after waiting period."""
    queue = MatchmakingQueue()

    result = await queue.join_queue(timeout=0.1)

    assert result is None


@pytest.mark.asyncio
async def test_players_assigned_different_colors() -> None:
    """Test that matched players get different colors."""
    queue = MatchmakingQueue()

    task1 = asyncio.create_task(queue.join_queue(timeout=5.0))
    task2 = asyncio.create_task(queue.join_queue(timeout=5.0))

    results = await asyncio.gather(task1, task2)

    colors = set(results[0].player_mappings.values())
    assert colors == {'white', 'black'}


@pytest.mark.asyncio
async def test_multiple_sequential_matches() -> None:
    """Test that multiple pairs can be matched sequentially."""
    queue = MatchmakingQueue()

    # First match
    task1a = asyncio.create_task(queue.join_queue(timeout=5.0))
    task1b = asyncio.create_task(queue.join_queue(timeout=5.0))
    results1 = await asyncio.gather(task1a, task1b)

    assert results1[0] is not None
    assert results1[1] is not None
    game_id_1 = results1[0].game_id

    # Second match
    task2a = asyncio.create_task(queue.join_queue(timeout=5.0))
    task2b = asyncio.create_task(queue.join_queue(timeout=5.0))
    results2 = await asyncio.gather(task2a, task2b)

    assert results2[0] is not None
    assert results2[1] is not None
    game_id_2 = results2[0].game_id

    # Should be different games
    assert game_id_1 != game_id_2
