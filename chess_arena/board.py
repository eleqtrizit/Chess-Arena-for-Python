"""Chess board state management module."""

from typing import Dict, List, Optional

import chess


class ChessBoard:
    """
    Manages chess board state and move execution.

    This class wraps the python-chess library to provide a simplified interface
    for managing a chess game, including move execution, board state retrieval,
    and game reset functionality.
    """

    def __init__(self, player_mappings: Optional[Dict[str, str]] = None) -> None:
        """
        Initialize a new chess board in the starting position.

        :param player_mappings: Optional mapping of player_id to color ('white' or 'black')
        :type player_mappings: Optional[Dict[str, str]]
        """
        self.board = chess.Board()
        self.player_mappings: Dict[str, str] = player_mappings or {}

    def reset(self) -> None:
        """Reset the board to the starting position."""
        self.board.reset()

    def make_move(self, move: str) -> bool:
        """
        Make a move on the board using algebraic notation.

        :param move: Move in standard algebraic notation (e.g., 'e4', 'Nf3')
        :type move: str
        :return: True if move was successful, False otherwise
        :rtype: bool
        """
        try:
            chess_move = self.board.parse_san(move)
            self.board.push(chess_move)
            return True
        except (ValueError, chess.IllegalMoveError, chess.InvalidMoveError):
            return False

    def get_legal_moves(self) -> List[str]:
        """
        Get all legal moves in the current position.

        :return: List of legal moves in standard algebraic notation
        :rtype: List[str]
        """
        return [self.board.san(move) for move in self.board.legal_moves]

    def get_all_coordinates(self) -> Dict[str, str]:
        """
        Get all piece positions on the board.

        :return: Dictionary mapping square coordinates to piece symbols
        :rtype: Dict[str, str]
        """
        coordinates = {}
        for square in chess.SQUARES:
            piece = self.board.piece_at(square)
            if piece:
                square_name = chess.square_name(square)
                coordinates[square_name] = piece.symbol()
        return coordinates

    def get_board_state(self) -> List[List[str]]:
        """
        Get the current board state as an 8x8 grid.

        :return: 8x8 list representing the board, with piece symbols or empty strings
        :rtype: List[List[str]]
        """
        board_state = []
        for rank in range(7, -1, -1):
            row = []
            for file in range(8):
                square = chess.square(file, rank)
                piece = self.board.piece_at(square)
                row.append(piece.symbol() if piece else ' ')
            board_state.append(row)
        return board_state

    def replay_pgn(self, pgn_moves: str) -> bool:
        """
        Replay a game from PGN notation.

        :param pgn_moves: PGN move string (e.g., '1.e4 e5 2.Nf3 Nc6')
        :type pgn_moves: str
        :return: True if replay was successful, False otherwise
        :rtype: bool
        """
        self.reset()
        moves = self._parse_pgn_moves(pgn_moves)
        try:
            for move in moves:
                if not self.make_move(move):
                    return False
            return True
        except Exception:
            return False

    def _parse_pgn_moves(self, pgn_moves: str) -> List[str]:
        """
        Parse PGN move string into individual moves.

        :param pgn_moves: PGN move string
        :type pgn_moves: str
        :return: List of individual moves in algebraic notation
        :rtype: List[str]
        """
        moves = []
        tokens = pgn_moves.split()
        for token in tokens:
            if token in ['1-0', '0-1', '1/2-1/2', '*']:
                continue
            if '.' in token:
                parts = token.split('.')
                if len(parts) > 1 and parts[1]:
                    moves.append(parts[1])
            else:
                moves.append(token)
        return moves

    def get_fen(self) -> str:
        """
        Get the current board position in FEN notation.

        :return: FEN string representing the current position
        :rtype: str
        """
        return self.board.fen()

    def is_game_over(self) -> bool:
        """
        Check if the game is over.

        :return: True if game is over, False otherwise
        :rtype: bool
        """
        return self.board.is_game_over()

    def get_game_over_reason(self) -> str:
        """
        Get the reason why the game is over.

        :return: Reason for game over, or empty string if game is not over
        :rtype: str
        """
        if not self.board.is_game_over():
            return ""

        if self.board.is_checkmate():
            winner = "Black" if self.board.turn else "White"
            return f"Checkmate - {winner} wins"
        if self.board.is_stalemate():
            return "Stalemate - Draw"
        if self.board.is_insufficient_material():
            return "Insufficient material - Draw"
        if self.board.is_seventyfive_moves():
            return "Seventy-five move rule - Draw"
        if self.board.is_fivefold_repetition():
            return "Fivefold repetition - Draw"

        return "Game over"

    def get_current_turn(self) -> str:
        """
        Get whose turn it is to move.

        :return: 'white' if it's white's turn, 'black' if it's black's turn
        :rtype: str
        """
        return 'white' if self.board.turn else 'black'

    def get_player_color(self, player_id: str) -> Optional[str]:
        """
        Get the color assigned to a player.

        :param player_id: The player's unique identifier
        :type player_id: str
        :return: 'white' or 'black' if player exists, None otherwise
        :rtype: Optional[str]
        """
        return self.player_mappings.get(player_id)

    def is_players_turn(self, player_id: str) -> bool:
        """
        Check if it is the specified player's turn to move.

        :param player_id: The player's unique identifier
        :type player_id: str
        :return: True if it's the player's turn, False otherwise
        :rtype: bool
        """
        player_color = self.get_player_color(player_id)
        if player_color is None:
            return False
        return player_color == self.get_current_turn()
