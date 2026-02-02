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

## Deployment Status

- **Deployed:** 2026-02-02 12:47 UTC
- **Platform:** Coolify with GitHub webhook auto-deploy
- **Domain:** https://aim.measai.app
- **Auto-deploy:** Enabled (webhook triggers on push to main)

Deployed by: Christian Hollbaum
Infrastructure: Taynor
Validation: Codex

