# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chess Arena is a FastAPI-based chess server with WebSocket support, real-time matchmaking, and TUI rendering. The architecture consists of these core modules:

1. **ChessBoard** (`chess_arena/board.py`) - Wraps python-chess library for board state management
2. **BoardRenderer** (`chess_arena/renderer.py`) - TUI rendering with algebraic notation coordinates
3. **FastAPI Server** (`chess_arena/server.py`) - WebSocket and REST API endpoints
4. **ConnectionManager** (`chess_arena/connection_manager.py`) - Tracks active WebSocket connections
5. **MatchmakingQueue** (`chess_arena/queue.py`) - Connection-aware player pairing system
6. **GameSessionManager** (`chess_arena/game_session.py`) - Monitors player connections and handles disconnects
7. **Persistence** (`chess_arena/persistence.py`) - Saves/loads game state to disk

The server maintains multiple concurrent games in a `games` dictionary and persists them to `/tmp/chess_arena/games.json`.

## Development Commands

### Setup and Running
```bash
# Install dependencies (uses uv package manager)
make install          # With dev dependencies
make install-prod     # Production only

# Run the FastAPI server (starts on http://localhost:9002)
make run
# Or directly:
python -m chess_arena

# Run demo AI client (connects via WebSocket)
python demos/chess_client.py --search-time 5.0
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
- The server uses a **global games dictionary** `games: Dict[str, ChessBoard]` in `server.py:18`
- Each game has a unique UUID and maintains independent board state
- Games persist to `/tmp/chess_arena/games.json` after every move
- Server loads persisted games on startup via `load_games()`

### WebSocket Communication
- Primary endpoint: `WS /ws` handles real-time bidirectional communication
- ConnectionManager tracks all active WebSocket connections by connection_id
- Each connection can be associated with a game_id and player_id
- Messages are JSON with a `type` field indicating the message purpose

### Matchmaking System
- MatchmakingQueue maintains a FIFO queue with connection-aware pairing
- **Bug Prevention**: Tracks `connection_id` to prevent self-matching
- When two different connections join, creates a match with random color assignment
- Creates a GameSession to monitor both players throughout the game
- 60-second timeout if no opponent found

### Connection & Disconnect Handling
- GameSessionManager tracks which players are connected to which games
- Detects disconnections via WebSocket close events
- 60-second grace period for reconnection before forfeit
- Notifies opponent of disconnect/reconnect events
- Game cancelled if both players disconnect

### Board Representation
- ChessBoard.get_board_state() returns `List[List[str]]` - an 8x8 grid
- Rows are indexed from rank 8 (top) to rank 1 (bottom)
- Each cell contains a piece symbol or space character
- The internal chess.Board uses python-chess library for move validation
- ChessBoard now supports `player_mappings: Dict[str, str]` for matchmade games

### Move Handling
- All moves use **Standard Algebraic Notation (SAN)** (e.g., "e4", "Nf3", "Qxd5")
- Move validation is handled by python-chess via `board.parse_san()`
- Invalid moves return error messages via WebSocket or HTTP 400
- WebSocket moves are broadcast to both players instantly
- Server validates turn order using player_id for matchmade games

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
- Test files mirror source structure: `test_board.py`, `test_renderer.py`, `test_server.py`, `test_queue.py`, `test_connection_manager.py`, `test_game_session.py`, `test_persistence.py`
- Server tests use `httpx.AsyncClient` for API endpoint testing
- WebSocket and async components tested with `pytest-asyncio`
- Client tests in `test_chess_client.py` dynamically import from `demos/`
- Coverage excludes test files (configured in pyproject.toml)
- All tests must pass before committing changes

## API Design Patterns

### WebSocket Message Pattern (Primary)
1. Client sends JSON message with `type` field
2. Server validates message and extracts game_id/player_id
3. Server calls ChessBoard method to modify/query state
4. Server broadcasts updates to both players via ConnectionManager
5. Server prints board state to console for debugging

### REST Endpoints (Legacy, for non-matchmaking games)
1. Accept game_id as query parameter or in request body
2. Look up game from `games` dictionary via `get_game_board(game_id)`
3. Call ChessBoard method to modify/query state
4. Get board_state via `get_board_state()`
5. Render via `BoardRenderer.render(board_state)`
6. Return Pydantic response model with board, rendered, fen, game_over
7. Persist games via `persist_games()` after modifications

### Key Design Decisions
- WebSocket `/ws` is the primary interface for matchmaking and live games
- REST API maintained for backward compatibility and non-matchmaking use cases
- All game state changes trigger persistence to disk
- Server prints board state to console on every state change for debugging
- Connection identity tracked throughout WebSocket lifecycle to prevent self-matching
