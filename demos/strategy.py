#!/usr/bin/env python3
"""
Minimax strategy with alpha-beta pruning for chess.

Uses iterative deepening, piece-square tables, and move ordering
for efficient search.
"""

import time
from typing import List, Optional, Tuple

import chess
from rich.console import Console
from strategy_base import StrategyBase

console = Console()

# Piece values for material evaluation
PIECE_VALUES = {
    'P': 100, 'N': 320, 'B': 330, 'R': 500, 'Q': 900, 'K': 20000,
    'p': -100, 'n': -320, 'b': -330, 'r': -500, 'q': -900, 'k': -20000
}

# Piece-square tables for positional evaluation (from white's perspective)
# Pawns: encourage center control and advancement
PAWN_TABLE = [
    0, 0, 0, 0, 0, 0, 0, 0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5, 5, 10, 25, 25, 10, 5, 5,
    0, 0, 0, 20, 20, 0, 0, 0,
    5, -5, -10, 0, 0, -10, -5, 5,
    5, 10, 10, -20, -20, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0
]

# Knights: encourage central positions
KNIGHT_TABLE = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20, 0, 0, 0, 0, -20, -40,
    -30, 0, 10, 15, 15, 10, 0, -30,
    -30, 5, 15, 20, 20, 15, 5, -30,
    -30, 0, 15, 20, 20, 15, 0, -30,
    -30, 5, 10, 15, 15, 10, 5, -30,
    -40, -20, 0, 5, 5, 0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50
]

# Bishops: encourage long diagonals
BISHOP_TABLE = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -10, 0, 5, 10, 10, 5, 0, -10,
    -10, 5, 5, 10, 10, 5, 5, -10,
    -10, 0, 10, 10, 10, 10, 0, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -20, -10, -10, -10, -10, -10, -10, -20
]

# Rooks: encourage open files and 7th rank
ROOK_TABLE = [
    0, 0, 0, 0, 0, 0, 0, 0,
    5, 10, 10, 10, 10, 10, 10, 5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    0, 0, 0, 5, 5, 0, 0, 0
]

# Queens: slight central preference
QUEEN_TABLE = [
    -20, -10, -10, -5, -5, -10, -10, -20,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -10, 0, 5, 5, 5, 5, 0, -10,
    -5, 0, 5, 5, 5, 5, 0, -5,
    0, 0, 5, 5, 5, 5, 0, -5,
    -10, 5, 5, 5, 5, 5, 0, -10,
    -10, 0, 5, 0, 0, 0, 0, -10,
    -20, -10, -10, -5, -5, -10, -10, -20
]

# King (middlegame): stay safe, prefer castled position
KING_MIDDLEGAME_TABLE = [
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    20, 20, 0, 0, 0, 0, 20, 20,
    20, 30, 10, 0, 0, 10, 30, 20
]

PIECE_SQUARE_TABLES = {
    'P': PAWN_TABLE,
    'N': KNIGHT_TABLE,
    'B': BISHOP_TABLE,
    'R': ROOK_TABLE,
    'Q': QUEEN_TABLE,
    'K': KING_MIDDLEGAME_TABLE
}


class Strategy(StrategyBase):
    """
    Minimax chess strategy with alpha-beta pruning and iterative deepening.

    Uses piece-square tables for positional evaluation and move ordering
    (captures, checks) for efficient search.

    :param search_time: Maximum time in seconds for move search
    :type search_time: float
    """

    def __init__(self, search_time: float):
        super().__init__(search_time)
        self.nodes_searched = 0

    def evaluate_position(self, board: chess.Board) -> int:
        """
        Evaluate board position (always from White's perspective).

        Combines material value with piece-square table positional bonuses.

        This function always returns scores from White's perspective (positive = good for White,
        negative = good for Black). This is standard practice in chess engines because it simplifies
        the evaluation logic - you only need one set of piece-square tables and material values.

        The minimax algorithm handles player perspective automatically: when this bot plays White,
        it maximizes the score; when playing Black, it minimizes the score (which means it seeks
        negative values, i.e., positions good for Black).

        :param board: chess.Board object
        :type board: chess.Board
        :return: Position score (positive favors White, negative favors Black)
        :rtype: int
        """
        if board.is_checkmate():
            return -20000 if board.turn else 20000

        if board.is_stalemate() or board.is_insufficient_material():
            return 0

        score = 0

        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece is None:
                continue

            # Get piece symbol
            piece_symbol = piece.symbol()

            # Material value
            score += PIECE_VALUES.get(piece_symbol, 0)

            # Positional bonus
            piece_type = piece_symbol.upper()
            if piece_type in PIECE_SQUARE_TABLES:
                table = PIECE_SQUARE_TABLES[piece_type]
                # chess library uses 0=a1, 63=h8. We need to convert to our table format
                # Our tables are indexed rank 8 (index 0) to rank 1 (index 7), files a-h
                rank = chess.square_rank(square)
                file = chess.square_file(square)

                if piece.color == chess.WHITE:
                    # White: flip rank (rank 0 in chess lib = rank 1 in our table = index 7)
                    table_idx = (7 - rank) * 8 + file
                    score += table[table_idx]
                else:
                    # Black: use rank as-is (rank 0 = rank 1 = index 7, which we then flip)
                    table_idx = rank * 8 + file
                    score -= table[table_idx]

        return score

    def _order_moves(self, board: chess.Board, moves: List[chess.Move]) -> List[chess.Move]:
        """
        Order moves for better alpha-beta pruning using board state.

        :param board: Current board position
        :type board: chess.Board
        :param moves: List of legal moves
        :type moves: List[chess.Move]
        :return: Ordered list of moves
        :rtype: List[chess.Move]
        """
        captures = []
        checks = []
        other_moves = []

        for move in moves:
            # Prioritize captures
            if board.is_capture(move):
                captures.append(move)
            # Then checks
            elif board.gives_check(move):
                checks.append(move)
            else:
                other_moves.append(move)

        return captures + checks + other_moves

    def minimax(self, board: chess.Board, depth: int, alpha: int, beta: int,
                maximizing: bool, start_time: float) -> Tuple[int, Optional[chess.Move]]:
        """
        Minimax search with alpha-beta pruning using local board simulation.

        :param board: Current board position
        :type board: chess.Board
        :param depth: Remaining search depth
        :type depth: int
        :param alpha: Alpha value for pruning
        :type alpha: int
        :param beta: Beta value for pruning
        :type beta: int
        :param maximizing: True if maximizing player's turn
        :type maximizing: bool
        :param start_time: Search start timestamp for time management
        :type start_time: float
        :return: Tuple of (evaluation, best_move)
        :rtype: Tuple[int, Optional[chess.Move]]
        """
        self.nodes_searched += 1

        # Time check
        if time.time() - start_time > self.search_time * 0.95:
            return self.evaluate_position(board), None

        # Base case: depth 0 or game over
        if depth == 0 or board.is_game_over():
            return self.evaluate_position(board), None

        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return self.evaluate_position(board), None

        # Order moves by heuristics (captures, checks, center control)
        ordered_moves = self._order_moves(board, legal_moves)
        best_move = None

        if maximizing:
            max_eval = float('-inf')
            for move in ordered_moves:
                # Make move
                board.push(move)

                # Recurse
                eval_score, _ = self.minimax(board, depth - 1, alpha, beta, False, start_time)

                # Undo move
                board.pop()

                if eval_score > max_eval:
                    max_eval = eval_score
                    best_move = move

                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break  # Beta cutoff

            return max_eval, best_move
        else:
            min_eval = float('inf')
            for move in ordered_moves:
                # Make move
                board.push(move)

                # Recurse
                eval_score, _ = self.minimax(board, depth - 1, alpha, beta, True, start_time)

                # Undo move
                board.pop()

                if eval_score < min_eval:
                    min_eval = eval_score
                    best_move = move

                beta = min(beta, eval_score)
                if beta <= alpha:
                    break  # Alpha cutoff

            return min_eval, best_move

    def choose_move(self, board: chess.Board, legal_moves: List[str], player_color: str) -> str:
        """
        Choose the best move using iterative deepening with minimax search.

        :param board: Current board position
        :type board: chess.Board
        :param legal_moves: List of legal moves in SAN (from server)
        :type legal_moves: List[str]
        :param player_color: Color of the player ("white" or "black")
        :type player_color: str
        :return: Selected move in SAN
        :rtype: str
        :raises Exception: If no legal moves available
        """
        if not legal_moves:
            raise Exception("No legal moves available")

        if len(legal_moves) == 1:
            return legal_moves[0]

        start_time = time.time()
        best_move_san = legal_moves[0]
        self.nodes_searched = 0

        maximizing = player_color == 'white'

        # Iterative deepening
        for depth in range(1, 20):
            if time.time() - start_time > self.search_time * 0.9:
                break

            try:
                # Copy board for this depth's search
                search_board = board.copy()

                # Run minimax search
                eval_score, best_move_obj = self.minimax(
                    search_board,
                    depth,
                    float('-inf'),
                    float('inf'),
                    maximizing,
                    start_time
                )

                if best_move_obj is not None:
                    # Convert chess.Move to SAN for server
                    best_move_san = board.san(best_move_obj)

                elapsed = time.time() - start_time
                console.print(
                    f"[dim]Depth {depth}:[/dim] {self.nodes_searched} nodes, {elapsed:.2f}s, "
                    f"eval={eval_score}, best=[cyan]{best_move_san}[/cyan]"
                )

                # Stop if we found a winning move
                if abs(eval_score) > 15000:
                    console.print("[bold green]✓ Found decisive advantage, stopping search[/bold green]")
                    break

            except Exception as e:
                console.print(f"[red]✗ Search error at depth {depth}:[/red] {e}")
                break

        return best_move_san
