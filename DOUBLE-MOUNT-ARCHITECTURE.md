# AIM Shared Directory Architecture

**Date:** 2026-02-02
**Status:** Implementing
**Related:** SMS webhook mount (same pattern)

---

## Problem

We need to share a folder between:
- **VM100 LXC** (where AI agents run)
- **Coolify Docker** (where aim.measai.app runs)

Both are on the same Hetzner AX42 host (mach42v2), but isolated from each other.

We do NOT want to expose the entire Maestro repo to the Docker container.

---

## Discovery: LXC Uses Disk Image Storage

**Initial approach failed:** We tried to use `/var/lib/lxc/100/rootfs/` but LXC 100 uses Proxmox disk image storage (`local:100/vm-100-disk-0.raw`), not directory storage. The filesystem is inside the disk image and not directly accessible from the host.

---

## Solution: Shared Host Directory with Bind Mounts

Create a dedicated shared directory on the Proxmox host, then bind mount it into both the LXC and the Docker container:

```
Proxmox Host: /mnt/aim-shared/rooms/
       │
       ├──► (pct bind mount mp1)
       │           │
       │           ▼
       │    VM100 LXC: /mnt/aim-shared/rooms/
       │
       └──► (Docker volume mount)
                   │
                   ▼
            Docker: /app/rooms/
```

### Path Mapping

| Location | Path |
|----------|------|
| Proxmox Host (mach42v2) | `/mnt/aim-shared/rooms/` |
| Inside VM100 (LXC 100) | `/mnt/aim-shared/rooms/` |
| Inside Docker | `/app/rooms/` |

---

## Why This Is Better

1. **Clean separation** - Dedicated shared space, not exposing internal paths
2. **Proven pattern** - Same as existing `mp0: /mnt/measai-shared` mount
3. **Storage agnostic** - Works with any LXC storage type (disk image, directory, ZFS)
4. **Simple paths** - Same path on host and LXC, easy to reason about

---

## Implementation Steps

### Step 1: Create shared directory on Proxmox host

```bash
# SSH to mach42v2 (Proxmox host)
mkdir -p /mnt/aim-shared/rooms/
chmod 777 /mnt/aim-shared/rooms/
```

### Step 2: Add bind mount to LXC 100

```bash
# On Proxmox host
pct set 100 -mp1 /mnt/aim-shared,mp=/mnt/aim-shared

# Or edit /etc/pve/lxc/100.conf directly:
# mp1: /mnt/aim-shared,mp=/mnt/aim-shared
```

### Step 3: Restart LXC to pick up mount (or mount live)

```bash
# Option A: Restart container
pct restart 100

# Option B: Mount without restart (if supported)
pct mount 100
```

### Step 4: Verify mount inside VM100

```bash
# From VM100
ls -la /mnt/aim-shared/rooms/
echo "test from vm100" > /mnt/aim-shared/rooms/test.txt
```

### Step 5: Configure Coolify Docker volume

In Coolify UI, add volume mount for aim-measai-app:

```
/mnt/aim-shared/rooms:/app/rooms
```

Or in docker-compose:

```yaml
volumes:
  - /mnt/aim-shared/rooms:/app/rooms
```

### Step 6: Update container environment

```
ROOMS_DIR=/app/rooms
```

### Step 7: Test bidirectional sync

```bash
# From VM100
echo "hello from vm100" > /mnt/aim-shared/rooms/test.txt

# From Docker
docker exec <container> cat /app/rooms/test.txt
# Should show: "hello from vm100"

# Write from Docker
docker exec <container> sh -c 'echo "hello from docker" >> /app/rooms/test.txt'

# Verify in VM100
cat /mnt/aim-shared/rooms/test.txt
# Should show both lines
```

---

## Permission Considerations

| Issue | Solution |
|-------|----------|
| Docker user can't write | `chmod 777` on rooms folder, or match UID/GID |
| LXC user can't read Docker files | Ensure Docker writes with permissive umask |

### Recommended permission setup

```bash
# On Proxmox host (sets permissions before mount)
chmod -R 777 /mnt/aim-shared/rooms/
```

---

## Symlink for Convenience (Optional)

To make the path match our repo structure inside VM100:

```bash
# Inside VM100
ln -s /mnt/aim-shared/rooms /home/maestro/Measai-Maestro/External/aim-measai-app/rooms
```

This lets agents use the familiar repo path while files actually live in the shared mount.

---

## Same Pattern For Other Services

This architecture works for any service needing file-based communication:

- **aim.measai.app** - AIM rooms (this document)
- **sms.measai.app** - Twilio webhook incoming messages
- Future external services

---

## Monitoring Integration

Once mounted, VM100 agents can:

1. **Watch for new files:** Use inotify or polling on `/mnt/aim-shared/rooms/`
2. **AIM Liaison Agent:** Dedicated agent monitors rooms folder
3. **Cor-daemon integration:** Fire sapwave when new message detected

---

## Security Notes

- Only the `rooms/` folder is exposed, not the entire repo
- Jonathan/AIMs cannot access signals, code, or secrets
- Docker runs with limited filesystem view
- Easy to revoke: remove volume mount in Coolify

---

*Document created: 2026-02-02 by Claude (Team Lead)*
*Updated: 2026-02-02 - Changed from rootfs approach to shared host directory*
