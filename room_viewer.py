#!/usr/bin/env python3
"""Room chat web UI - overview, thread viewer, room creation, chat input.

Live-refreshes via JS fetch (no full page reload). Pauses refresh when typing.
Env: ROOMS_DIR (default: /data/rooms), DEFAULT_SENDER (default: Guest)
"""

import argparse
import html
import os
import re
import subprocess
import urllib.parse
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

import yaml


def get_online_agents() -> list[dict]:
    """Get list of online agents from tmux sessions.

    Returns list of dicts with 'name' and 'status' keys.
    """
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}:#{session_attached}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return []

        agents = []
        for line in result.stdout.strip().split("\n"):
            if not line or ":" not in line:
                continue
            session, attached = line.rsplit(":", 1)
            # Filter to agent sessions (ending with _session)
            if session.endswith("_session"):
                name = session.replace("_session", "").title()
                status = "active" if attached == "1" else "idle"
                agents.append({"name": name, "status": status})

        return sorted(agents, key=lambda a: a["name"])
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def get_room_message_counts(room_name: str) -> dict[str, int]:
    """Count messages per sender in a room's thread.md.

    Returns dict mapping sender name to message count.
    """
    thread_path = ROOMS_DIR / room_name / "thread.md"
    if not thread_path.exists():
        return {}

    counts: dict[str, int] = {}
    raw = thread_path.read_text(encoding="utf-8")

    # Match **SenderName** (HH:MM:SS): pattern
    for match in re.finditer(r"\*\*(.+?)\*\*\s*\(\d{2}:\d{2}:\d{2}\):", raw):
        sender = match.group(1)
        counts[sender] = counts.get(sender, 0) + 1

    return counts

ROOMS_DIR = Path(os.environ.get("ROOMS_DIR", "/data/rooms"))
DEFAULT_SENDER = os.environ.get("DEFAULT_SENDER", "Christian")

STYLE = """
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         margin: 40px auto; padding: 0 20px;
         background: #1a1a2e; color: #e0e0e0; }
  .layout { display: flex; max-width: 1100px; margin: 0 auto; gap: 24px; }
  .main-content { flex: 1; max-width: 800px; }
  .sidebar { width: 200px; flex-shrink: 0; position: sticky; top: 20px; align-self: flex-start; }
  h1 { color: #e94560; border-bottom: 2px solid #e94560; padding-bottom: 8px; }
  h2 { color: #e94560; }
  .meta { color: #888; font-size: 0.9em; margin-bottom: 20px; }
  .message { background: #16213e; border-left: 3px solid #0f3460;
              padding: 12px 16px; margin: 16px 0; border-radius: 0 8px 8px 0; }
  .message.human { background: #1e2a4a; border-left-color: #4a90d9; }
  .message .sender { color: #e94560; font-weight: bold; }
  .message .time { color: #888; font-size: 0.85em; }
  .message .body { margin-top: 8px; white-space: pre-wrap; line-height: 1.5; }
  .message .body h1, .message .body h2 { color: #e94560; margin: 8px 0 4px; font-size: 1em; }
  .message .body li { margin: 2px 0; }
  hr { border: none; border-top: 1px solid #333; margin: 20px 0; }
  .status { text-align: center; color: #666; font-size: 0.8em; margin-top: 30px; }
  a { color: #e94560; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .room-card { background: #16213e; border: 1px solid #0f3460; border-radius: 8px;
               padding: 16px 20px; margin: 12px 0; }
  .room-card h3 { margin: 0 0 8px; }
  .room-card .info { color: #888; font-size: 0.9em; }
  .chat-form { background: #16213e; border: 1px solid #0f3460; border-radius: 8px;
               padding: 16px; margin-top: 24px; }
  .chat-form input[type=text] { background: #0f3460; color: #e0e0e0; border: 1px solid #333;
                                  padding: 8px 12px; border-radius: 4px; width: 120px; }
  .chat-form textarea { background: #0f3460; color: #e0e0e0; border: 1px solid #333;
                         padding: 8px 12px; border-radius: 4px; width: 100%;
                         min-height: 60px; resize: vertical; box-sizing: border-box; }
  .chat-form button { background: #e94560; color: white; border: none; padding: 8px 20px;
                       border-radius: 4px; cursor: pointer; font-size: 1em; margin-top: 8px; }
  .chat-form button:hover { background: #d63851; }
  .chat-form label { color: #888; font-size: 0.9em; display: block; margin: 8px 0 4px; }
  .flash { background: #0f3460; border: 1px solid #e94560; border-radius: 4px;
           padding: 10px 16px; margin-bottom: 16px; color: #e0e0e0; }
  /* Sidebar: Online Agents */
  .agents-box { background: #16213e; border: 1px solid #0f3460; border-radius: 8px;
                padding: 12px 16px; }
  .agents-box h4 { margin: 0 0 12px; color: #e94560; font-size: 0.95em;
                   border-bottom: 1px solid #0f3460; padding-bottom: 8px; }
  .agent-item { display: flex; align-items: center; padding: 6px 0; font-size: 0.9em; }
  .agent-dot { width: 8px; height: 8px; border-radius: 50%; margin-right: 10px; }
  .agent-dot.active { background: #4ade80; box-shadow: 0 0 6px #4ade80; }
  .agent-dot.idle { background: #fbbf24; }
  .agent-dot.offline { background: #666; }
  .agent-name { color: #e0e0e0; }
  .agents-none { color: #666; font-size: 0.85em; font-style: italic; }
  .msg-count { color: #888; font-size: 0.85em; }
"""

LIVE_REFRESH_SCRIPT = """
<script>
setInterval(async () => {
  try {
    const active = document.activeElement;
    if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA')) return;
    const resp = await fetch(location.pathname);
    if (!resp.ok) return;
    const html = await resp.text();
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    document.getElementById('content').innerHTML = doc.getElementById('content').innerHTML;
  } catch(e) {}
}, INTERVAL);
// Scroll to bottom if flash message present (just sent a message)
if (location.search.includes('flash=')) {
  window.scrollTo(0, document.body.scrollHeight);
}
</script>
"""

PAGE_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>{style}</style>
</head>
<body>
<div id="content">
<div class="layout">
<div class="main-content">
{content}
</div>
<div class="sidebar">
{sidebar}
</div>
</div>
</div>
{script}
</body>
</html>"""


def render_agents_sidebar(room_name: str = "") -> str:
    """Render the online agents sidebar box(es).

    Overview page: Single "Online Agents" list.
    Room page: Two boxes - "Participants" (with counts) and "Available Agents".
    """
    agents = get_online_agents()
    agent_status = {a["name"]: a["status"] for a in agents}
    online_names = set(agent_status.keys())

    # Overview page - single list
    if not room_name:
        parts = ['<div class="agents-box">', '<h4>Online Agents</h4>']
        if agents:
            for agent in agents:
                dot_class = "active" if agent["status"] == "active" else "idle"
                parts.append(
                    f'<div class="agent-item">'
                    f'<span class="agent-dot {dot_class}"></span>'
                    f'<span class="agent-name">{html.escape(agent["name"])}</span>'
                    f'</div>'
                )
        else:
            parts.append('<div class="agents-none">No agents online</div>')
        parts.append('</div>')
        return "\n".join(parts)

    # Room page - two boxes
    msg_counts = get_room_message_counts(room_name)
    participants = {name: count for name, count in msg_counts.items() if count > 0}
    participant_names = set(participants.keys())

    # Available = online agents not in participants
    available_names = online_names - participant_names

    parts = []

    # Box 1: Participants (sorted by message count, descending)
    parts.append('<div class="agents-box">')
    parts.append(f'<h4>Participants ({len(participants)})</h4>')
    if participants:
        for name, count in sorted(participants.items(), key=lambda x: -x[1]):
            status = agent_status.get(name, "offline")
            if status == "active":
                dot_class = "active"
            elif status == "idle":
                dot_class = "idle"
            else:
                dot_class = "offline"
            parts.append(
                f'<div class="agent-item">'
                f'<span class="agent-dot {dot_class}"></span>'
                f'<span class="agent-name">{html.escape(name)} '
                f'<span class="msg-count">({count})</span></span>'
                f'</div>'
            )
    else:
        parts.append('<div class="agents-none">No messages yet</div>')
    parts.append('</div>')

    # Box 2: Available Agents (online but not participated)
    parts.append('<div class="agents-box" style="margin-top: 16px;">')
    parts.append(f'<h4>Available ({len(available_names)})</h4>')
    if available_names:
        for name in sorted(available_names):
            status = agent_status.get(name, "idle")
            dot_class = "active" if status == "active" else "idle"
            parts.append(
                f'<div class="agent-item">'
                f'<span class="agent-dot {dot_class}"></span>'
                f'<span class="agent-name">{html.escape(name)}</span>'
                f'</div>'
            )
    else:
        parts.append('<div class="agents-none">All agents participating</div>')
    parts.append('</div>')

    return "\n".join(parts)


def render_overview(sort: str = "recent") -> str:
    # Get all rooms with their metadata
    room_data = []
    for d in ROOMS_DIR.iterdir():
        if d.is_dir() and (d / "thread.md").exists():
            thread_path = d / "thread.md"
            thread = thread_path.read_text(encoding="utf-8")
            msg_count = thread.count("\n---\n")
            mtime = thread_path.stat().st_mtime
            room_data.append({
                "dir": d,
                "name": d.name,
                "msg_count": msg_count,
                "mtime": mtime,
            })

    # Sort based on parameter
    if sort == "name":
        room_data.sort(key=lambda r: r["name"])
    elif sort == "messages":
        room_data.sort(key=lambda r: -r["msg_count"])
    else:  # "recent" is default
        room_data.sort(key=lambda r: -r["mtime"])

    parts = ['<h1>Room Chat</h1>']

    # Sort options
    sort_links = []
    for key, label in [("recent", "Recent"), ("name", "A-Z"), ("messages", "Messages")]:
        if sort == key:
            sort_links.append(f'<strong>{label}</strong>')
        else:
            sort_links.append(f'<a href="/?sort={key}">{label}</a>')
    parts.append(f'<div class="meta">{len(room_data)} room(s) &middot; Sort: {" | ".join(sort_links)}</div>')

    for room in room_data:
        room_dir = room["dir"]
        name = room["name"]
        msg_count = room["msg_count"]
        participants = ""
        room_yaml = room_dir / "room.yaml"
        if room_yaml.exists():
            with open(room_yaml, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            p_list = config.get("participants", [])
            participants = ", ".join(p_list) if p_list else "none yet"

        parts.append(
            f'<div class="room-card">'
            f'<h3><a href="/{name}">{name}</a></h3>'
            f'<div class="info">{msg_count} messages &middot; Participants: {html.escape(participants)}</div>'
            f'</div>'
        )

    parts.append(
        '<div class="chat-form">'
        '<h3>Create New Room</h3>'
        '<form method="POST" action="/">'
        '<label for="room_name">Room name (lowercase, dashes ok):</label>'
        '<input type="text" id="room_name" name="room_name" placeholder="e.g. sprint-planning" '
        'pattern="[a-z0-9][a-z0-9-]*" required />'
        '<label for="first_msg">First message (use @Name to invite participants):</label>'
        '<textarea id="first_msg" name="first_msg" '
        'placeholder="e.g. Hello team! Let\'s discuss..." required></textarea>'
        '<button type="submit">Create Room</button>'
        '</form>'
        '</div>'
    )

    parts.append('<div class="status">Auto-refreshes every 5s</div>')

    return PAGE_TEMPLATE.format(
        title="Room Chat - Overview",
        style=STYLE,
        content="\n".join(parts),
        sidebar=render_agents_sidebar(),
        script=LIVE_REFRESH_SCRIPT.replace("INTERVAL", "5000"),
    )


def render_thread(room_name: str, flash: str = "") -> str:
    thread_path = ROOMS_DIR / room_name / "thread.md"
    if not thread_path.exists():
        return PAGE_TEMPLATE.format(
            title=f"Room: {room_name}",
            style=STYLE,
            content=f"<h1>Room not found: {html.escape(room_name)}</h1><p><a href='/'>&larr; All rooms</a></p>",
            sidebar=render_agents_sidebar(room_name),
            script="",
        )

    raw = thread_path.read_text(encoding="utf-8")
    sections = raw.split("\n---\n")

    parts = ['<p><a href="/">&larr; All rooms</a></p>']

    header = sections[0].strip()
    parts.append(f"<div class='meta'>{simple_md(header)}</div>")

    for section in sections[1:]:
        section = section.strip()
        if not section:
            continue
        match = re.match(r"\*\*(.+?)\*\*\s*\((\d{2}:\d{2}:\d{2})\):\s*(.*)", section, re.DOTALL)
        if match:
            sender_raw = match.group(1)
            sender = html.escape(sender_raw)
            timestamp = html.escape(match.group(2))
            body = simple_md(match.group(3).strip())
            msg_class = "message human" if sender_raw == "Christian" else "message"
            parts.append(
                f'<div class="{msg_class}">'
                f'<span class="sender">{sender}</span> '
                f'<span class="time">({timestamp} UTC)</span>'
                f'<div class="body">{body}</div>'
                f'</div>'
            )
        else:
            parts.append(f'<div class="message"><div class="body">{simple_md(section)}</div></div>')

    if flash:
        parts.append(f'<div class="flash">{html.escape(flash)}</div>')

    parts.append(
        f'<div class="chat-form">'
        f'<form method="POST" action="/{html.escape(room_name)}">'
        f'<label for="sender">Your name:</label>'
        f'<input type="text" id="sender" name="sender" value="{html.escape(DEFAULT_SENDER)}" required />'
        f'<label for="msg">Message:</label>'
        f'<textarea id="msg" name="msg" placeholder="Type your message..." required></textarea>'
        f'<button type="submit">Send to room</button>'
        f'</form>'
        f'</div>'
    )

    parts.append(
        '<div class="status">Auto-refreshes every 3s &middot; '
        'Messages go to inbox &rarr; daemon consolidates to thread</div>'
    )

    parts.append('<p><a href="/">&larr; All rooms</a></p>')

    return PAGE_TEMPLATE.format(
        title=f"Room: {room_name}",
        style=STYLE,
        content="\n".join(parts),
        sidebar=render_agents_sidebar(room_name),
        script=LIVE_REFRESH_SCRIPT.replace("INTERVAL", "3000"),
    )


def simple_md(text: str) -> str:
    """Minimal markdown to HTML."""
    text = html.escape(text)
    text = re.sub(r"^## (.+)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
    text = re.sub(r"^# (.+)$", r"<h1>\1</h1>", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"^- (.+)$", r"<li>\1</li>", text, flags=re.MULTILINE)
    text = re.sub(r"^  - (.+)$", r"<li style='margin-left:20px'>\1</li>", text, flags=re.MULTILINE)
    return text


class RoomHandler(BaseHTTPRequestHandler):
    default_room = "lobby"

    def do_GET(self):
        path = self.path.strip("/").split("?")[0]

        if not path:
            sort = "recent"
            if "?" in self.path:
                qs = urllib.parse.parse_qs(self.path.split("?", 1)[1])
                sort = qs.get("sort", ["recent"])[0]
            content = render_overview(sort=sort)
        elif (ROOMS_DIR / path / "thread.md").exists():
            flash = ""
            if "?" in self.path:
                qs = urllib.parse.parse_qs(self.path.split("?", 1)[1])
                flash = qs.get("flash", [""])[0]
            content = render_thread(path, flash=flash)
        else:
            content = render_thread(self.default_room)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def do_POST(self):
        path = self.path.strip("/").split("?")[0]

        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length).decode("utf-8")
        params = urllib.parse.parse_qs(raw_body)

        if not path:
            self._handle_create_room(params)
        else:
            room_name = path if (ROOMS_DIR / path).is_dir() else self.default_room
            self._handle_chat_message(room_name, params)

    def _handle_create_room(self, params):
        room_input = params.get("room_name", [""])[0].strip()
        first_msg = params.get("first_msg", [""])[0].strip()

        safe_name = re.sub(r"[^a-z0-9-]", "", room_input.lower().replace(" ", "-"))
        if not safe_name:
            self.send_response(303)
            self.send_header("Location", "/?flash=Invalid+room+name")
            self.end_headers()
            return

        room_dir = ROOMS_DIR / safe_name
        if room_dir.exists():
            self.send_response(303)
            self.send_header("Location", f"/{safe_name}?flash=Room+already+exists")
            self.end_headers()
            return

        (room_dir / "inbox").mkdir(parents=True, exist_ok=True)
        (room_dir / "processed").mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc)
        (room_dir / "thread.md").write_text(
            f"# Room: {safe_name}\n**Created:** {now.strftime('%Y-%m-%dT%H:%M:%SZ')}\n",
            encoding="utf-8",
        )
        config = {
            "created_by": DEFAULT_SENDER,
            "created_at": now.isoformat(),
            "participants": [DEFAULT_SENDER],
        }
        with open(room_dir / "room.yaml", "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False)

        if first_msg:
            safe_sender = re.sub(r"[^a-zA-Z0-9_-]", "", DEFAULT_SENDER) or "Guest"
            ts = now.strftime("%Y%m%d-%H%M%S")
            (room_dir / "inbox" / f"{ts}-{safe_sender}.md").write_text(first_msg, encoding="utf-8")

        flash = f"Room '{safe_name}' created"
        self.send_response(303)
        self.send_header("Location", f"/{safe_name}?flash={urllib.parse.quote(flash)}")
        self.end_headers()

    def _handle_chat_message(self, room_name, params):
        sender = params.get("sender", ["Guest"])[0].strip()
        msg = params.get("msg", [""])[0].strip()

        if sender and msg:
            safe_sender = re.sub(r"[^a-zA-Z0-9_-]", "", sender) or "Guest"
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            filename = f"{ts}-{safe_sender}.md"

            inbox_dir = ROOMS_DIR / room_name / "inbox"
            inbox_dir.mkdir(parents=True, exist_ok=True)
            (inbox_dir / filename).write_text(msg, encoding="utf-8")

            flash = f"Message sent as {safe_sender}"
        else:
            flash = "Message empty - not sent"

        self.send_response(303)
        self.send_header("Location", f"/{room_name}?flash={urllib.parse.quote(flash)}")
        self.end_headers()

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description="Room chat web UI")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--room", default="lobby")
    args = parser.parse_args()

    RoomHandler.default_room = args.room
    server = HTTPServer(("0.0.0.0", args.port), RoomHandler)

    ROOMS_DIR.mkdir(parents=True, exist_ok=True)
    rooms = [d.name for d in ROOMS_DIR.iterdir() if d.is_dir() and (d / "thread.md").exists()]
    print(f"Room viewer: http://localhost:{args.port}")
    print(f"Available rooms: {', '.join(rooms) or 'none yet (create one!)'}")
    print(f"Overview: http://localhost:{args.port}/")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nViewer stopped.")
    server.server_close()


if __name__ == "__main__":
    main()
