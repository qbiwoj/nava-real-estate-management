#!/bin/bash
set -e

echo "🗑️  Resetting database..."

# Terminate active connections
docker-compose exec -T db psql -U nava -d postgres -c "SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = 'nava' AND pid <> pg_backend_pid();" > /dev/null 2>&1 || true

# Drop and recreate database
docker-compose exec -T db psql -U nava -d postgres << EOF
DROP DATABASE IF EXISTS nava;
CREATE DATABASE nava;
EOF

echo "📦 Running migrations..."
docker-compose exec -T backend uv run alembic upgrade head

echo "🌱 Seeding fresh data from data.csv..."
docker-compose exec -T backend uv run python -m app.seed

echo "✅ Database reset complete. Ready for fresh agent runs."
