.PHONY: help install dev test lint format clean run

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install package
	uv sync

install-prod:  ## Install with development dependencies
	uv sync --no-dev

test:  ## Run tests
	pytest tests/ -v

lint:  ## Run linters
	flake8 chess_arena/ tests/
	mypy chess_arena/

format:  ## Format code
	autopep8 -a  --in-place --recursive .

clean:  ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

build:  ## Build distribution packages
	python -m build


client1: ## start a client demo - player 1
	cd demos && python chess_client.py --search-time 1 --auth-file .player1

client2: ## start a client demo - player 2
	cd demos && python chess_client.py --search-time 2 --auth-file .player2

client1-continue: ## continue stopped client demo - player 1
	cd demos && python chess_client.py --search-time 1 --auth-file .player1 --continue

client2-continue: ## continue stopped client demo - player 2
	cd demos && python chess_client.py --search-time 2 --auth-file .player2 --continue

server:  ## Run the FastAPI server
	python -m chess_arena
