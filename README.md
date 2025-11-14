# Chess Arenagit 

A FastAPI-based chess server with WebSocket support, real-time matchmaking, and TUI rendering.

## Features

- **Real-time WebSocket communication** for instant move updates
- **Matchmaking queue system** with connection-aware pairing
- **Multi-game support** - multiple concurrent games with persistence
- **Disconnect handling** - 60-second reconnection window with forfeit on timeout
- **Prevention of self-matching** - players can't match with themselves
- Chess board state management with standard algebraic notation
- Text-based UI (TUI) rendering with proper coordinate labels (a-h files, 1-8 ranks)
- PGN (Portable Game Notation) game replay
- RESTful API with FastAPI
- Full move validation using the python-chess library
- Game state persistence across server restarts

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
make server

# Or directly
python -m chess_arena
```

The server will start on `http://localhost:9002`

Visit `http://localhost:9002/docs` for interactive API documentation.

## Make a Client

See [demos/BUILD_YOUR_OWN.md](demos/BUILD_YOUR_OWN.md) for instructions on building your own chess client.

## Architecture

### WebSocket Endpoint

**WS /ws** - Primary endpoint for real-time chess gameplay

The WebSocket connection handles:
- **Matchmaking**: Join queue and get paired with another player
- **Move submission**: Send moves in real-time
- **Board updates**: Receive opponent's moves instantly
- **Disconnect notifications**: Get notified when opponent disconnects
- **Game state queries**: Request current board state

#### Message Types (Client → Server)

```json
// Join matchmaking queue
{"type": "join_queue"}

// Make a move
{
  "type": "make_move",
  "data": {
    "game_id": "uuid",
    "player_id": "uuid",
    "move": "e4"
  }
}

// Get board state
{"type": "get_board", "game_id": "uuid"}

// Heartbeat
{"type": "ping"}
```

#### Message Types (Server → Client)

```json
// Match found
{
  "type": "match_found",
  "game_id": "uuid",
  "player_id": "uuid",
  "assigned_color": "white",
  "first_move": "player_id"
}

// Move made (broadcast to both players)
{
  "type": "move_made",
  "game_id": "uuid",
  "move": "e4",
  "board": [...],
  "rendered": "...",
  "fen": "...",
  "game_over": false
}

// Opponent disconnected
{
  "type": "opponent_disconnected",
  "message": "Your opponent has disconnected. Waiting 60s for reconnection...",
  "disconnected_player_id": "uuid"
}

// Game over (forfeit/cancelled)
{
  "type": "game_over",
  "status": "forfeit|cancelled",
  "winner": "player_id",
  "message": "..."
}

// Error
{"type": "error", "message": "..."}
```

### REST API Endpoints (Legacy)

These endpoints are still available for non-matchmaking games:

#### POST /newgame
Create a new chess game.

**Response:**
```json
{"game_id": "uuid"}
```

#### GET /board?game_id=uuid
Get the current board state with TUI rendering.

#### GET /coordinates?game_id=uuid
Get all piece positions on the board.

#### POST /move
Make a move using standard algebraic notation.

**Request:**
```json
{
  "game_id": "uuid",
  "move": "e4",
  "player_id": "uuid"  // For matchmade games
}
```

#### POST /replay
Replay a complete chess game from PGN notation.

#### POST /reset
Reset the board to the starting position.

## Demo Client

An autonomous chess AI client that connects via WebSocket, joins the matchmaking queue, and plays complete games using minimax search with alpha-beta pruning.

### Running the Demo Client

```bash
# Start a client (default 5 second search time)
python demos/chess_client.py

# Adjust search time per move
python demos/chess_client.py --search-time 10.0

# Connect to a different port
python demos/chess_client.py --port 9002

# Run two clients simultaneously to watch them play each other
# Terminal 1:
python demos/chess_client.py --search-time 5.0

# Terminal 2:
python demos/chess_client.py --search-time 5.0
```

### Client Features

- **Automatic matchmaking**: Joins queue and waits for opponent
- **WebSocket connection**: Maintains persistent connection throughout game
- **Real-time updates**: Receives opponent moves instantly
- **Disconnect resilience**: Notified if opponent disconnects
- **AI Engine**:
  - Material and position evaluation using piece-square tables
  - Minimax search with alpha-beta pruning
  - Iterative deepening for time management
  - Move ordering (captures first, then center control)
  - Search depth scales with available time

### Client Options

- `--search-time`: Maximum seconds to search for a move (default: `5.0`)
- `--port`: Server port (default: `9002`)

### How Matchmaking Works

1. Client connects to WebSocket endpoint (`ws://localhost:9002/ws`)
2. Sends `join_queue` message
3. Waits up to 60 seconds for an opponent
4. When matched:
   - Receives unique `player_id` and `game_id`
   - Assigned random color (white or black)
   - Informed who moves first
5. Game proceeds with real-time move exchange
6. If opponent disconnects:
   - Notified and given 60-second grace period
   - Wins by forfeit if opponent doesn't reconnect
   - Game cancelled if both disconnect

## Quick Start Example

```bash
# Terminal 1: Start the server
make run

# Terminal 2: Start first AI client
python demos/chess_client.py --search-time 3.0

# Terminal 3: Start second AI client
python demos/chess_client.py --search-time 3.0

# Watch them play a complete game!
```

### REST API Usage (for non-matchmaking games)

```bash
# Create a new game
curl -X POST http://localhost:9002/newgame

# Get board state
curl "http://localhost:9002/board?game_id=<uuid>"

# Make a move (legacy endpoint)
curl -X POST http://localhost:9002/move \
  -H "Content-Type: application/json" \
  -d '{"game_id":"<uuid>","move":"e4","player":"white"}'
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

- **FastAPI** - Modern web framework with WebSocket support
- **WebSockets** - Real-time bidirectional communication
- **python-chess** - Chess library for move validation and PGN parsing
- **Uvicorn** - ASGI server
- **Pydantic** - Data validation
- **pytest** - Testing framework with async support
- **Rich** - Terminal UI library for client rendering

## Architecture Overview

### Connection Manager
Tracks all active WebSocket connections and their associated games.

### Matchmaking Queue
- Connection-aware pairing prevents self-matching
- FIFO queue with 60-second timeout
- Random color assignment
- Creates game sessions on match

### Game Session Manager
- Monitors player connections in active games
- 60-second disconnect grace period
- Automatic forfeit on timeout
- Game cancellation if both players disconnect

### Persistence
- Games stored in `/tmp/chess_arena/games.json`
- Preserves board state across server restarts
- FEN notation for compact storage

## Key Improvements

### Bug Fix: Self-Matching Prevention
**Problem**: When a player joined the queue and timed out, then rejoined, the server would match them with their own previous queue entry, allowing self-play.

**Solution**: Queue system now tracks `connection_id` for each entry and rejects attempts from the same connection to match with itself. WebSocket connections provide stable identity throughout the session.

### Real-Time Communication
Replaced HTTP polling with persistent WebSocket connections:
- Instant move updates (no polling delay)
- Server can notify clients of events (disconnects, game over)
- Reduced network overhead
- Better user experience

### Disconnect Handling
- Server monitors all connections in real-time
- 60-second grace period for reconnection
- Opponent notified of disconnect
- Automatic forfeit if reconnection fails
- Game cancelled if both players disconnect

## License

MIT
