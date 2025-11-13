"""Chess board TUI rendering module."""

from typing import List


class BoardRenderer:
    """
    Renders a chess board in text format with algebraic notation coordinates.

    Uses standard chess notation (files a-h, ranks 1-8) and provides
    padding around each piece character.
    """

    PIECE_SYMBOLS = {
        'P': 'P', 'N': 'N', 'B': 'B', 'R': 'R', 'Q': 'Q', 'K': 'K',
        'p': 'p', 'n': 'n', 'b': 'b', 'r': 'r', 'q': 'q', 'k': 'k',
        ' ': ' '
    }

    @staticmethod
    def render(board_state: List[List[str]]) -> str:
        """
        Render the board state as a text-based UI.

        :param board_state: 8x8 list of piece symbols
        :type board_state: List[List[str]]
        :return: Formatted board string with coordinates
        :rtype: str
        """
        lines = []
        files = "abcdefgh"

        for rank_idx, rank in enumerate(board_state):
            rank_num = 8 - rank_idx
            squares = []
            for piece in rank:
                squares.append(f" {piece} ")
            line = f"{rank_num} |{'|'.join(squares)}|"
            lines.append(line)

        separator = "  +" + "---+" * 8
        lines.insert(0, separator)
        for i in range(1, len(lines)):
            lines.insert(i * 2, separator)

        file_labels = "    " + "   ".join(files)
        lines.append(file_labels)

        return "\n".join(lines)

    @staticmethod
    def render_compact(board_state: List[List[str]]) -> str:
        """
        Render the board in a more compact format.

        :param board_state: 8x8 list of piece symbols
        :type board_state: List[List[str]]
        :return: Compact formatted board string
        :rtype: str
        """
        lines = []
        for rank_idx, rank in enumerate(board_state):
            rank_num = 8 - rank_idx
            squares = " ".join(f" {piece} " for piece in rank)
            lines.append(f"{rank_num} {squares}")
        lines.append("   a   b   c   d   e   f   g   h")
        return "\n".join(lines)
