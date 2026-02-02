# Coolify Config - aim.measai.app

## Service type
- Dockerfile app
- Build context: `External/aim-measai-app`
- Exposed app port: `8000`

## Domain
- Primary domain: `aim.measai.app`
- TLS: Let's Encrypt (Coolify/Traefik default)

## Environment variables
- `ROOMS_DIR=/data/rooms`
- `DEFAULT_SENDER=Guest`
- `PORT=8000`

## Persistent storage
- Add one persistent volume:
  - Host/managed volume -> container path: `/data/rooms`

## Startup behavior
- `start.sh` seeds `welcome-jonathan` from `/app/seed_rooms` only when `/data/rooms` is empty.
- Viewer-only mode is enabled (no `room_daemon.py` process).

## Pre-deploy checks
1. DNS A record for `aim.measai.app` points to `136.243.148.151`.
2. Coolify app points to this repo path/build context.
3. Port in app config is `8000` (not 3000).
4. Volume mount exists at `/data/rooms`.

## Post-deploy checks
1. Open `https://aim.measai.app` and verify `welcome-jonathan` loads.
2. Send a test message from UI; verify append to thread file in volume.
3. Confirm HTTPS cert issued and active.
