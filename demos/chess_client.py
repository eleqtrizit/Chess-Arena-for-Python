#!/usr/bin/env python3
"""
Chess client for Chess Arena server.

Uses minimax search with alpha-beta pruning, iterative deepening,
and piece-square table evaluation.
"""

import argparse
import json
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib import error, request

import chess
from rich.console import Console

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


class ChessClient:
    """
    Standalone chess client with minimax search and alpha-beta pruning.

    :param server_url: Base URL of the Chess Arena server
    :type server_url: str
    :param player_color: 'white' or 'black'
    :type player_color: str
    :param search_time: Maximum time in seconds for move search
    :type search_time: float
    :param game_id: Optional game ID to join existing game
    :type game_id: str
    """

    def __init__(self, server_url: str, player_color: str, search_time: float, game_id: str = None):
        self.server_url = server_url
        self.player_color = player_color
        self.search_time = search_time
        self.game_id = game_id
        self.nodes_searched = 0
        self.local_board = chess.Board()  # Local board for move simulation

    def make_request(self, endpoint: str, method: str = 'GET', data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make HTTP request to the server.

        :param endpoint: API endpoint path
        :type endpoint: str
        :param method: HTTP method (GET or POST)
        :type method: str
        :param data: Request payload for POST requests
        :type data: Optional[Dict]
        :return: Parsed JSON response
        :rtype: Dict[str, Any]
        :raises Exception: If request fails
        """
        url = f"{self.server_url}{endpoint}"

        # Add game_id to URL query params for GET requests
        if method == 'GET' and self.game_id:
            separator = '&' if '?' in url else '?'
            url = f"{url}{separator}game_id={self.game_id}"

        headers = {'Content-Type': 'application/json'}

        req = request.Request(url, method=method, headers=headers)
        if data:
            # Add game_id to POST request body
            if self.game_id and 'game_id' not in data:
                data['game_id'] = self.game_id
            req.data = json.dumps(data).encode('utf-8')

        try:
            with request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        except error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            try:
                error_json = json.loads(error_body)
                raise Exception(f"HTTP {e.code}: {error_json.get('detail', error_body)}")
            except json.JSONDecodeError:
                raise Exception(f"HTTP {e.code}: {error_body}")

    def sync_local_board(self) -> None:
        """
        Synchronize local board state with server using FEN.

        :raises Exception: If sync fails
        """
        board_state = self.make_request('/board')
        fen = board_state['fen']
        self.local_board.set_fen(fen)

    def evaluate_position(self, board: chess.Board) -> int:
        """
        Evaluate board position from white's perspective.

        Combines material value with piece-square table positional bonuses.

        :param board: chess.Board object
        :type board: chess.Board
        :return: Position score (positive favors white, negative favors black)
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

    def order_moves(self, moves: List[str]) -> List[str]:
        """
        Order moves for better alpha-beta pruning (captures first, center control).

        :param moves: List of legal moves in SAN
        :type moves: List[str]
        :return: Ordered list of moves
        :rtype: List[str]
        """
        captures = []
        center_moves = []
        other_moves = []

        center_squares = {'e4', 'e5', 'd4', 'd5', 'Nf3', 'Nc3', 'Nf6', 'Nc6'}

        for move in moves:
            if 'x' in move:
                captures.append(move)
            elif move in center_squares or any(sq in move for sq in ['e4', 'e5', 'd4', 'd5']):
                center_moves.append(move)
            else:
                other_moves.append(move)

        return captures + center_moves + other_moves

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
        ordered_moves = self._order_moves_internal(board, legal_moves)
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

    def _order_moves_internal(self, board: chess.Board, moves: List[chess.Move]) -> List[chess.Move]:
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

    def choose_move(self, legal_moves: List[str]) -> str:
        """
        Choose the best move using iterative deepening with minimax search.

        :param legal_moves: List of legal moves in SAN (from server)
        :type legal_moves: List[str]
        :return: Selected move in SAN
        :rtype: str
        """
        if not legal_moves:
            raise Exception("No legal moves available")

        if len(legal_moves) == 1:
            return legal_moves[0]

        # Sync local board with server
        self.sync_local_board()

        start_time = time.time()
        best_move_san = legal_moves[0]
        self.nodes_searched = 0

        maximizing = self.player_color == 'white'

        # Iterative deepening
        for depth in range(1, 20):
            if time.time() - start_time > self.search_time * 0.9:
                break

            try:
                # Copy board for this depth's search
                search_board = self.local_board.copy()

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
                    best_move_san = self.local_board.san(best_move_obj)

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

    def run(self) -> None:
        """
        Main game loop - poll server and make moves when it's our turn.

        :raises Exception: If critical errors occur
        """
        console.print("[bold green]♟ Chess client started[/bold green]")
        console.print(f"[cyan]Playing as:[/cyan] [bold]{self.player_color}[/bold]")
        console.print(f"[cyan]Search time:[/cyan] {self.search_time}s")
        console.print(f"[cyan]Server:[/cyan] {self.server_url}")

        # Create new game if no game_id provided
        if not self.game_id:
            response = self.make_request('/newgame', 'POST')
            self.game_id = response['game_id']
            console.print(f"[green]✓[/green] Created new game: [bold]{self.game_id}[/bold]")
        else:
            console.print(f"[yellow]↻[/yellow] Joining game: [bold]{self.game_id}[/bold]")

        # Initial sync with server
        self.sync_local_board()
        console.print("[green]✓[/green] Board synced with server")

        move_count = 0

        while True:
            try:
                # Check turn
                turn_response = self.make_request('/turn')

                # Check if game is over from turn response
                if turn_response.get('game_over', False):
                    console.print("\n[bold red]Game over![/bold red]")
                    reason = turn_response.get('game_over_reason', 'Unknown reason')
                    console.print(f"[yellow]Reason:[/yellow] {reason}")
                    # Get final board state
                    board_state = self.make_request('/board')
                    print(board_state.get('rendered', ''))
                    break

                current_turn = turn_response['turn']

                if current_turn == self.player_color:
                    # Get board state
                    board_state = self.make_request('/board')

                    if board_state.get('game_over', False):
                        console.print("\n[bold red]Game over![/bold red]")
                        reason = board_state.get('game_over_reason', 'Unknown reason')
                        console.print(f"[yellow]Reason:[/yellow] {reason}")
                        print(board_state.get('rendered', ''))
                        break

                    # Get legal moves
                    legal_moves_response = self.make_request('/legal-moves')
                    legal_moves = legal_moves_response['legal_moves']

                    if not legal_moves:
                        console.print("[bold red]No legal moves available - game over[/bold red]")
                        break

                    console.print(f"\n[bold magenta]━━━ Move {move_count + 1} ({self.player_color}) ━━━[/bold magenta]")
                    console.print(f"[dim]Legal moves ({len(legal_moves)}):[/dim] {', '.join(legal_moves[:10])}...")

                    # Choose move
                    move_start = time.time()
                    chosen_move = self.choose_move(legal_moves)
                    move_time = time.time() - move_start

                    console.print(
                        f"[bold green]➜ Chosen move:[/bold green] [bold white]{chosen_move}[/bold white] "
                        f"[dim](time: {move_time:.2f}s)[/dim]"
                    )

                    # Submit move
                    response = self.make_request('/move', 'POST', {
                        'move': chosen_move,
                        'player': self.player_color
                    })

                    # Update local board with our move
                    move_obj = self.local_board.parse_san(chosen_move)
                    self.local_board.push(move_obj)

                    console.print(f"\n[bold cyan]Game: {self.game_id}[/bold cyan] [dim](waiting for opponent)[/dim]")
                    print(response.get('rendered', ''))

                    move_count += 1
                else:
                    # Not our turn - sync to catch opponent's move
                    self.sync_local_board()

                time.sleep(0.5)

            except KeyboardInterrupt:
                console.print("\n[yellow]⚠ Client stopped by user[/yellow]")
                break
            except Exception as e:
                console.print(f"[red]✗ Error:[/red] {e}")
                time.sleep(1)


def main() -> None:
    """
    Parse command-line arguments and start the chess client.
    """
    parser = argparse.ArgumentParser(description='Chess Arena Client')
    parser.add_argument('--player', choices=['w', 'b', 'W', 'B', 'white', 'black'],
                        required=True, help='Player color (w/W/white or b/B/black)')
    parser.add_argument('--search-time', type=float, default=5.0,
                        help='Maximum search time per move in seconds (default: 5.0)')
    parser.add_argument('--port', type=int, default=9002,
                        help='Server port (default: 9002)')
    parser.add_argument('--game-id', type=str, default=None,
                        help='Game ID to join existing game (if not provided, creates new game)')

    args = parser.parse_args()

    # Normalize player color
    player_color = 'white' if args.player.lower() in ['w', 'white'] else 'black'

    server_url = f"http://localhost:{args.port}"

    client = ChessClient(server_url, player_color, args.search_time, args.game_id)
    client.run()


if __name__ == '__main__':
    main()
