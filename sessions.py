"""Session persistence for the Inkling agent.

Every session autosaves to ~/.inkling/sessions/<id>.json after each turn, so a
crash or a closed terminal loses nothing. `--continue` reopens the most recent
session, `--resume <id>` (or /resume in-session) reopens a specific one, and
/sessions lists what's there.

The system message is not stored — it is rebuilt fresh on resume so mode, cwd,
skills and memory reflect the present, not the past.
"""

import json
import re
import time
from pathlib import Path

DIR = Path.home() / ".inkling" / "sessions"


def new_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def _title(messages: list[dict]) -> str:
    for msg in messages:
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            line = msg["content"].strip().splitlines()[0]
            return line[:60]
    return "(empty)"


def save(session_id: str, messages: list[dict], todos: list[dict], meta: dict) -> Path:
    DIR.mkdir(parents=True, exist_ok=True)
    body = [m for m in messages if m.get("role") != "system"]
    payload = {
        "id": session_id,
        "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cwd": str(Path.cwd()),
        "title": _title(body),
        "turns": sum(1 for m in body if m.get("role") == "user"),
        **meta,
        "messages": body,
        "todos": todos,
    }
    path = DIR / f"{session_id}.json"
    path.write_text(json.dumps(payload, indent=1, default=str))
    return path


def load(ref: str) -> dict | None:
    """Load by exact id or unique prefix."""
    if not DIR.is_dir():
        return None
    exact = DIR / f"{ref}.json"
    if exact.is_file():
        return json.loads(exact.read_text())
    hits = [p for p in DIR.glob("*.json") if p.stem.startswith(ref)]
    if len(hits) == 1:
        return json.loads(hits[0].read_text())
    return None


def latest() -> dict | None:
    entries = list_sessions(limit=1)
    return load(entries[0]["id"]) if entries else None


def list_sessions(limit: int = 15) -> list[dict]:
    """Newest first, metadata only."""
    if not DIR.is_dir():
        return []
    out = []
    for path in sorted(DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        out.append({k: data.get(k) for k in ("id", "updated", "title", "turns", "cwd")})
    return out


def ids() -> list[str]:
    return [m["id"] for m in list_sessions(limit=30)]


def sanitize(ref: str) -> str:
    return re.sub(r"[^\w.-]", "", ref)
