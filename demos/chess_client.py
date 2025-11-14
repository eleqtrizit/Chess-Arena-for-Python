#!/usr/bin/env python3
"""
Chess client for Chess Arena server.

Handles WebSocket communication, matchmaking, and game management.
Strategy for move selection is injected as a dependency.
"""

import argparse
import asyncio
import glob
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import chess
import websockets
from rich.console import Console
from strategy import Strategy
from strategy_base import StrategyBase

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


class ChessClient:
    """
    Chess client for WebSocket-based Chess Arena server.

    Handles connection management, matchmaking, and game state synchronization.
    Move selection is delegated to an injected Strategy implementation.

    :param server_url: Base WebSocket URL of the Chess Arena server
    :type server_url: str
    :param strategy: Strategy implementation for move selection
    :type strategy: StrategyBase
    :param continue_game: Whether to continue from an existing game
    :type continue_game: bool
    :param auth_file: Optional path to JSON file for storing/loading auth token
    :type auth_file: Optional[str]
    """

    def __init__(self, server_url: str, strategy: StrategyBase, continue_game: bool = False,
                 auth_file: Optional[str] = None):
        self.server_url = server_url.replace('http://', 'ws://').replace('https://', 'wss://')
        self.strategy = strategy
        self.continue_game = continue_game
        self.auth_file = auth_file
        self.game_id: Optional[str] = None
        self.player_id: Optional[str] = None
        self.auth_token: Optional[str] = None
        self.player_color: Optional[str] = None
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

    async def run(self) -> None:
        """
        Main game loop - join queue via WebSocket, wait for opponent, and make moves.

        :raises Exception: If critical errors occur
        """
        console.print("[bold green]♟ Chess client started[/bold green]")
        console.print(f"[cyan]Search time:[/cyan] {self.strategy.search_time}s")
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
                        chosen_move = self.strategy.choose_move(self.local_board, legal_moves, self.player_color)
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
                                    chosen_move = self.strategy.choose_move(
                                        self.local_board, legal_moves, self.player_color)
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
                                chosen_move = self.strategy.choose_move(
                                    self.local_board, legal_moves, self.player_color)
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

    # Create strategy instance
    strategy = Strategy(search_time=args.search_time)

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
            client = ChessClient(server_url, strategy, continue_game=True, auth_file=args.auth_file)
            client.game_id = game_id
            client.player_id = player_id
            client.player_color = player_color
            client.auth_token = auth_token
            asyncio.run(client.run())
        else:
            console.print("[red]✗ No saved auth token found. Starting new game instead.[/red]")
            client = ChessClient(server_url, strategy, auth_file=args.auth_file)
            asyncio.run(client.run())
    else:
        client = ChessClient(server_url, strategy, auth_file=args.auth_file)
        asyncio.run(client.run())


if __name__ == '__main__':
    main()
