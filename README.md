# conversation-archive

An OpenClaw skill that preserves full conversation transcripts before compaction can destroy them.

## The Problem

When OpenClaw compacts a session to stay within token limits, the full conversation is replaced with a lossy summary. Exact wording, troubleshooting steps, tool outputs, and nuanced decisions are lost forever.

## The Solution

This skill archives complete session transcripts as searchable markdown files organized by date:

```
conversations/
├── 2026/
│   └── 03/
│       └── 23/
│           ├── agent_main_main.md
│           └── agent_main_cron_abc123.md
```

Archives are:
- **Compaction-immune** — saved before compaction runs
- **Searchable** — plain markdown, works with any RAG/vector search
- **Incremental** — only new/changed sessions are re-archived (file hash tracking)
- **Lightweight** — ~200KB/day for active usage

## Installation

```bash
clawhub install conversation-archive
```

Or manually copy to your OpenClaw skills directory.

## Quick Start

1. Run the archiver: `python3 skills/conversation-archive/scripts/archive-transcripts.py`
2. Configure pre-compaction hook (see SKILL.md)
3. Optionally set up hourly cron

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ARCHIVE_WORKSPACE` | `~/.openclaw/workspace` | Workspace root |
| `ARCHIVE_AGENTS_DIR` | `~/.openclaw/agents` | Agent sessions directory |
| `ARCHIVE_MIN_MESSAGES` | `3` | Min user messages to archive |

## License

MIT

## Author

Bucky Cole ([@dakotasnapshot](https://github.com/dakotasnapshot))
