# aim.measai.app

Minimal room-chat deployment for Jonathan follow-up, based on `External/team-chat`.

## What it includes
- `room_viewer.py` (web UI)
- `room_daemon.py` (inbox -> thread consolidation)
- `seed_rooms/welcome-jonathan/thread.md` (first room example)

## Coolify quick setup
- Build context: `External/aim-measai-app`
- Port: `8000`
- Domain: `aim.measai.app`
- Persistent volume: mount to `/data/rooms`

## Environment variables
- `ROOMS_DIR=/data/rooms`
- `DEFAULT_SENDER=Guest`
- `PORT=8000`

On first boot, `start.sh` seeds `/data/rooms` from `/app/seed_rooms` if the volume is empty.
