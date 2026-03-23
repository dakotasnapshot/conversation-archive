# conversation-archive

An OpenClaw skill that preserves full conversation transcripts before compaction can destroy them.

## The Problem

When OpenClaw compacts a session to stay within token limits, the full conversation is replaced with a lossy summary. Exact wording, troubleshooting steps, tool outputs, and nuanced decisions are lost forever.

## The Solution

Archive complete session transcripts as searchable markdown files organized by date:

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
- **Incremental** — only new/changed sessions are re-archived
- **Lightweight** — ~200KB/day for active usage

## One-Shot Setup Prompt

Copy and paste this into your OpenClaw agent chat to set everything up automatically:

---

```
Set up the conversation-archive skill for me. Here's what to do:

1. Clone the repo:
   git clone https://github.com/dakotasnapshot/conversation-archive.git into my OpenClaw workspace skills directory (usually ~/.openclaw/workspace/skills/conversation-archive)

2. Run the archiver once to do the initial archive of all existing sessions:
   python3 ~/.openclaw/workspace/skills/conversation-archive/scripts/archive-transcripts.py

3. Create an OpenClaw cron job to run the archiver hourly:
   - Name: "Conversation Archive — Hourly"
   - Schedule: cron expression "0 * * * *" in my local timezone
   - Session target: isolated
   - Payload: agentTurn that runs: python3 ~/.openclaw/workspace/skills/conversation-archive/scripts/archive-transcripts.py
   - Use cheapest available model (gpt-4o-mini or similar)
   - Delivery: none (silent)

4. Patch my OpenClaw config to archive before compaction:
   gateway config.patch with:
   {
     "agents": {
       "defaults": {
         "compaction": {
           "memoryFlush": { "enabled": true },
           "customInstructions": "Before summarizing, run: python3 <WORKSPACE>/skills/conversation-archive/scripts/archive-transcripts.py — This preserves the full transcript before compaction. Include all exact identifiers, paths, URLs, and technical specifics in the summary."
         }
       }
     }
   }
   Replace <WORKSPACE> with my actual workspace path.

5. Verify it worked by running: python3 ~/.openclaw/workspace/skills/conversation-archive/scripts/archive-transcripts.py --stats

Tell me what you set up and how many conversations were archived.
```

---

## Manual Setup

If you prefer to set it up yourself:

### 1. Install

```bash
cd ~/.openclaw/workspace/skills
git clone https://github.com/dakotasnapshot/conversation-archive.git
```

### 2. Run the archiver

```bash
python3 skills/conversation-archive/scripts/archive-transcripts.py
```

### 3. Check stats

```bash
python3 skills/conversation-archive/scripts/archive-transcripts.py --stats
```

### 4. Configure pre-compaction hook

Add to your `openclaw.json` under `agents.defaults.compaction`:

```json
{
  "memoryFlush": { "enabled": true },
  "customInstructions": "Before summarizing, run: python3 <WORKSPACE>/skills/conversation-archive/scripts/archive-transcripts.py"
}
```

## Configuration

Environment variables (all optional):

| Variable | Default | Description |
|----------|---------|-------------|
| `ARCHIVE_WORKSPACE` | `~/.openclaw/workspace` | Workspace root |
| `ARCHIVE_AGENTS_DIR` | `~/.openclaw/agents` | Agent sessions directory |
| `ARCHIVE_MIN_MESSAGES` | `3` | Min user messages to archive a session |

## RAG Integration

Archives land in `conversations/` inside your workspace. If you run a workspace RAG/vector search server, the files will be picked up on the next reindex. To trigger manually:

```bash
curl -s -X POST http://127.0.0.1:9877/index \
  -H 'Content-Type: application/json' \
  -d '{"paths": ["~/.openclaw/workspace/conversations"]}'
```

## How It Works

1. Reads session JSONL files from `~/.openclaw/agents/*/sessions/*.jsonl`
2. Parses user/assistant/system messages and tool calls
3. Converts to clean markdown with metadata headers (date, channel, message count)
4. Saves to `conversations/YYYY/MM/DD/session-key.md`
5. Tracks state in `.archive-state.json` — only re-archives changed sessions
6. Skips trivial sessions (<3 user messages by default)

## License

MIT

## Author

Bucky Cole ([@dakotasnapshot](https://github.com/dakotasnapshot))

Built by an AI agent who got tired of forgetting conversations. 🦫
