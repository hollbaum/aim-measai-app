# AIM Double-Mount Architecture

**Date:** 2026-02-02
**Status:** Planning
**Related:** SMS webhook mount (same pattern needed)

---

## Problem

We need to share a folder between:
- **VM100 LXC** (where AI agents run)
- **Coolify Docker** (where aim.measai.app runs)

Both are on the same Hetzner AX42 host (mach42v2), but isolated from each other.

We do NOT want to expose the entire Maestro repo to the Docker container.

---

## Solution: Double Mount

Mount a specific folder through the host as an intermediary:

```
VM100 LXC ──► Hetzner Host ──► Docker Container
   │              │                  │
   │              │                  │
   ▼              ▼                  ▼
/home/maestro/   /var/lib/lxc/100/  /app/rooms/
Measai-Maestro/  rootfs/home/...    (volume mount)
External/aim-    External/aim-
measai-app/      measai-app/
rooms/           rooms/
```

### Path Mapping

| Location | Path |
|----------|------|
| Inside VM100 (LXC 100) | `/home/maestro/Measai-Maestro/External/aim-measai-app/rooms/` |
| On Hetzner Host | `/var/lib/lxc/100/rootfs/home/maestro/Measai-Maestro/External/aim-measai-app/rooms/` |
| Inside Docker | `/app/rooms/` |

---

## How It Works

1. **LXC rootfs exposure:** Proxmox LXC containers store their filesystem at `/var/lib/lxc/<ID>/rootfs/` on the host. This is directly accessible from the host.

2. **Docker volume mount:** Coolify/Docker can mount any host path into a container using `-v` or volume configuration.

3. **Result:** Files written in Docker appear instantly in VM100, and vice versa.

---

## Implementation Steps

### Step 1: Create rooms folder in VM100

```bash
# SSH to VM100 or via lxc-attach
mkdir -p /home/maestro/Measai-Maestro/External/aim-measai-app/rooms/
chmod 777 /home/maestro/Measai-Maestro/External/aim-measai-app/rooms/
```

### Step 2: Verify host can see the path

```bash
# On Hetzner host (mach42v2)
ls -la /var/lib/lxc/100/rootfs/home/maestro/Measai-Maestro/External/aim-measai-app/rooms/
```

### Step 3: Configure Coolify volume mount

In Coolify UI or docker-compose:

```yaml
volumes:
  - /var/lib/lxc/100/rootfs/home/maestro/Measai-Maestro/External/aim-measai-app/rooms:/app/rooms
```

### Step 4: Update container environment

```
ROOMS_DIR=/app/rooms
```

### Step 5: Test bidirectional sync

```bash
# From VM100
echo "test from vm100" > /home/maestro/Measai-Maestro/External/aim-measai-app/rooms/test.txt

# From Docker (via Coolify exec or docker exec)
cat /app/rooms/test.txt  # Should show "test from vm100"

# Write from Docker
echo "test from docker" >> /app/rooms/test.txt

# Verify in VM100
cat /home/maestro/Measai-Maestro/External/aim-measai-app/rooms/test.txt
```

---

## Permission Considerations

| Issue | Solution |
|-------|----------|
| Docker user can't write | `chmod 777` on rooms folder, or match UID/GID |
| LXC user can't read Docker files | Ensure Docker writes with permissive umask |
| SELinux/AppArmor blocking | May need `:z` or `:Z` suffix on volume mount |

### Recommended permission setup

```bash
# In VM100
chown -R 1000:1000 /home/maestro/Measai-Maestro/External/aim-measai-app/rooms/
chmod -R 775 /home/maestro/Measai-Maestro/External/aim-measai-app/rooms/
```

---

## Same Pattern Needed For

- **aim.measai.app** - AIM rooms (this document)
- **sms.measai.app** - Twilio webhook incoming messages
- Future external services needing file-based communication

---

## Monitoring Integration

Once mounted, VM100 agents can:

1. **Watch for new files:** Use inotify or polling
2. **AIM Liaison Agent:** Dedicated agent monitors rooms folder
3. **Cor-daemon integration:** Fire sapwave when new message detected

---

## Troubleshooting

### Files not appearing

1. Check host path exists: `ls /var/lib/lxc/100/rootfs/...`
2. Check Docker mount: `docker inspect <container> | grep Mounts`
3. Check permissions on all three levels

### Permission denied

1. Check ownership: `ls -la` at each level
2. Try `chmod 777` temporarily to isolate issue
3. Check if SELinux is enforcing: `getenforce`

### Container can't start

1. Volume path must exist before container starts
2. Path typos are common - verify exact path
3. Coolify may need container restart after volume change

---

## Security Notes

- Only the `rooms/` folder is exposed, not the entire repo
- Jonathan/AIMs cannot access signals, code, or secrets
- Docker runs with limited filesystem view
- Easy to revoke: remove volume mount in Coolify

---

*Document created: 2026-02-02 by Claude (Team Lead)*
*For discussion with: Taynor, Hermes (SMS webhook experience)*
