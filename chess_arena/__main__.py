"""Main entry point for chess arena application."""

import argparse

import uvicorn


def main() -> None:
    """
    Start the FastAPI server.

    Runs the Chess Arena API server. Default configuration is host 0.0.0.0 and port 9002.
    Visit http://<host>:<port>/docs for API documentation.
    """
    parser = argparse.ArgumentParser(description="Chess Arena API Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=9002, help="Port to bind the server to (default: 9002)")
    args = parser.parse_args()

    uvicorn.run("chess_arena.server:app", host=args.host, port=args.port, reload=True)


if __name__ == "__main__":
    main()
