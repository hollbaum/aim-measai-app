#!/bin/sh
set -e

ROOMS_DIR="${ROOMS_DIR:-/data/rooms}"
SEED_DIR="/app/seed_rooms"

mkdir -p "$ROOMS_DIR"

# Seed example room on first boot only.
if [ -d "$SEED_DIR" ] && [ -z "$(ls -A "$ROOMS_DIR" 2>/dev/null)" ]; then
  echo "Seeding initial rooms from $SEED_DIR..."
  cp -R "$SEED_DIR"/* "$ROOMS_DIR"/
fi

echo "Starting room daemon in background..."
python3 -u room_daemon.py &

echo "Starting room viewer on port ${PORT:-8000}..."
if [ -n "$DEFAULT_ROOM" ]; then
  exec python3 -u room_viewer.py --port "${PORT:-8000}" --room "$DEFAULT_ROOM"
else
  exec python3 -u room_viewer.py --port "${PORT:-8000}"
fi
