"""FastAPI server for chess arena application."""

from typing import Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from chess_arena.board import ChessBoard
from chess_arena.renderer import BoardRenderer

app = FastAPI(title="Chess Arena API", version="1.0.0")
game_board = ChessBoard()


def print_board() -> None:
    """
    Print the current board state to the terminal.

    Displays the board using the TUI renderer.
    """
    board_state = game_board.get_board_state()
    rendered = BoardRenderer.render(board_state)
    print("\n" + rendered + "\n")


@app.on_event("startup")
def on_startup() -> None:
    """
    Handle application startup event.

    Displays the initial board state when the server starts.
    """
    print("\n" + "=" * 50)
    print("Chess Arena Server Started")
    print("=" * 50)
    print_board()


class MoveRequest(BaseModel):
    """
    Request model for making a chess move.

    :param move: Move in standard algebraic notation
    :type move: str
    :param player: Player making the move ('white' or 'black')
    :type player: str
    """

    move: str
    player: str


class ReplayRequest(BaseModel):
    """
    Request model for replaying a PGN game.

    :param pgn: PGN notation string containing the game moves
    :type pgn: str
    """

    pgn: str


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


@app.get("/board", response_model=BoardResponse)
def get_board() -> BoardResponse:
    """
    Get the current state of the chess board.

    :return: Current board state with rendering
    :rtype: BoardResponse
    """
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
def get_coordinates() -> CoordinatesResponse:
    """
    Get all piece coordinates on the board.

    :return: Dictionary of square coordinates to piece symbols
    :rtype: CoordinatesResponse
    """
    coordinates = game_board.get_all_coordinates()
    return CoordinatesResponse(coordinates=coordinates)


@app.get("/turn", response_model=TurnResponse)
def get_turn() -> TurnResponse:
    """
    Get whose turn it is to move.

    :return: Current player's turn with game over status
    :rtype: TurnResponse
    """
    turn = game_board.get_current_turn()
    return TurnResponse(
        turn=turn,
        game_over=game_board.is_game_over(),
        game_over_reason=game_board.get_game_over_reason()
    )


@app.get("/legal-moves", response_model=LegalMovesResponse)
def get_legal_moves() -> LegalMovesResponse:
    """
    Get all legal moves in the current position.

    :return: List of legal moves in algebraic notation
    :rtype: LegalMovesResponse
    """
    legal_moves = game_board.get_legal_moves()
    return LegalMovesResponse(legal_moves=legal_moves)


@app.post("/move", response_model=BoardResponse)
def make_move(move_request: MoveRequest) -> BoardResponse:
    """
    Make a move on the chess board.

    :param move_request: Move request containing algebraic notation
    :type move_request: MoveRequest
    :return: Updated board state
    :rtype: BoardResponse
    :raises HTTPException: If the move is invalid or wrong player's turn
    """
    current_turn = game_board.get_current_turn()
    if move_request.player != current_turn:
        raise HTTPException(
            status_code=403,
            detail=f"It is {current_turn}'s turn, not {move_request.player}'s turn"
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

    print(f"\nMove: {move_request.move}")
    print_board()

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

    :param replay_request: Request containing PGN notation
    :type replay_request: ReplayRequest
    :return: Final board state after replay
    :rtype: BoardResponse
    :raises HTTPException: If PGN replay fails
    """
    success = game_board.replay_pgn(replay_request.pgn)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to replay PGN")

    print("\nPGN Game Replayed")
    print_board()

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
def reset_board() -> BoardResponse:
    """
    Reset the chess board to the starting position.

    :return: Board state at starting position
    :rtype: BoardResponse
    """
    game_board.reset()

    print("\nBoard Reset to Starting Position")
    print_board()

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
