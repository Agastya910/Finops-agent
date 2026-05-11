.PHONY: install dev dev-backend dev-frontend build test clean

install:
	uv sync
	cd frontend && npm install

dev-backend:
	uv run uvicorn backend.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

dev:
	make -j2 dev-backend dev-frontend

build:
	cd frontend && npm run build

test:
	uv run pytest tests/ -v

clean:
	rm -rf qdrant_data/ frontend/dist/ __pycache__ .pytest_cache
