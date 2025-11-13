# Chess Arena Client Development Guide

This guide explains how to build a client that connects to the Chess Arena server.

## Overview

The Chess Arena server exposes a RESTful API for playing chess. Clients can:
- Query board state and legal moves
- Submit moves in Standard Algebraic Notation (SAN)
- Monitor game state and turn progression

## Server Configuration

**Default Server**: `http://localhost:9001`

Start the server with:
```bash
make run
# Or directly:
python -m chess_arena
```

## API Endpoints

### GET /board
Returns current board state with visual rendering.

**Response**:
```json
{
  "board": [["r","n","b","q","k","b","n","r"], ...],
  "rendered": "8 ♜ ♞ ♝ ♛ ♚ ♝ ♞ ♜\n...",
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "game_over": false
}
```

### GET /turn
Returns whose turn it is.

**Response**:
```json
{
  "turn": "white"
}
```

### GET /legal-moves
Returns all legal moves in current position.

**Response**:
```json
{
  "legal_moves": ["e4", "d4", "Nf3", "c4", ...]
}
```

### POST /move
Submit a move to the server.

**Request**:
```json
{
  "move": "e4",
  "player": "white"
}
```

**Response**: Same as GET /board

**Error Response** (400):
```json
{
  "detail": "ILLEGAL MOVE ATTEMPTED\nMove: 'e5'\nCurrent turn: white\nLegal moves: ['e4', 'd4', ...]"
}
```

## Building a Client

### 1. Basic HTTP Communication

Use standard HTTP library to make requests:

**Python Example**:
```python
import json
from urllib import request

def make_request(endpoint: str, method: str = 'GET', data: dict = None):
    url = f"http://localhost:9001{endpoint}"
    headers = {'Content-Type': 'application/json'}

    req = request.Request(url, method=method, headers=headers)
    if data:
        req.data = json.dumps(data).encode('utf-8')

    with request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))
```

### 2. Game Loop Pattern

Typical client structure:

```python
while True:
    # 1. Check whose turn it is
    current_turn = make_request('/turn')['turn']

    # 2. If it's your turn:
    if current_turn == your_color:
        # Get board state
        state = make_request('/board')

        # Check for game over
        if state['game_over']:
            break

        # Get legal moves
        legal_moves = make_request('/legal-moves')['legal_moves']

        # Choose a move (your algorithm here)
        move = choose_move(state, legal_moves)

        # Submit the move
        make_request('/move', method='POST', data={
            'move': move,
            'player': your_color
        })

    # 3. Wait before checking again
    time.sleep(0.5)
```

### 3. Move Notation (SAN)

All moves use Standard Algebraic Notation:

- **Pawn moves**: `e4`, `d5`, `e8=Q` (promotion)
- **Piece moves**: `Nf3`, `Bc4`, `Qd1`
- **Captures**: `exd5`, `Nxe5`, `Qxf7`
- **Castling**: `O-O` (kingside), `O-O-O` (queenside)
- **Disambiguation**: `Nbd2`, `R1e2`, `Qh4e1`

### 4. Error Handling

Always handle illegal moves gracefully:

```python
try:
    make_request('/move', method='POST', data={'move': move, 'player': player})
except HTTPError as e:
    error_body = e.read().decode('utf-8')
    error_json = json.loads(error_body)
    print(f"Move rejected: {error_json['detail']}")
```

### 5. Board State Structure

The `board` field is an 8x8 list of lists:
- **Index [0][0]**: Rank 8, File a (top-left, a8)
- **Index [7][7]**: Rank 1, File h (bottom-right, h1)

**Piece symbols**:
- White: `P N B R Q K` (uppercase)
- Black: `p n b r q k` (lowercase)
- Empty: ` ` (space)

### 6. Turn Management

- The `/turn` endpoint returns `"white"` or `"black"`
- Match this against your client's color before making moves
- Poll periodically (recommended: 0.5s interval)

## Example Client

See `demos/simple_client.py` for a complete working example that includes:
- Position evaluation
- Minimax search with alpha-beta pruning
- Move ordering heuristics
- Iterative deepening

**Run the example**:
```bash
# Terminal 1: Start server
make run

# Terminal 2: Start white player
python demos/simple_client.py --player W

# Terminal 3: Start black player
python demos/simple_client.py --player B
```

## Client Architecture Recommendations

### Minimal Client (Random Player)
```python
import random
move = random.choice(legal_moves)
```

### Basic Client (Material Count)
```python
# Evaluate each legal move
# Choose move with best material balance
```

### Advanced Client
- **Search**: Minimax with alpha-beta pruning
- **Evaluation**: Material + position tables + mobility
- **Move ordering**: Captures first, then center control
- **Time management**: Iterative deepening with time limit

## Common Pitfalls

1. **Polling too fast**: Don't hammer the server. Use 0.5-1s intervals.
2. **Not checking turn**: Always verify it's your turn before moving.
3. **Ignoring game_over**: Check `game_over` flag to exit gracefully.
4. **Invalid SAN**: Ensure moves match exactly what `/legal-moves` returns.
5. **Player mismatch**: The `player` field in POST /move must match the current turn.

## Testing Your Client

**Manual testing**:
```bash
# Start server
make run

# In another terminal, test endpoints:
curl http://localhost:9001/board
curl http://localhost:9001/turn
curl http://localhost:9001/legal-moves
curl -X POST http://localhost:9001/move \
  -H "Content-Type: application/json" \
  -d '{"move":"e4","player":"white"}'
```

**Automated testing**:
```python
# Test against itself
client_white = ChessClient(server_url, 'W')
client_black = ChessClient(server_url, 'B')

# Run both in separate threads/processes
```

## Advanced Features

### Custom Evaluation Functions
Override `evaluate_position()` in simple_client.py:287 to implement your own board evaluation logic.

### Opening Books
Pre-load common opening moves to avoid computation in early game.

### Endgame Tablebases
Integrate Syzygy tablebases for perfect endgame play.

### Time Control
The server doesn't enforce time limits - implement your own time management.

## Resources

- **python-chess docs**: https://python-chess.readthedocs.io/
- **Chess Programming Wiki**: https://www.chessprogramming.org/
- **SAN Notation**: https://en.wikipedia.org/wiki/Algebraic_notation_(chess)

## Support

For issues with the Chess Arena server, see the main README.md in the project root.
