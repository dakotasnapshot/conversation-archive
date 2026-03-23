---
name: conversation-archive
description: Archive full OpenClaw conversation transcripts before compaction destroys them. Saves session JSONL files as searchable markdown to conversations/YYYY/MM/DD/. Use when setting up conversation archival, configuring pre-compaction hooks, or troubleshooting lost conversation context. Pairs with RAG/vector search for retrieval.
---

# Conversation Archive

Preserves full conversation transcripts immune to compaction. Sessions are archived as markdown files in `conversations/YYYY/MM/DD/` and can be indexed by any vector search system.

## Setup

### 1. Run the archiver

```bash
python3 {{SKILL_DIR}}/scripts/archive-transcripts.py
```

First run archives all existing sessions. Subsequent runs only archive new/changed sessions (change detection via file hash).

### 2. Configure pre-compaction archival

Patch OpenClaw config to run the archiver before compaction:

```
gateway config.patch with:
{
  "agents": {
    "defaults": {
      "compaction": {
        "memoryFlush": { "enabled": true },
        "customInstructions": "Before summarizing, run: python3 <WORKSPACE>/skills/conversation-archive/scripts/archive-transcripts.py — This preserves the full transcript before compaction."
      }
    }
  }
}
```

Replace `<WORKSPACE>` with the actual workspace path.

### 3. Schedule hourly archival (recommended)

Create an OpenClaw cron job:
- Schedule: `0 * * * *` (hourly)
- Payload: `python3 <WORKSPACE>/skills/conversation-archive/scripts/archive-transcripts.py`
- Model: cheapest available (gpt-4o-mini or similar)
- Delivery: none (silent)

### 4. RAG integration (optional)

The `conversations/` directory is inside the workspace. If you run a workspace RAG server, trigger a reindex after archiving to make transcripts searchable:

```bash
curl -s -X POST http://127.0.0.1:9877/index \
  -H 'Content-Type: application/json' \
  -d '{"paths": ["<WORKSPACE>/conversations"]}'
```

## How it works

1. Reads session JSONL files from `~/.openclaw/agents/*/sessions/*.jsonl`
2. Parses messages (user, assistant, system, tool calls)
3. Converts to clean markdown with metadata header
4. Saves to `conversations/YYYY/MM/DD/session-key.md`
5. Tracks archived sessions in `conversations/.archive-state.json` (idempotent)
6. Skips sessions with <3 user messages (trivial/empty)

## Output format

```markdown
# Conversation Archive: agent:main:main

- **Session ID:** af7e41c0-...
- **Date:** 2026-03-23 09:00 UTC
- **Channel:** matrix
- **Messages:** 142

---

## Conversation

### 👤 User (09:04)
Can you fix the billing endpoint?

### 🤖 Assistant (09:04)
[Called tools: exec, read]
Let me check the server code...
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ARCHIVE_WORKSPACE` | `~/.openclaw/workspace` | Workspace root |
| `ARCHIVE_AGENTS_DIR` | `~/.openclaw/agents` | Agent sessions directory |
| `ARCHIVE_MIN_MESSAGES` | `3` | Minimum user messages to archive |

## Troubleshooting

- **No sessions found:** Check that `~/.openclaw/agents/*/sessions/*.jsonl` files exist
- **Empty archives:** Sessions with <3 user messages are skipped by default
- **Disk usage:** ~200KB/day for active usage. Archives compress well if needed.
