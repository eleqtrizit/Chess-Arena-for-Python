"""Example: Using logged game states to test chess algorithms."""

import json
from typing import List

import chess

from chess_arena.persistence import GAME_STATES_FILE


def example_choose_move(board: chess.Board, legal_moves: List[str], player_color: str) -> str:
    """
    Example implementation of a choose_move function.

    This is the signature that clients must implement.

    :param board: Current chess board state
    :type board: chess.Board
    :param legal_moves: List of legal moves in algebraic notation
    :type legal_moves: List[str]
    :param player_color: Color of the player to move ('white' or 'black')
    :type player_color: str
    :return: Selected move in algebraic notation
    :rtype: str
    """
    # Simple example: just pick the first legal move
    return legal_moves[0] if legal_moves else ""


def test_algorithm_with_logged_data() -> None:
    """
    Test a chess algorithm using logged game states.

    Reads game states from the log file and runs them through
    the algorithm to verify behavior.
    """
    if not GAME_STATES_FILE.exists():
        print(f"No log file found at {GAME_STATES_FILE}")
        print("Run some games first to generate test data!")
        return

    print("Testing algorithm with logged game states...")
    print("=" * 70)

    with open(GAME_STATES_FILE, 'r') as f:
        for i, line in enumerate(f, 1):
            data = json.loads(line)

            # Reconstruct the exact state the client would see
            board = chess.Board(data["fen"])
            legal_moves = data["legal_moves"]
            player_color = data["player_color"]

            # Test your algorithm
            chosen_move = example_choose_move(board, legal_moves, player_color)

            print(f"\nTest Case #{i}:")
            print(f"  Player: {player_color}")
            print(f"  Position: {data['fen']}")
            print(f"  Legal moves: {len(legal_moves)} available")
            print(f"  Algorithm chose: {chosen_move}")

            # Verify the chosen move is legal
            if chosen_move in legal_moves:
                print(f"  ✓ Valid move")
            else:
                print(f"  ✗ INVALID MOVE! Not in legal moves list")

    print("\n" + "=" * 70)
    print("Testing complete!")


if __name__ == "__main__":
    test_algorithm_with_logged_data()
