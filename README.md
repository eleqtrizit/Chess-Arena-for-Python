# Chess Arena

A FastAPI-based chess board server with TUI rendering and PGN replay support.

## Features

- Chess board state management with standard algebraic notation
- Text-based UI (TUI) rendering with proper coordinate labels (a-h files, 1-8 ranks)
- PGN (Portable Game Notation) game replay
- RESTful API with FastAPI
- Full move validation using the python-chess library

## Installation

```bash
# Install dependencies
make install

# Or install without dev dependencies
make install-prod
```

## Running the Server

```bash
# Start the FastAPI server
make run

# Or directly
python -m chess_arena
```

The server will start on `http://localhost:9001`

Visit `http://localhost:9001/docs` for interactive API documentation.

## API Endpoints

### GET /board
Get the current board state with TUI rendering.

**Response:**
```json
{
  "board": [...],
  "rendered": "...",
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "game_over": false
}
```

### GET /coordinates
Get all piece positions on the board.

**Response:**
```json
{
  "coordinates": {
    "e1": "K",
    "e8": "k",
    ...
  }
}
```

### POST /move
Make a move using standard algebraic notation.

**Request:**
```json
{
  "move": "e4"
}
```

**Response:** Updated board state (same as GET /board)

### POST /replay
Replay a complete chess game from PGN notation.

**Request:**
```json
{
  "pgn": "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6"
}
```

**Response:** Final board state after replay

### POST /reset
Reset the board to the starting position.

**Response:** Board state at starting position

## Demo Client

A standalone chess client is included that plays against the Chess Arena server using basic chess algorithms.

### Running the Demo Client

```bash
# Play as White against the server
python demos/simple_client.py --player W

# Play as Black
python demos/simple_client.py --player B

# Connect to a specific host and port
python demos/simple_client.py --player W --host localhost --port 9001

# Connect to a remote server
python demos/simple_client.py --player B --host 192.168.1.100 --port 9001

# Use a full server URL (overrides --host and --port)
python demos/simple_client.py --player W --server http://example.com:9001

# Adjust search time per move (default: 5 seconds)
python demos/simple_client.py --player W --search-time 10.0
```

### Client Options

- `--player` (required): Color to play as (`W` for White, `B` for Black)
- `--host`: Server hostname (default: `localhost`)
- `--port`: Server port (default: `9001`)
- `--server`: Full server URL (overrides `--host` and `--port` if provided)
- `--search-time`: Maximum seconds to search for a move (default: `5.0`)

The client implements:
- Material and position evaluation
- Minimax search with alpha-beta pruning
- Move ordering for better performance

## Example Usage

```bash
# Get current board
curl http://localhost:9001/board

# Make a move
curl -X POST http://localhost:9001/move \
  -H "Content-Type: application/json" \
  -d '{"move":"e4"}'

# Replay a complete game
curl -X POST http://localhost:9001/replay \
  -H "Content-Type: application/json" \
  -d '{"pgn":"1.e4 e5 2.Nf3 Nc6"}'

# Reset the board
curl -X POST http://localhost:9001/reset
```

## Development

```bash
# Run tests
make test

# Format code
make format

# Run linters
make lint

# Clean build artifacts
make clean
```

## Board Rendering

The TUI renderer displays the board with:
- One space padding around each piece character
- Standard chess coordinates (a-h for files, 1-8 for ranks)
- Uppercase letters for white pieces (K, Q, R, B, N, P)
- Lowercase letters for black pieces (k, q, r, b, n, p)

Example:
```
  +---+---+---+---+---+---+---+---+
8 | r | n | b | q | k | b | n | r |
  +---+---+---+---+---+---+---+---+
7 | p | p | p | p | p | p | p | p |
  +---+---+---+---+---+---+---+---+
6 |   |   |   |   |   |   |   |   |
  +---+---+---+---+---+---+---+---+
5 |   |   |   |   |   |   |   |   |
  +---+---+---+---+---+---+---+---+
4 |   |   |   |   |   |   |   |   |
  +---+---+---+---+---+---+---+---+
3 |   |   |   |   |   |   |   |   |
  +---+---+---+---+---+---+---+---+
2 | P | P | P | P | P | P | P | P |
  +---+---+---+---+---+---+---+---+
1 | R | N | B | Q | K | B | N | R |
  +---+---+---+---+---+---+---+---+
    a   b   c   d   e   f   g   h
```

## Tech Stack

- **FastAPI** - Modern web framework for building APIs
- **python-chess** - Chess library for move validation and PGN parsing
- **Uvicorn** - ASGI server
- **Pydantic** - Data validation
- **pytest** - Testing framework

## License

MIT
