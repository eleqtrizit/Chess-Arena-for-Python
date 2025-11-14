#!/usr/bin/env python3
"""
Chess client for Chess Arena server.

Uses minimax search with alpha-beta pruning, iterative deepening,
and piece-square table evaluation.
"""

import argparse
import asyncio
import glob
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chess
import websockets
from rich.console import Console

console = Console()


def load_auth_from_file(file_path: str) -> Optional[Tuple[str, str, str, str]]:
    """
    Load auth data from a JSON file.

    :param file_path: Path to the auth file
    :type file_path: str
    :return: Tuple of (game_id, player_id, player_color, auth_token) if found, None otherwise
    :rtype: Optional[Tuple[str, str, str, str]]
    """
    try:
        with open(file_path, 'r') as f:
            auth_data = json.load(f)

        game_id = auth_data.get("game_id")
        player_id = auth_data.get("player_id")
        player_color = auth_data.get("player_color")
        auth_token = auth_data.get("auth_token")

        if not all([game_id, player_id, player_color, auth_token]):
            console.print(f"[red]Error: Missing required fields in {file_path}[/red]")
            return None

        console.print(f"[cyan]Loaded auth token for player:[/cyan] {player_id}")
        console.print(f"[cyan]Game ID:[/cyan] {game_id}")
        console.print(f"[cyan]Color:[/cyan] {player_color}")
        return game_id, player_id, player_color, auth_token

    except FileNotFoundError:
        console.print(f"[red]Error: Auth file not found: {file_path}[/red]")
        return None
    except json.JSONDecodeError:
        console.print(f"[red]Error: Invalid JSON in auth file: {file_path}[/red]")
        return None
    except Exception as e:
        console.print(f"[red]Error reading auth file:[/red] {e}")
        return None


def get_latest_auth() -> Optional[Tuple[str, str, str, str]]:
    """
    Find and load the most recent auth token file.

    :return: Tuple of (game_id, player_id, player_color, auth_token) if found, None otherwise
    :rtype: Optional[Tuple[str, str, str, str]]
    """
    auth_files = glob.glob(".*_auth")
    if not auth_files:
        return None

    # Sort by modification time, newest first
    auth_files.sort(key=os.path.getmtime, reverse=True)
    latest_file = auth_files[0]

    try:
        # Parse filename: .{player_id}_{game_id}_{color}_{auth_token}_auth
        filename = Path(latest_file).name
        if not filename.startswith('.') or not filename.endswith('_auth'):
            return None

        # Remove leading '.' and trailing '_auth'
        content = filename[1:-5]
        parts = content.split('_', 3)

        if len(parts) != 4:
            return None

        player_id, game_id, player_color, auth_token = parts
        console.print(f"[cyan]Found auth token for player:[/cyan] {player_id}")
        console.print(f"[cyan]Game ID:[/cyan] {game_id}")
        console.print(f"[cyan]Color:[/cyan] {player_color}")
        return game_id, player_id, player_color, auth_token

    except Exception as e:
        console.print(f"[red]Error reading auth file:[/red] {e}")
        return None


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

    :param server_url: Base WebSocket URL of the Chess Arena server
    :type server_url: str
    :param search_time: Maximum time in seconds for move search
    :type search_time: float
    :param continue_game: Whether to continue from an existing game
    :type continue_game: bool
    :param auth_file: Optional path to JSON file for storing/loading auth token
    :type auth_file: Optional[str]
    """

    def __init__(self, server_url: str, search_time: float, continue_game: bool = False,
                 auth_file: Optional[str] = None):
        self.server_url = server_url.replace('http://', 'ws://').replace('https://', 'wss://')
        self.search_time = search_time
        self.continue_game = continue_game
        self.auth_file = auth_file
        self.game_id: Optional[str] = None
        self.player_id: Optional[str] = None
        self.auth_token: Optional[str] = None
        self.player_color: Optional[str] = None
        self.nodes_searched = 0
        self.local_board = chess.Board()
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.message_queue: asyncio.Queue = asyncio.Queue()

    async def send_message(self, message: Dict[str, Any]) -> None:
        """
        Send a message via WebSocket.

        :param message: Message dictionary to send
        :type message: Dict[str, Any]
        """
        if self.websocket:
            await self.websocket.send(json.dumps(message))

    async def receive_messages(self) -> None:
        """
        Background task to receive messages from WebSocket.

        :raises Exception: If WebSocket connection fails
        """
        if not self.websocket:
            return

        try:
            async for message in self.websocket:
                data = json.loads(message)
                await self.message_queue.put(data)
        except websockets.exceptions.ConnectionClosed:
            console.print("[red]✗ Connection to server closed[/red]")

    def save_auth_token(self) -> None:
        """
        Save auth token to file for reconnection.

        :raises Exception: If save fails
        """
        if not all([self.player_id, self.game_id, self.player_color, self.auth_token]):
            return

        if self.auth_file:
            # Save as JSON to custom file
            auth_data = {
                "game_id": self.game_id,
                "player_id": self.player_id,
                "player_color": self.player_color,
                "auth_token": self.auth_token
            }
            try:
                with open(self.auth_file, 'w') as f:
                    json.dump(auth_data, f, indent=2)
                console.print(f"[green]✓[/green] Auth token saved to {self.auth_file}")
            except Exception as e:
                console.print(f"[yellow]⚠ Failed to save auth token:[/yellow] {e}")
        else:
            # Legacy: save as empty file with encoded filename
            filename = f".{self.player_id}_{self.game_id}_{self.player_color}_{self.auth_token}_auth"
            try:
                Path(filename).touch()
                console.print(f"[green]✓[/green] Auth token saved to {filename}")
            except Exception as e:
                console.print(f"[yellow]⚠ Failed to save auth token:[/yellow] {e}")

    async def sync_board_state(self) -> bool:
        """
        Request and sync current board state from server.

        :return: True if it's our turn after syncing, False otherwise
        :rtype: bool
        :raises Exception: If sync fails
        """
        await self.send_message({
            "type": "get_board",
            "game_id": self.game_id,
            "player_id": self.player_id,
            "auth_token": self.auth_token
        })

        # Wait for board_state response
        while True:
            msg = await self.message_queue.get()
            if msg.get("type") == "board_state":
                fen = msg.get("fen")
                if fen:
                    self.local_board.set_fen(fen)
                current_turn = msg.get("current_turn")
                # Check if it's our turn
                is_our_turn = current_turn == self.player_color
                return is_our_turn
            elif msg.get("type") == "error":
                raise Exception(f"Board sync error: {msg.get('message')}")
            await self.message_queue.put(msg)  # Put back if not for us
            await asyncio.sleep(0.01)

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

    async def run(self) -> None:
        """
        Main game loop - join queue via WebSocket, wait for opponent, and make moves.

        :raises Exception: If critical errors occur
        """
        console.print("[bold green]♟ Chess client started[/bold green]")
        console.print(f"[cyan]Search time:[/cyan] {self.search_time}s")
        console.print(f"[cyan]Server:[/cyan] {self.server_url}")

        try:
            async with websockets.connect(self.server_url + "/ws") as websocket:
                self.websocket = websocket

                # Start background task to receive messages
                receive_task = asyncio.create_task(self.receive_messages())

                # If continuing a game, skip matchmaking
                if self.continue_game and self.game_id and self.player_id and self.auth_token:
                    console.print("\n[green]✓ Reconnecting to existing game...[/green]")
                    console.print(f"[cyan]Game ID:[/cyan] [bold]{self.game_id}[/bold]")
                    console.print(f"[cyan]Player ID:[/cyan] [bold]{self.player_id}[/bold]")
                    match_found = True
                else:
                    # Join matchmaking queue
                    console.print("\n[yellow]⏳ Joining matchmaking queue...[/yellow]")
                    console.print("[dim]Waiting for opponent...[/dim]")

                    await self.send_message({"type": "join_queue"})

                    # Wait for match
                    match_found = False

                while not match_found:
                    msg = await self.message_queue.get()
                    msg_type = msg.get("type")

                    if msg_type == "match_found":
                        self.game_id = msg["game_id"]
                        self.player_id = msg["player_id"]
                        self.auth_token = msg["auth_token"]
                        self.player_color = msg["assigned_color"]
                        first_move_player = msg["first_move"]

                        console.print("[green]✓ Match found![/green]")
                        console.print(f"[cyan]Game ID:[/cyan] [bold]{self.game_id}[/bold]")
                        console.print(f"[cyan]Player ID:[/cyan] [bold]{self.player_id}[/bold]")
                        console.print(f"[cyan]Color:[/cyan] [bold]{self.player_color}[/bold]")

                        # Save auth token for reconnection
                        self.save_auth_token()

                        if self.player_id == first_move_player:
                            console.print("[green]You move first (White)[/green]")
                        else:
                            console.print("[yellow]Opponent moves first (White)[/yellow]")

                        match_found = True

                    elif msg_type == "queue_timeout":
                        console.print("[red]✗ Queue timeout, retrying...[/red]")
                        await asyncio.sleep(1)
                        await self.send_message({"type": "join_queue"})

                # Sync board state
                is_our_turn = await self.sync_board_state()
                console.print("[green]✓[/green] Board synced with server")

                # Main game loop
                move_count = 0
                game_over = False

                # If reconnecting and it's our turn, make a move
                if self.continue_game and is_our_turn and not self.local_board.is_game_over():
                    legal_moves = [self.local_board.san(m) for m in self.local_board.legal_moves]
                    if legal_moves:
                        console.print(
                            f"\n[bold magenta]━━━ Move {move_count + 1} ({self.player_color}) ━━━[/bold magenta]")
                        console.print(f"[cyan]Game ID:[/cyan] [bold]{self.game_id}[/bold]")
                        console.print(f"[cyan]Client:[/cyan] [bold]{self.player_id}[/bold]")
                        console.print(f"[dim]Legal moves ({len(legal_moves)}):[/dim] {', '.join(legal_moves[:10])}...")

                        move_start = time.time()
                        chosen_move = self.choose_move(legal_moves)
                        move_time = time.time() - move_start

                        console.print(
                            f"[bold green]➜ Chosen move:[/bold green] "
                            f"[bold white]{chosen_move}[/bold white] [dim](time: {move_time:.2f}s)[/dim]"
                        )

                        await self.send_message({
                            "type": "make_move",
                            "data": {
                                "game_id": self.game_id,
                                "player_id": self.player_id,
                                "auth_token": self.auth_token,
                                "move": chosen_move
                            }
                        })

                        move_count += 1

                while not game_over:
                    try:
                        msg = await asyncio.wait_for(self.message_queue.get(), timeout=0.1)
                        msg_type = msg.get("type")

                        if msg_type == "move_made":
                            # Update local board
                            fen = msg.get("fen")
                            if fen:
                                self.local_board.set_fen(fen)

                            rendered = msg.get("rendered", "")
                            if rendered:
                                print("\n" + rendered)

                            if msg.get("game_over"):
                                console.print("\n[bold red]Game over![/bold red]")
                                reason = msg.get("game_over_reason", "Unknown")
                                console.print(f"[yellow]Reason:[/yellow] {reason}")

                                # Determine win/loss
                                if "checkmate" in reason.lower():
                                    # After checkmate, board.turn is the losing side
                                    losing_color = "white" if self.local_board.turn else "black"
                                    if losing_color == self.player_color:
                                        console.print("[bold red]I lost :([/bold red]")
                                    else:
                                        console.print("[bold green]I won :)[/bold green]")
                                elif "stalemate" in reason.lower() or "draw" in reason.lower():
                                    console.print("[yellow]Draw[/yellow]")

                                game_over = True
                                continue

                            # Check if it's our turn
                            if not self.local_board.is_game_over():
                                current_turn = "white" if self.local_board.turn else "black"
                                if current_turn == self.player_color:
                                    # Our turn - make a move
                                    legal_moves = [self.local_board.san(m) for m in self.local_board.legal_moves]

                                    if not legal_moves:
                                        console.print("[bold red]No legal moves - game over[/bold red]")
                                        game_over = True
                                        continue

                                    console.print(
                                        f"\n[bold magenta]━━━ Move {move_count + 1} "
                                        f"({self.player_color}) ━━━[/bold magenta]"
                                    )
                                    console.print(f"[cyan]Game ID:[/cyan] [bold]{self.game_id}[/bold]")
                                    console.print(f"[cyan]Client:[/cyan] [bold]{self.player_id}[/bold]")
                                    moves_preview = ', '.join(legal_moves[:10])
                                    console.print(f"[dim]Legal moves ({len(legal_moves)}):[/dim] {moves_preview}...")

                                    move_start = time.time()
                                    chosen_move = self.choose_move(legal_moves)
                                    move_time = time.time() - move_start

                                    console.print(
                                        f"[bold green]➜ Chosen move:[/bold green] "
                                        f"[bold white]{chosen_move}[/bold white] [dim](time: {move_time:.2f}s)[/dim]"
                                    )

                                    # Send move
                                    await self.send_message({
                                        "type": "make_move",
                                        "data": {
                                            "game_id": self.game_id,
                                            "player_id": self.player_id,
                                            "auth_token": self.auth_token,
                                            "move": chosen_move
                                        }
                                    })

                                    move_count += 1

                        elif msg_type == "opponent_disconnected":
                            console.print("[yellow]⚠ Opponent disconnected - waiting for reconnection...[/yellow]")

                        elif msg_type == "game_over":
                            status = msg.get("status")
                            message = msg.get("message", "Game ended")
                            console.print("\n[bold red]Game over![/bold red]")
                            console.print(f"[yellow]{message}[/yellow]")
                            if status == "forfeit":
                                winner = msg.get("winner")
                                if winner == self.player_id:
                                    console.print("[green]✓ You win by forfeit![/green]")
                                    console.print("[bold green]I won :)[/bold green]")
                                else:
                                    console.print("[red]✗ You lost by forfeit[/red]")
                                    console.print("[bold red]I lost :([/bold red]")
                            game_over = True

                        elif msg_type == "error":
                            error_msg = msg.get("message", "Unknown error")
                            console.print(f"[red]✗ Error:[/red] {error_msg}")

                    except asyncio.TimeoutError:
                        # Check if it's our turn to move initially
                        if self.game_id and not self.local_board.is_game_over():
                            current_turn = "white" if self.local_board.turn else "black"
                            if current_turn == self.player_color and move_count == 0:
                                # Make first move
                                legal_moves = [self.local_board.san(m) for m in self.local_board.legal_moves]

                                console.print(f"\n[bold magenta]━━━ Move 1 ({self.player_color}) ━━━[/bold magenta]")
                                console.print(f"[cyan]Game ID:[/cyan] [bold]{self.game_id}[/bold]")
                                console.print(f"[cyan]Client:[/cyan] [bold]{self.player_id}[/bold]")
                                console.print(
                                    f"[dim]Legal moves ({len(legal_moves)}):[/dim] {', '.join(legal_moves[:10])}...")

                                move_start = time.time()
                                chosen_move = self.choose_move(legal_moves)
                                move_time = time.time() - move_start

                                console.print(
                                    f"[bold green]➜ Chosen move:[/bold green] [bold white]{chosen_move}[/bold white] "
                                    f"[dim](time: {move_time:.2f}s)[/dim]"
                                )

                                await self.send_message({
                                    "type": "make_move",
                                    "data": {
                                        "game_id": self.game_id,
                                        "player_id": self.player_id,
                                        "auth_token": self.auth_token,
                                        "move": chosen_move
                                    }
                                })

                                move_count += 1
                        continue

                receive_task.cancel()

        except KeyboardInterrupt:
            console.print("\n[yellow]⚠ Client stopped by user[/yellow]")
        except Exception as e:
            console.print(f"[red]✗ Connection error:[/red] {e}")


def main() -> None:
    """
    Parse command-line arguments and start the chess client.
    """
    parser = argparse.ArgumentParser(description='Chess Arena Client - WebSocket Edition')
    parser.add_argument('--search-time', type=float, default=5.0,
                        help='Maximum search time per move in seconds (default: 5.0)')
    parser.add_argument('--port', type=int, default=9002,
                        help='Server port (default: 9002)')
    parser.add_argument('--continue', dest='continue_game', action='store_true',
                        help='Continue from the most recent saved game using auth token')
    parser.add_argument('--auth-file', type=str, default=None,
                        help='Path to file for storing/loading auth token (JSON format)')

    args = parser.parse_args()

    server_url = f"http://localhost:{args.port}"

    # If --continue flag is set, try to load auth token
    if args.continue_game:
        # Load from custom file if specified, otherwise use legacy method
        if args.auth_file:
            auth_data = load_auth_from_file(args.auth_file)
        else:
            auth_data = get_latest_auth()

        if auth_data:
            game_id, player_id, player_color, auth_token = auth_data
            console.print(f"[green]✓ Continuing as player {player_id}[/green]")
            # Create client with loaded auth data
            client = ChessClient(server_url, args.search_time, continue_game=True, auth_file=args.auth_file)
            client.game_id = game_id
            client.player_id = player_id
            client.player_color = player_color
            client.auth_token = auth_token
            asyncio.run(client.run())
        else:
            console.print("[red]✗ No saved auth token found. Starting new game instead.[/red]")
            client = ChessClient(server_url, args.search_time, auth_file=args.auth_file)
            asyncio.run(client.run())
    else:
        client = ChessClient(server_url, args.search_time, auth_file=args.auth_file)
        asyncio.run(client.run())


if __name__ == '__main__':
    main()
