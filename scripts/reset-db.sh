#!/bin/bash
set -e

echo "🗑️  Resetting database..."

# Drop and recreate database
dropdb nava 2>/dev/null || true
createdb nava

echo "📦 Running migrations..."
uv run alembic upgrade head

echo "🌱 Seeding fresh data from data.csv..."
uv run python -m app.seed --force

echo "✅ Database reset complete. Ready for fresh agent runs."
