"""FastAPI server for chess arena application."""

import asyncio
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from chess_arena.board import ChessBoard
from chess_arena.connection_manager import ConnectionManager
from chess_arena.game_session import GameSessionManager
from chess_arena.persistence import load_games, log_game_state, save_games
from chess_arena.queue import MatchmakingQueue
from chess_arena.renderer import BoardRenderer

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="Chess Arena API", version="1.0.0")
games: Dict[str, ChessBoard] = {}
connection_manager = ConnectionManager()
matchmaking_queue = MatchmakingQueue(connection_manager)
game_session_manager = GameSessionManager(connection_manager)
move_start_times: Dict[str, Dict[str, float]] = {}  # {game_id: {player_id: timestamp}}
game_creation_times: Dict[str, float] = {}  # {game_id: timestamp}

# Server-enforced search time (optional)
SERVER_SEARCH_TIME: Optional[float] = None
if "SEARCH_TIME" in os.environ and os.environ["SEARCH_TIME"] != "None":
    SERVER_SEARCH_TIME = float(os.environ["SEARCH_TIME"])

# Matchmaking queue timeout configuration
MATCHMAKING_TIMEOUT: Optional[float] = 60.0  # Default 60 seconds
if "MATCHMAKING_TIMEOUT" in os.environ:
    timeout_str = os.environ["MATCHMAKING_TIMEOUT"]
    if timeout_str.lower() == "none":
        MATCHMAKING_TIMEOUT = None  # No timeout
    else:
        MATCHMAKING_TIMEOUT = float(timeout_str)


def get_game_board(game_id: str) -> ChessBoard:
    """
    Retrieve a game board by game ID.

    :param game_id: The unique game identifier
    :type game_id: str
    :return: ChessBoard instance for the game
    :rtype: ChessBoard
    :raises HTTPException: If game_id is not found
    """
    if game_id not in games:
        raise HTTPException(status_code=404, detail=f"Game '{game_id}' not found")
    return games[game_id]


def print_board(game_board: ChessBoard, game_id: str) -> None:
    """
    Print the current board state to the terminal.

    :param game_board: ChessBoard instance to print
    :type game_board: ChessBoard
    :param game_id: The game identifier
    :type game_id: str
    """
    board_state = game_board.get_board_state()
    rendered = BoardRenderer.render(board_state)
    print(f"\n[Game: {game_id}]")
    print(rendered + "\n")


def persist_games() -> None:
    """Save all game states to disk."""
    save_games(games)


@app.on_event("startup")
def on_startup() -> None:
    """Handle application startup event."""
    global games
    logger.debug("Starting Chess Arena server")
    games = load_games()
    loaded_count = len(games)
    logger.debug(f"Loaded {loaded_count} persisted game(s)")

    print("\n" + "=" * 50)
    print("Chess Arena Server Started")
    print("Multi-game support enabled")
    print(f"Loaded {loaded_count} persisted game(s)")

    if SERVER_SEARCH_TIME is not None:
        print(f"Search time limit enforced: {SERVER_SEARCH_TIME}s per move")

    print("=" * 50)
    logger.debug("Chess Arena server started successfully")


class NewGameResponse(BaseModel):
    """
    Response model for new game creation.

    :param game_id: Unique identifier for the new game
    :type game_id: str
    """

    game_id: str


class MoveRequest(BaseModel):
    """
    Request model for making a chess move.

    :param game_id: The game identifier
    :type game_id: str
    :param move: Move in standard algebraic notation
    :type move: str
    :param player_id: Player ID making the move (for matchmade games)
    :type player_id: Optional[str]
    :param player: Player color making the move (for non-matchmade games, 'white' or 'black')
    :type player: Optional[str]
    """

    game_id: str
    move: str
    player_id: Optional[str] = None
    player: Optional[str] = None


class ReplayRequest(BaseModel):
    """
    Request model for replaying a PGN game.

    :param game_id: The game identifier
    :type game_id: str
    :param pgn: PGN notation string containing the game moves
    :type pgn: str
    """

    game_id: str
    pgn: str


class ResetRequest(BaseModel):
    """
    Request model for resetting a game.

    :param game_id: The game identifier
    :type game_id: str
    """

    game_id: str


class BoardResponse(BaseModel):
    """
    Response model for board state.

    :param board: 8x8 grid representation of the board
    :type board: List[List[str]]
    :param rendered: Text-based rendering of the board
    :type rendered: str
    :param fen: FEN notation of the current position
    :type fen: str
    :param game_over: Whether the game has ended
    :type game_over: bool
    :param game_over_reason: Reason for game over (empty string if not over)
    :type game_over_reason: str
    """

    board: List[List[str]]
    rendered: str
    fen: str
    game_over: bool
    game_over_reason: str


class CoordinatesResponse(BaseModel):
    """
    Response model for piece coordinates.

    :param coordinates: Mapping of square names to piece symbols
    :type coordinates: Dict[str, str]
    """

    coordinates: Dict[str, str]


class TurnResponse(BaseModel):
    """
    Response model for current turn.

    :param turn: Current player's turn ('white' or 'black')
    :type turn: str
    :param game_over: Whether the game has ended
    :type game_over: bool
    :param game_over_reason: Reason for game over (empty string if not over)
    :type game_over_reason: str
    """

    turn: str
    game_over: bool
    game_over_reason: str


class LegalMovesResponse(BaseModel):
    """
    Response model for legal moves.

    :param legal_moves: List of legal moves in algebraic notation
    :type legal_moves: List[str]
    """

    legal_moves: List[str]


class QueueResponse(BaseModel):
    """
    Response model for queue matchmaking.

    :param game_id: Unique identifier for the created game
    :type game_id: str
    :param player_id: Unique identifier for this player
    :type player_id: str
    :param assigned_color: Color assigned to this player ('white' or 'black')
    :type assigned_color: str
    :param first_move: Player ID of the player who moves first
    :type first_move: str
    :param no_challengers: True if timeout occurred with no opponent
    :type no_challengers: Optional[bool]
    """

    game_id: Optional[str] = None
    player_id: Optional[str] = None
    assigned_color: Optional[str] = None
    first_move: Optional[str] = None
    no_challengers: Optional[bool] = None


@app.post("/newgame", response_model=NewGameResponse)
def create_new_game() -> NewGameResponse:
    """
    Create a new chess game.

    :return: New game identifier
    :rtype: NewGameResponse
    """
    game_id = str(uuid.uuid4())
    games[game_id] = ChessBoard()
    persist_games()
    print(f"\n[New game created: {game_id}]")
    return NewGameResponse(game_id=game_id)


# Old HTTP queue endpoint - replaced by WebSocket /ws endpoint
# Kept for backward compatibility but requires connection_id parameter
# Clients should use WebSocket connection for proper matchmaking


@app.get("/board", response_model=BoardResponse)
def get_board(game_id: str) -> BoardResponse:
    """
    Get the current state of the chess board.

    :param game_id: The game identifier
    :type game_id: str
    :return: Current board state with rendering
    :rtype: BoardResponse
    """
    game_board = get_game_board(game_id)
    board_state = game_board.get_board_state()
    rendered = BoardRenderer.render(board_state)
    return BoardResponse(
        board=board_state,
        rendered=rendered,
        fen=game_board.get_fen(),
        game_over=game_board.is_game_over(),
        game_over_reason=game_board.get_game_over_reason()
    )


@app.get("/coordinates", response_model=CoordinatesResponse)
def get_coordinates(game_id: str) -> CoordinatesResponse:
    """
    Get all piece coordinates on the board.

    :param game_id: The game identifier
    :type game_id: str
    :return: Dictionary of square coordinates to piece symbols
    :rtype: CoordinatesResponse
    """
    game_board = get_game_board(game_id)
    coordinates = game_board.get_all_coordinates()
    return CoordinatesResponse(coordinates=coordinates)


@app.get("/turn", response_model=TurnResponse)
def get_turn(game_id: str) -> TurnResponse:
    """
    Get whose turn it is to move.

    :param game_id: The game identifier
    :type game_id: str
    :return: Current player's turn with game over status
    :rtype: TurnResponse
    """
    game_board = get_game_board(game_id)
    turn = game_board.get_current_turn()
    return TurnResponse(
        turn=turn,
        game_over=game_board.is_game_over(),
        game_over_reason=game_board.get_game_over_reason()
    )


@app.get("/legal-moves", response_model=LegalMovesResponse)
def get_legal_moves(game_id: str) -> LegalMovesResponse:
    """
    Get all legal moves in the current position.

    :param game_id: The game identifier
    :type game_id: str
    :return: List of legal moves in algebraic notation
    :rtype: LegalMovesResponse
    """
    game_board = get_game_board(game_id)
    legal_moves = game_board.get_legal_moves()
    return LegalMovesResponse(legal_moves=legal_moves)


@app.post("/move", response_model=BoardResponse)
def make_move(move_request: MoveRequest) -> BoardResponse:
    """
    Make a move on the chess board.

    :param move_request: Move request containing game_id and algebraic notation
    :type move_request: MoveRequest
    :return: Updated board state
    :rtype: BoardResponse
    :raises HTTPException: If the move is invalid or wrong player's turn
    """
    game_board = get_game_board(move_request.game_id)
    current_turn = game_board.get_current_turn()

    # Validate turn - support both player_id (matchmade games) and player color (non-matchmade games)
    if move_request.player_id:
        # Matchmade game - use player_id
        if not game_board.is_players_turn(move_request.player_id):
            player_color = game_board.get_player_color(move_request.player_id)
            if player_color is None:
                raise HTTPException(
                    status_code=403,
                    detail=f"Player ID '{move_request.player_id}' is not part of this game"
                )
            raise HTTPException(
                status_code=403,
                detail=f"It is {current_turn}'s turn, not your turn (you are {player_color})"
            )
    elif move_request.player:
        # Non-matchmade game - use color directly (backward compatibility)
        if move_request.player != current_turn:
            raise HTTPException(
                status_code=403,
                detail=f"It is {current_turn}'s turn, not {move_request.player}'s turn"
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="Either player_id or player must be provided"
        )

    # Log game state before move
    legal_moves = game_board.get_legal_moves()
    log_game_state(game_board.board, legal_moves, current_turn)

    success = game_board.make_move(move_request.move)
    if not success:
        legal_moves = game_board.get_legal_moves()
        fen = game_board.get_fen()
        detail_msg = (
            f"ILLEGAL MOVE ATTEMPTED: '{move_request.move}' | "
            f"Position: {fen} | "
            f"Legal moves ({len(legal_moves)}): {', '.join(legal_moves[:20])}"
            f"{'...' if len(legal_moves) > 20 else ''}"
        )
        raise HTTPException(status_code=400, detail=detail_msg)

    persist_games()
    print(f"\n[Game: {move_request.game_id}] Move: {move_request.move}")
    print_board(game_board, move_request.game_id)

    board_state = game_board.get_board_state()
    rendered = BoardRenderer.render(board_state)
    return BoardResponse(
        board=board_state,
        rendered=rendered,
        fen=game_board.get_fen(),
        game_over=game_board.is_game_over(),
        game_over_reason=game_board.get_game_over_reason()
    )


@app.post("/replay", response_model=BoardResponse)
def replay_game(replay_request: ReplayRequest) -> BoardResponse:
    """
    Replay a chess game from PGN notation.

    :param replay_request: Request containing game_id and PGN notation
    :type replay_request: ReplayRequest
    :return: Final board state after replay
    :rtype: BoardResponse
    :raises HTTPException: If PGN replay fails
    """
    game_board = get_game_board(replay_request.game_id)
    success = game_board.replay_pgn(replay_request.pgn)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to replay PGN")

    persist_games()
    print(f"\n[Game: {replay_request.game_id}] PGN Game Replayed")
    print_board(game_board, replay_request.game_id)

    board_state = game_board.get_board_state()
    rendered = BoardRenderer.render(board_state)
    return BoardResponse(
        board=board_state,
        rendered=rendered,
        fen=game_board.get_fen(),
        game_over=game_board.is_game_over(),
        game_over_reason=game_board.get_game_over_reason()
    )


@app.post("/reset", response_model=BoardResponse)
def reset_board(reset_request: ResetRequest) -> BoardResponse:
    """
    Reset the chess board to the starting position.

    :param reset_request: Request containing game_id
    :type reset_request: ResetRequest
    :return: Board state at starting position
    :rtype: BoardResponse
    """
    game_board = get_game_board(reset_request.game_id)
    game_board.reset()
    persist_games()

    print(f"\n[Game: {reset_request.game_id}] Board Reset to Starting Position")
    print_board(game_board, reset_request.game_id)

    board_state = game_board.get_board_state()
    rendered = BoardRenderer.render(board_state)
    return BoardResponse(
        board=board_state,
        rendered=rendered,
        fen=game_board.get_fen(),
        game_over=game_board.is_game_over(),
        game_over_reason=game_board.get_game_over_reason()
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time chess game communication.

    Handles matchmaking, moves, and disconnect notifications.

    :param websocket: WebSocket connection
    :type websocket: WebSocket
    """
    connection_id = await connection_manager.connect(websocket)
    player_id: Optional[str] = None
    game_id: Optional[str] = None

    try:
        while True:
            try:
                data = await websocket.receive_json()
            except (RuntimeError, WebSocketDisconnect):
                # WebSocket disconnected while receiving
                raise WebSocketDisconnect()

            message_type = data.get("type")

            if message_type == "join_queue":
                logger.debug(f"[WS:{connection_id}] Joining matchmaking queue")
                # Join matchmaking queue
                try:
                    match_result = await matchmaking_queue.join_queue(connection_id, timeout=MATCHMAKING_TIMEOUT)
                except asyncio.CancelledError:
                    logger.debug(f"[WS:{connection_id}] WebSocket disconnected while in queue")
                    # WebSocket disconnected while in queue
                    raise WebSocketDisconnect()

                if match_result is None:
                    logger.debug(f"[WS:{connection_id}] No opponent found in queue")
                    await connection_manager.send_message(connection_id, {
                        "type": "queue_timeout",
                        "message": "No opponent found"
                    })
                else:
                    # Match found - perform health checks on both players before proceeding
                    game_id = match_result.game_id
                    player_id = match_result.player_id
                    logger.debug(f"[WS:{connection_id}] Match found for game {game_id}, player {player_id}")

                    # Get the waiting player connection ID from the queue entry
                    # The waiting player is the one whose future was set in the queue
                    waiting_player_conn_id = None
                    async with matchmaking_queue.lock:
                        if matchmaking_queue.waiting_player:
                            # This shouldn't happen since we just matched, but let's be safe
                            waiting_player_conn_id = matchmaking_queue.waiting_player.connection_id

                    logger.debug(f"[WS:{connection_id}] Waiting player connection ID: {waiting_player_conn_id}")

                    # Perform health checks on both players (passive check only)
                    players_healthy = True
                    if waiting_player_conn_id:
                        logger.debug(f"[Health Check] Checking health of both players before starting game {game_id}")

                        # Check health of waiting player (passive check)
                        logger.debug(f"[Health Check] Checking health of waiting player {waiting_player_conn_id}")
                        waiting_player_healthy = connection_manager.is_connected(waiting_player_conn_id)
                        if not waiting_player_healthy:
                            logger.debug(f"[Health Check] Waiting player {waiting_player_conn_id} is not healthy")
                            print(f"[Health Check] Waiting player {waiting_player_conn_id} is not healthy")
                            players_healthy = False

                        # Check health of current player (passive check)
                        logger.debug(f"[Health Check] Checking health of current player {connection_id}")
                        current_player_healthy = connection_manager.is_connected(connection_id)
                        if not current_player_healthy:
                            logger.debug(f"[Health Check] Current player {connection_id} is not healthy")
                            print(f"[Health Check] Current player {connection_id} is not healthy")
                            players_healthy = False

                    if not players_healthy:
                        # Cancel the game creation and notify players
                        logger.debug(f"[Health Check] Game {game_id} cancelled due to unhealthy player(s)")
                        print(f"[Health Check] Game {game_id} cancelled due to unhealthy player(s)")

                        # Check if this is a newly created game (within first minute) and delete from history if so
                        if game_id in game_creation_times:
                            creation_time = game_creation_times[game_id]
                            if time.time() - creation_time < 60:  # Within first minute
                                # Remove game from games dictionary and persistence
                                if game_id in games:
                                    logger.debug(
                                        f"[Health Check] Deleting game {game_id} from history "
                                        f"(cancelled within first minute)")
                                    del games[game_id]
                                    del game_creation_times[game_id]
                                    persist_games()
                                    print(
                                        f"[Health Check] Game {game_id} deleted from history "
                                        f"(cancelled within first minute)")

                        await connection_manager.send_message(connection_id, {
                            "type": "error",
                            "message": "Game cancelled - one or more players are not responding"
                        })

                        # Try to notify the waiting player if still connected
                        if waiting_player_conn_id:
                            logger.debug(
                                f"[Health Check] Notifying waiting player {waiting_player_conn_id} "
                                f"of cancellation")
                            await connection_manager.send_message(waiting_player_conn_id, {
                                "type": "error",
                                "message": "Game cancelled - one or more players are not responding"
                            })

                        # Don't create the game, return to queue state
                        logger.debug(f"[Health Check] Returning {connection_id} to queue state")
                        return

                    # Players are healthy, proceed with game creation
                    logger.debug(f"[Health Check] Both players are healthy, creating game {game_id}")
                    print(f"[Health Check] Both players are healthy, creating game {game_id}")

                    # Create the game if it doesn't exist yet
                    if game_id not in games:
                        logger.debug(f"[Game:{game_id}] Creating new matchmade game")
                        games[game_id] = ChessBoard(player_mappings=match_result.player_mappings)
                        game_creation_times[game_id] = time.time()  # Track when the game was created
                        persist_games()
                        print(f"\n[New matchmade game created: {game_id}]")
                        print_board(games[game_id], game_id)

                    # Store connection info
                    logger.debug(f"[WS:{connection_id}] Setting game info: game_id={game_id}, player_id={player_id}")
                    connection_manager.set_game_info(connection_id, game_id, player_id)

                    # Generate auth token for this player
                    auth_token = connection_manager.generate_auth_token(game_id, player_id)
                    logger.debug(f"[WS:{connection_id}] Generated auth token for game {game_id}")

                    # Create game session tracking
                    game_connections = connection_manager.get_game_connections(game_id)
                    logger.debug(f"[Game:{game_id}] Current game connections: {game_connections}")

                    # Always create session, don't wait for 2 connections since we already have a match
                    logger.debug(f"[Game:{game_id}] Creating game session")
                    await game_session_manager.create_session(game_id, {
                        player_id: connection_id  # Add current player
                    })

                    # Add the waiting player to the session if we have their connection ID
                    if waiting_player_conn_id:
                        # We need to get the waiting player's player_id from the match result
                        waiting_player_id = None
                        for pid in match_result.player_mappings.keys():
                            if pid != player_id:
                                waiting_player_id = pid
                                break
                        if waiting_player_id:
                            logger.debug(f"[Game:{game_id}] Adding waiting player {waiting_player_id} to session")
                            # Update the session with both players
                            session = game_session_manager.get_session(game_id)
                            if session:
                                session.player_connections[waiting_player_id] = waiting_player_conn_id

                    # Initialize timer for white's first move if SERVER_SEARCH_TIME is set
                    if SERVER_SEARCH_TIME is not None:
                        white_player_id = match_result.first_move
                        logger.debug(f"[Game:{game_id}] Initializing move timer for white player {white_player_id}")
                        if game_id not in move_start_times:
                            move_start_times[game_id] = {}
                        move_start_times[game_id][white_player_id] = time.time()

                    # Send match found response with auth token
                    match_message: Dict[str, Any] = {
                        "type": "match_found",
                        "game_id": game_id,
                        "player_id": player_id,
                        "auth_token": auth_token,
                        "assigned_color": match_result.assigned_color,
                        "first_move": match_result.first_move
                    }
                    if SERVER_SEARCH_TIME is not None:
                        match_message["server_search_time"] = SERVER_SEARCH_TIME

                    logger.debug(f"[WS:{connection_id}] Sending match_found message: {match_message}")
                    await connection_manager.send_message(connection_id, match_message)

            elif message_type == "make_move":
                # Handle move
                move_data = data.get("data", {})
                move = move_data.get("move")
                move_game_id = move_data.get("game_id")
                move_player_id = move_data.get("player_id")
                move_auth_token = move_data.get("auth_token")

                if not all([move, move_game_id, move_player_id, move_auth_token]):
                    await connection_manager.send_message(connection_id, {
                        "type": "error",
                        "message": "Missing required fields: move, game_id, player_id, auth_token"
                    })
                    continue

                # Validate auth token
                if not connection_manager.validate_auth_token(move_game_id, move_player_id, move_auth_token):
                    await connection_manager.send_message(connection_id, {
                        "type": "error",
                        "message": "Invalid authentication token"
                    })
                    continue

                try:
                    game_board = get_game_board(move_game_id)
                    current_turn = game_board.get_current_turn()

                    # Validate turn
                    if not game_board.is_players_turn(move_player_id):
                        player_color = game_board.get_player_color(move_player_id)
                        await connection_manager.send_message(connection_id, {
                            "type": "error",
                            "message": f"It is {current_turn}'s turn, not your turn (you are {player_color})"
                        })
                        continue

                    # Check time limit if SERVER_SEARCH_TIME is set
                    if SERVER_SEARCH_TIME is not None:
                        # Get the time when this player's turn started
                        if move_game_id in move_start_times and move_player_id in move_start_times[move_game_id]:
                            move_start = move_start_times[move_game_id][move_player_id]
                            move_duration = time.time() - move_start

                            if move_duration > SERVER_SEARCH_TIME:
                                # Time limit violated - disqualify the player
                                print(f"\n[Game: {move_game_id}] TIME VIOLATION: Player {move_player_id} "
                                      f"took {move_duration:.2f}s (limit: {SERVER_SEARCH_TIME}s)")

                                # Determine winner (the other player)
                                player_color = game_board.get_player_color(move_player_id)
                                winner_color = "black" if player_color == "white" else "white"
                                winner_id = None
                                for pid, color in game_board.player_mappings.items():
                                    if color == winner_color:
                                        winner_id = pid
                                        break

                                # Send disqualification message to both players
                                await connection_manager.send_to_game(move_game_id, {
                                    "type": "game_over",
                                    "status": "disqualified",
                                    "winner": winner_id,
                                    "disqualified_player": move_player_id,
                                    "reason": f"Time limit exceeded: {move_duration:.2f}s > {SERVER_SEARCH_TIME}s",
                                    "message": f"Player {move_player_id} disqualified for exceeding time limit"
                                })

                                # Clean up session
                                await game_session_manager.remove_session(move_game_id)

                                # Clean up move tracking
                                if move_game_id in move_start_times:
                                    del move_start_times[move_game_id]

                                continue

                    # Log game state before move
                    legal_moves = game_board.get_legal_moves()
                    log_game_state(game_board.board, legal_moves, current_turn)

                    # Make move
                    success = game_board.make_move(move)
                    if not success:
                        legal_moves = game_board.get_legal_moves()
                        await connection_manager.send_message(connection_id, {
                            "type": "error",
                            "message": f"Illegal move: {move}",
                            "legal_moves": legal_moves
                        })
                        continue

                    persist_games()
                    print(f"\n[Game: {move_game_id}] Move: {move}")
                    print_board(game_board, move_game_id)

                    # Get updated board state
                    board_state = game_board.get_board_state()
                    rendered = BoardRenderer.render(board_state)

                    move_response: Dict[str, Any] = {
                        "type": "move_made",
                        "game_id": move_game_id,
                        "move": move,
                        "board": board_state,
                        "rendered": rendered,
                        "fen": game_board.get_fen(),
                        "game_over": game_board.is_game_over(),
                        "game_over_reason": game_board.get_game_over_reason()
                    }

                    # Record start time for next player's turn if SERVER_SEARCH_TIME is set
                    if SERVER_SEARCH_TIME is not None and not game_board.is_game_over():
                        current_turn = game_board.get_current_turn()
                        # Find the player_id for the current turn
                        next_player_id = None
                        for pid, color in game_board.player_mappings.items():
                            if color == current_turn:
                                next_player_id = pid
                                break
                        if next_player_id:
                            if move_game_id not in move_start_times:
                                move_start_times[move_game_id] = {}
                            move_start_times[move_game_id][next_player_id] = time.time()

                    # Broadcast to both players
                    await connection_manager.send_to_game(move_game_id, move_response)

                except HTTPException as e:
                    await connection_manager.send_message(connection_id, {
                        "type": "error",
                        "message": str(e.detail)
                    })

            elif message_type == "get_board":
                # Get current board state
                board_game_id = data.get("game_id")
                board_player_id = data.get("player_id")
                board_auth_token = data.get("auth_token")

                if not all([board_game_id, board_player_id, board_auth_token]):
                    await connection_manager.send_message(connection_id, {
                        "type": "error",
                        "message": "Missing required fields: game_id, player_id, auth_token"
                    })
                    continue

                # Validate auth token
                if not connection_manager.validate_auth_token(board_game_id, board_player_id, board_auth_token):
                    await connection_manager.send_message(connection_id, {
                        "type": "error",
                        "message": "Invalid authentication token"
                    })
                    continue

                # Re-register this connection with the game (handles reconnection)
                connection_manager.set_game_info(connection_id, board_game_id, board_player_id)
                game_id = board_game_id
                player_id = board_player_id

                # Handle reconnection in game session
                reconnect_success = await game_session_manager.handle_reconnect(
                    connection_id, board_game_id, board_player_id
                )
                if reconnect_success:
                    # Notify opponent of reconnection
                    await connection_manager.send_to_game(board_game_id, {
                        "type": "opponent_reconnected",
                        "message": "Your opponent has reconnected",
                        "reconnected_player_id": board_player_id
                    }, exclude_connection=connection_id)

                try:
                    game_board = get_game_board(board_game_id)
                    board_state = game_board.get_board_state()
                    rendered = BoardRenderer.render(board_state)

                    await connection_manager.send_message(connection_id, {
                        "type": "board_state",
                        "game_id": board_game_id,
                        "board": board_state,
                        "rendered": rendered,
                        "fen": game_board.get_fen(),
                        "current_turn": game_board.get_current_turn(),
                        "game_over": game_board.is_game_over(),
                        "game_over_reason": game_board.get_game_over_reason()
                    })
                except HTTPException as e:
                    await connection_manager.send_message(connection_id, {
                        "type": "error",
                        "message": str(e.detail)
                    })

            elif message_type == "ping":
                # Heartbeat
                await connection_manager.send_message(connection_id, {
                    "type": "pong"
                })

    except WebSocketDisconnect:
        # Handle disconnect
        logger.debug(f"[WS:{connection_id}] WebSocket disconnected")
        await connection_manager.disconnect(connection_id)

        # Remove from matchmaking queue if still waiting
        logger.debug(f"[WS:{connection_id}] Removing from matchmaking queue")
        await matchmaking_queue.remove_from_queue(connection_id)
        queue_count = matchmaking_queue.get_queue_size()
        print(f"\n[Disconnect] Connection {connection_id} removed. Queue count: {queue_count}")
        logger.debug(f"[Queue] Queue count after removal: {queue_count}")

        if game_id and player_id:
            logger.debug(f"[Game:{game_id}] Handling disconnect for player {player_id}")
            disconnect_info = await game_session_manager.handle_disconnect(connection_id)

            if disconnect_info:
                status = disconnect_info.get("status")
                logger.debug(f"[Game:{game_id}] Disconnect status: {status}")

                if status == "disconnected":
                    # Notify opponent
                    logger.debug(f"[Game:{game_id}] Notifying opponent of disconnection")
                    await connection_manager.send_to_game(game_id, {
                        "type": "opponent_disconnected",
                        "message": "Your opponent has disconnected. Waiting 60s for reconnection...",
                        "disconnected_player_id": disconnect_info["disconnected_player_id"]
                    }, exclude_connection=connection_id)

                elif status in ["forfeit", "cancelled"]:
                    # Game ended
                    logger.debug(f"[Game:{game_id}] Game ended with status: {status}")
                    await connection_manager.send_to_game(game_id, {
                        "type": "game_over",
                        "status": status,
                        "winner": disconnect_info.get("winner"),
                        "message": "Game cancelled" if status == "cancelled" else "Opponent forfeited"
                    })

                    # Clean up session
                    logger.debug(f"[Game:{game_id}] Cleaning up session")
                    await game_session_manager.remove_session(game_id)


@app.get("/")
def root() -> Dict[str, str]:
    """
    Root endpoint providing API information.

    :return: API welcome message
    :rtype: Dict[str, str]
    """
    return {"message": "Chess Arena API - Use /docs for API documentation"}
