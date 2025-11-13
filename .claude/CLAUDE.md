# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chess Arena is a FastAPI-based chess server with TUI rendering and PGN replay support. The architecture consists of three core modules:

1. **ChessBoard** (`chess_arena/board.py`) - Wraps python-chess library for board state management
2. **BoardRenderer** (`chess_arena/renderer.py`) - TUI rendering with algebraic notation coordinates
3. **FastAPI Server** (`chess_arena/server.py`) - RESTful API exposing chess functionality

The server maintains a single global `game_board` instance that persists state across API requests.

## Development Commands

### Setup and Running
```bash
# Install dependencies (uses uv package manager)
make install          # With dev dependencies
make install-prod     # Production only

# Run the FastAPI server (starts on http://localhost:8555)
make run
# Or directly:
python -m chess_arena
```

### Testing and Quality
```bash
# Run all tests
make test
# Run specific test file:
pytest tests/test_board.py -v

# Format code (autopep8)
make format

# Run linters (flake8 + mypy)
make lint

# Clean build artifacts
make clean
```

### Package Management
This project uses **uv** (not pip) for dependency management. Always use `uv` commands or the Makefile for package operations.

## Architecture Notes

### State Management
- The server uses a **global singleton** `game_board` object in `server.py:12`
- This means the board state persists across all API requests until server restart
- No database or persistence layer - all state is in-memory

### Board Representation
- ChessBoard.get_board_state() returns `List[List[str]]` - an 8x8 grid
- Rows are indexed from rank 8 (top) to rank 1 (bottom)
- Each cell contains a piece symbol or space character
- The internal chess.Board uses python-chess library for move validation

### Move Handling
- All moves use **Standard Algebraic Notation (SAN)** (e.g., "e4", "Nf3", "Qxd5")
- Move validation is handled by python-chess via `board.parse_san()`
- Invalid moves return HTTP 400 without modifying board state

### PGN Replay
- PGN parsing is custom implementation in `board._parse_pgn_moves()`
- Handles numbered moves (e.g., "1.e4") and filters game result markers
- Replays always reset the board first, then apply moves sequentially

## Code Style Requirements

- Line length: 120 characters (pycodestyle, isort configured)
- Docstrings: Sphinx style (already used throughout)
- Type hints: Required on all function parameters and return types
- Pydantic models: Used for all API request/response models

## Testing Structure

- Tests located in `tests/` directory off project root
- Test files mirror source structure: `test_board.py`, `test_renderer.py`, `test_server.py`
- Server tests use `httpx.AsyncClient` for API endpoint testing
- Coverage excludes test files (configured in pyproject.toml)

## API Design Patterns

All endpoints follow this pattern:
1. Call ChessBoard method to modify/query state
2. Get board_state via `get_board_state()`
3. Render via `BoardRenderer.render(board_state)`
4. Return Pydantic response model with board, rendered, fen, game_over

The server prints board state to console on every state change for debugging.
