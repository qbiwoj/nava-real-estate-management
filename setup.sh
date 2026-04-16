#!/usr/bin/env bash
set -e

echo "Starting database..."
docker-compose up -d

echo "Running migrations..."
uv run alembic upgrade head

echo "Seeding data..."
uv run python -m app.seed

echo "Starting backend..."
uvicorn app.main:app --reload &

echo "Starting frontend..."
cd frontend && npm install && npm run dev
