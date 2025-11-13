"""FastAPI server for chess arena application."""

import uuid
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from chess_arena.board import ChessBoard
from chess_arena.persistence import load_games, save_games
from chess_arena.queue import MatchmakingQueue
from chess_arena.renderer import BoardRenderer

app = FastAPI(title="Chess Arena API", version="1.0.0")
games: Dict[str, ChessBoard] = {}
matchmaking_queue = MatchmakingQueue()


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
    games = load_games()
    loaded_count = len(games)

    print("\n" + "=" * 50)
    print("Chess Arena Server Started")
    print("Multi-game support enabled")
    print(f"Loaded {loaded_count} persisted game(s)")
    print("=" * 50)


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


@app.post("/queue", response_model=QueueResponse)
async def join_matchmaking_queue() -> QueueResponse:
    """
    Join the matchmaking queue and wait for an opponent.

    Waits up to 60 seconds for another player to join. Once matched,
    both players receive a game_id, their player_id, assigned color,
    and who moves first.

    :return: Match details or timeout indication
    :rtype: QueueResponse
    """
    match_result = await matchmaking_queue.join_queue(timeout=60.0)

    if match_result is None:
        return QueueResponse(no_challengers=True)

    # Check if game already exists (second player matched)
    if match_result.game_id not in games:
        # First player to get result - create the game
        game_board = ChessBoard(player_mappings=match_result.player_mappings)
        games[match_result.game_id] = game_board
        persist_games()

        player_ids = list(match_result.player_mappings.keys())
        print(f"\n[Match created: {match_result.game_id}]")
        print(f"[Players: {player_ids[0]} ({match_result.player_mappings[player_ids[0]]}) vs "
              f"{player_ids[1]} ({match_result.player_mappings[player_ids[1]]})]")

    return QueueResponse(
        game_id=match_result.game_id,
        player_id=match_result.player_id,
        assigned_color=match_result.assigned_color,
        first_move=match_result.first_move,
        no_challengers=False
    )


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


@app.get("/")
def root() -> Dict[str, str]:
    """
    Root endpoint providing API information.

    :return: API welcome message
    :rtype: Dict[str, str]
    """
    return {"message": "Chess Arena API - Use /docs for API documentation"}
