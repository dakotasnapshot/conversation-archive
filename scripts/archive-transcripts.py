#!/usr/bin/env python3
"""
Conversation Archive for OpenClaw
==================================
Archives full session transcripts as searchable markdown files.
Reads OpenClaw JSONL session files, converts to clean markdown,
and saves to conversations/YYYY/MM/DD/ in the workspace.

Usage:
  python3 archive-transcripts.py              # Archive all new/changed sessions
  python3 archive-transcripts.py --force      # Re-archive everything
  python3 archive-transcripts.py --stats      # Show archive statistics

Environment variables:
  ARCHIVE_WORKSPACE    — Workspace root (default: ~/.openclaw/workspace)
  ARCHIVE_AGENTS_DIR   — Agent sessions dir (default: ~/.openclaw/agents)
  ARCHIVE_MIN_MESSAGES — Min user messages to archive (default: 3)
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Configuration via environment or defaults
WORKSPACE = Path(os.environ.get("ARCHIVE_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
AGENTS_DIR = Path(os.environ.get("ARCHIVE_AGENTS_DIR", os.path.expanduser("~/.openclaw/agents")))
MIN_USER_MESSAGES = int(os.environ.get("ARCHIVE_MIN_MESSAGES", "3"))

CONVERSATIONS_DIR = WORKSPACE / "conversations"
STATE_FILE = CONVERSATIONS_DIR / ".archive-state.json"


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"archived": {}, "lastRun": None}


def save_state(state):
    CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
    state["lastRun"] = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_file_hash(path):
    stat = path.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def parse_session_jsonl(filepath):
    session_info = {}
    messages = []
    compactions = []

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            obj_type = obj.get("type")

            if obj_type == "session":
                session_info = {
                    "id": obj.get("id"),
                    "version": obj.get("version"),
                    "timestamp": obj.get("timestamp"),
                }

            elif obj_type == "compaction":
                compactions.append({
                    "timestamp": obj.get("timestamp"),
                    "summary": obj.get("summary", ""),
                })

            elif obj_type == "message":
                msg = obj.get("message", {})
                role = msg.get("role")
                if not role:
                    continue

                content = msg.get("content", "")
                timestamp = obj.get("timestamp", "")

                # Extract text content
                if isinstance(content, list):
                    text_parts = []
                    for part in content:
                        if isinstance(part, dict):
                            if part.get("type") == "text":
                                text_parts.append(part.get("text", ""))
                            elif part.get("type") == "tool_use":
                                text_parts.append(f"[Tool: {part.get('name', '?')}]")
                            elif part.get("type") == "tool_result":
                                result = part.get("content", "")
                                if isinstance(result, str):
                                    preview = result[:200] + "..." if len(result) > 200 else result
                                    text_parts.append(f"[Tool result: {preview}]")
                                elif isinstance(result, list):
                                    text_parts.append(f"[Tool result: {len(result)} parts]")
                    content_text = "\n".join(text_parts)
                elif isinstance(content, str):
                    content_text = content
                else:
                    content_text = str(content)

                # Handle empty assistant messages with tool calls
                if role == "assistant" and not content_text.strip():
                    if isinstance(msg.get("content"), list):
                        tool_calls = [p for p in msg["content"] if isinstance(p, dict) and p.get("type") == "tool_use"]
                        if tool_calls:
                            tool_names = [t.get("name", "?") for t in tool_calls]
                            content_text = f"[Called tools: {', '.join(tool_names)}]"
                    if not content_text.strip():
                        continue

                if role == "toolResult":
                    continue

                messages.append({
                    "role": role,
                    "content": content_text,
                    "timestamp": timestamp,
                })

    return session_info, messages, compactions


def format_transcript(session_key, session_info, messages, compactions, meta):
    lines = []

    session_date = ""
    if session_info.get("timestamp"):
        try:
            dt = datetime.fromisoformat(session_info["timestamp"].replace("Z", "+00:00"))
            session_date = dt.strftime("%Y-%m-%d %H:%M %Z")
        except (ValueError, AttributeError):
            session_date = session_info.get("timestamp", "Unknown")

    lines.append(f"# Conversation Archive: {session_key}")
    lines.append("")
    lines.append(f"- **Session ID:** {session_info.get('id', 'unknown')}")
    lines.append(f"- **Date:** {session_date}")
    lines.append(f"- **Channel:** {meta.get('lastChannel', meta.get('origin', 'unknown'))}")
    if meta.get("label"):
        lines.append(f"- **Label:** {meta['label']}")
    lines.append(f"- **Messages:** {len(messages)}")
    lines.append(f"- **Compactions:** {len(compactions)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    if compactions:
        lines.append("## Compaction Summaries")
        lines.append("")
        for i, comp in enumerate(compactions):
            lines.append(f"### Compaction {i+1} ({comp.get('timestamp', '?')})")
            lines.append("")
            lines.append(comp.get("summary", "(no summary)"))
            lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## Conversation")
    lines.append("")

    for msg in messages:
        role = msg["role"]
        content = msg["content"].strip()
        ts = msg.get("timestamp", "")

        if not content:
            continue

        time_str = ""
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                time_str = f" ({dt.strftime('%H:%M')})"
            except (ValueError, AttributeError):
                pass

        role_map = {
            "user": "👤 User",
            "assistant": "🤖 Assistant",
            "system": "⚙️ System",
        }
        label = role_map.get(role, role.title())
        lines.append(f"### {label}{time_str}")
        lines.append("")
        lines.append(content)
        lines.append("")

    return "\n".join(lines)


def get_session_date(session_info, meta):
    ts = session_info.get("timestamp") or ""
    if ts:
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

    updated = meta.get("updatedAt")
    if updated:
        try:
            return datetime.fromtimestamp(updated / 1000, tz=timezone.utc)
        except (ValueError, TypeError):
            pass

    return datetime.now(timezone.utc)


def archive_session(session_key, session_file, meta, state, force=False):
    filepath = Path(session_file)
    if not filepath.exists():
        return False

    file_hash = get_file_hash(filepath)
    prev_hash = state["archived"].get(session_key, {}).get("hash")

    if not force and file_hash == prev_hash:
        return False

    session_info, messages, compactions = parse_session_jsonl(filepath)

    user_msgs = [m for m in messages if m["role"] == "user"]
    if len(user_msgs) < MIN_USER_MESSAGES:
        state["archived"][session_key] = {
            "hash": file_hash,
            "skipped": True,
            "reason": f"Only {len(user_msgs)} user messages",
        }
        return False

    session_date = get_session_date(session_info, meta)
    date_dir = CONVERSATIONS_DIR / session_date.strftime("%Y/%m/%d")
    date_dir.mkdir(parents=True, exist_ok=True)

    safe_key = session_key.replace(":", "_").replace("/", "_")
    output_file = date_dir / f"{safe_key}.md"

    transcript = format_transcript(session_key, session_info, messages, compactions, meta)
    with open(output_file, "w") as f:
        f.write(transcript)

    state["archived"][session_key] = {
        "hash": file_hash,
        "file": str(output_file),
        "messages": len(messages),
        "userMessages": len(user_msgs),
        "archivedAt": datetime.now(timezone.utc).isoformat(),
    }

    return True


def show_stats(state):
    archived = state.get("archived", {})
    total = len(archived)
    skipped = sum(1 for v in archived.values() if v.get("skipped"))
    saved = total - skipped
    total_msgs = sum(v.get("messages", 0) for v in archived.values() if not v.get("skipped"))
    print(f"Archived sessions: {saved}")
    print(f"Skipped (trivial): {skipped}")
    print(f"Total messages: {total_msgs}")
    print(f"Last run: {state.get('lastRun', 'never')}")

    # Disk usage
    if CONVERSATIONS_DIR.exists():
        total_bytes = sum(f.stat().st_size for f in CONVERSATIONS_DIR.rglob("*.md"))
        print(f"Disk usage: {total_bytes / 1024:.1f} KB")


def main():
    force = "--force" in sys.argv
    stats_only = "--stats" in sys.argv

    state = load_state()

    if stats_only:
        show_stats(state)
        return 0

    archived_count = 0

    for agent_dir in AGENTS_DIR.glob("*/sessions"):
        meta_file = agent_dir / "sessions.json"
        if not meta_file.exists():
            continue

        with open(meta_file) as f:
            sessions_meta = json.load(f)

        known_files = set()

        for session_key, meta in sessions_meta.items():
            session_file = meta.get("sessionFile")
            if session_file:
                known_files.add(Path(session_file).name)
                if archive_session(session_key, session_file, meta, state, force):
                    archived_count += 1

        # Orphan session files
        for jsonl_file in agent_dir.glob("*.jsonl"):
            if jsonl_file.name in known_files or jsonl_file.name.endswith(".tmp"):
                continue
            orphan_key = f"orphan:{jsonl_file.stem}"
            if archive_session(orphan_key, str(jsonl_file), {}, state, force):
                archived_count += 1

    save_state(state)

    if archived_count > 0:
        print(f"Archived {archived_count} new/updated conversations")

    return 0


if __name__ == "__main__":
    sys.exit(main())
