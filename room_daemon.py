#!/usr/bin/env python3
"""Room daemon - polls room inboxes, consolidates to thread.md.

Auto-detects @mentions and adds participants to room.yaml.
Gracefully skips tmux notifications when not available (e.g. in Docker).

Env: ROOMS_DIR (default: /data/rooms)
"""

import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOMS_DIR = Path(os.environ.get("ROOMS_DIR", "/data/rooms"))


def get_active_agents() -> dict[str, str]:
    """Return {lowercase_name: DisplayName} for active tmux agent sessions."""
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return {}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}
    agents = {}
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if line.endswith("_session"):
            name = line[: -len("_session")]
            agents[name] = name.capitalize()
    return agents


def extract_sender(filename: str) -> str:
    match = re.match(r"\d{8}-\d{6}-(.+)\.md$", filename)
    if match:
        return match.group(1)
    return Path(filename).stem


def auto_add_participants(room_dir: Path, sender: str, body: str) -> list[str]:
    """Detect @mentions, add sender + mentioned agents to room.yaml."""
    room_yaml = room_dir / "room.yaml"

    if room_yaml.exists():
        with open(room_yaml, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {"created_by": sender, "created_at": datetime.now(timezone.utc).isoformat()}

    participants = config.get("participants", [])
    original_count = len(participants)

    if sender not in participants:
        participants.append(sender)

    # Match @mentions against active tmux sessions
    active_agents = get_active_agents()
    at_mentions = re.findall(r"@(\w+)", body)
    for mention in at_mentions:
        mention_lower = mention.lower()
        if mention_lower in active_agents:
            display_name = active_agents[mention_lower]
            if display_name not in participants:
                participants.append(display_name)
                print(f"  Auto-added participant: {display_name} (from @{mention})")

    if len(participants) != original_count:
        config["participants"] = participants
        with open(room_yaml, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False)

    return participants


def consolidate(message_path: Path) -> None:
    """Read inbox message, append to thread.md, move to processed."""
    room_dir = message_path.parent.parent
    room_name = room_dir.name

    body = message_path.read_text(encoding="utf-8").strip()
    sender = extract_sender(message_path.name)
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")

    thread_path = room_dir / "thread.md"
    entry = f"\n---\n\n**{sender}** ({timestamp}):\n{body}\n"
    with open(thread_path, "a", encoding="utf-8") as f:
        f.write(entry)

    processed_dir = room_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(message_path), str(processed_dir / message_path.name))

    print(f"  Consolidated: {sender} -> {room_name}/thread.md ({len(body)} chars)")

    participants = auto_add_participants(room_dir, sender, body)
    mentions = [name for name in participants if f"@{name}" in body]
    notify_participants(room_name, sender, body, participants, mentions)


def notify_participants(
    room_name: str, sender: str, body: str,
    participants: list[str], mentions: list[str],
) -> None:
    """Notify participants via tmux (skips gracefully if tmux unavailable)."""
    thread_path = f"AI_Agents/signals/rooms/{room_name}/thread.md"

    for participant in participants:
        if participant == sender:
            continue

        session = f"{participant.lower()}_session"

        try:
            check = subprocess.run(
                ["tmux", "has-session", "-t", session],
                capture_output=True, timeout=5,
            )
            if check.returncode != 0:
                continue
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

        ts_tag = datetime.now(timezone.utc).strftime("%H:%M")
        inbox_path = f"AI_Agents/signals/rooms/{room_name}/inbox"
        ts_hint = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        reply_file = f"{inbox_path}/{ts_hint}-{participant}.md"
        is_mentioned = participant in mentions
        if is_mentioned:
            msg = (
                f"[Room:{room_name} {ts_tag}]: @{participant} from {sender}. "
                f"Read: cat {thread_path} -- "
                f"WRITE reply to {reply_file} (NOT thread.md) -- "
                f"Keep short (1-2 lines). No confirmations of confirmations."
            )
        else:
            msg = (
                f"[Room:{room_name} {ts_tag}]: New msg from {sender}. "
                f"Read: tail -50 {thread_path} (need more context? tail -200 or -500) -- "
                f"Default: SILENCE. Only reply if your SME domain adds new info. "
                f"If replying, WRITE to {reply_file} (NOT thread.md, 1-2 lines)."
            )

        try:
            subprocess.run(["tmux", "send-keys", "-t", session, msg], timeout=5)
            time.sleep(0.5)
            subprocess.run(["tmux", "send-keys", "-t", session, "Enter"], timeout=5)
            print(f"  Notified: {participant} ({session})")
            time.sleep(0.3)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass


def scan_rooms() -> None:
    """Scan all room inboxes and consolidate any .md files found."""
    for room_dir in ROOMS_DIR.iterdir():
        if not room_dir.is_dir():
            continue
        inbox_dir = room_dir / "inbox"
        if not inbox_dir.exists():
            continue
        for md_file in sorted(inbox_dir.glob("*.md")):
            ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
            print(f"[{ts}] Found: {room_dir.name}/inbox/{md_file.name}")
            try:
                consolidate(md_file)
            except Exception as exc:
                print(f"  ERROR: {exc}")


def main():
    ROOMS_DIR.mkdir(parents=True, exist_ok=True)

    # Create default lobby room if no rooms exist
    lobby = ROOMS_DIR / "lobby"
    if not any(d.is_dir() for d in ROOMS_DIR.iterdir() if (d / "inbox").exists()):
        (lobby / "inbox").mkdir(parents=True, exist_ok=True)
        (lobby / "processed").mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        (lobby / "thread.md").write_text(
            f"# Room: lobby\n**Created:** {now.strftime('%Y-%m-%dT%H:%M:%SZ')}\n",
            encoding="utf-8",
        )
        config = {"created_by": "system", "created_at": now.isoformat(), "participants": []}
        with open(lobby / "room.yaml", "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False)
        print("Created default lobby room.")

    rooms = [d.name for d in ROOMS_DIR.iterdir() if d.is_dir() and (d / "inbox").exists()]
    print(f"Room daemon running (polling). Watching {len(rooms)} room(s): {', '.join(rooms)}")
    print("Scanning every 1s.\n")

    try:
        while True:
            scan_rooms()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nRoom daemon stopped.")


if __name__ == "__main__":
    main()
