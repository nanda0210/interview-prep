# Interview-Prep Monitoring Agent

A daily agent that grows this repo's prep files with fresh, AI-generated interview
Q&A — **append-only** (your original content is never edited or deleted).

## How it works
- **Common agent** (`orchestrator.py`) runs once/day: pulls latest → discovers every
  `*.md` file → launches one **sub-agent** per file → collects their reports → writes a
  timestamped **changelog** → commits & pushes.
- **Sub-agent** (`subagent.py`, one per file): reads the file's subject, calls the Claude
  API for N new Q&A that don't repeat what's already covered, and **appends** them under a
  dated section (`## 🗓️ Added YYYY-MM-DD`). Reports back to the common agent.
- **Changelog** (`../AGENT-CHANGELOG.md`, committed): each run logs which files changed and
  the exact questions added, with a timestamp.
- Dedup state in `state.json` (gitignored) prevents repeat questions over time.

## One-time setup
1. **API key** — copy the template and add your Anthropic key:
   ```bash
   cp _agent/.env.example _agent/.env      # then edit _agent/.env
   ```
   `.env` is gitignored — the key never gets committed.
2. **Test a real run** (generates + appends, but does NOT push):
   ```bash
   bash _agent/run.sh --no-push
   ```
   Check the new dated section at the end of the file and `AGENT-CHANGELOG.md`.
3. **Schedule it daily** (macOS launchd, runs 08:00):
   ```bash
   cp _agent/com.nanda.interviewprep.agent.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.nanda.interviewprep.agent.plist
   ```
   To stop: `launchctl unload ~/Library/LaunchAgents/com.nanda.interviewprep.agent.plist`

## Run modes
| Command | Effect |
|---|---|
| `bash _agent/run.sh` | full daily run: append → changelog → commit → push |
| `bash _agent/run.sh --no-push` | append + changelog locally, no push (review first) |
| `bash _agent/run.sh --dry-run` | no API calls, no writes — just show what it'd do |

## Config (in `_agent/.env`)
- `ANTHROPIC_API_KEY` — required
- `PREP_MODEL` — default `claude-sonnet-4-6` (cost-effective; use an Opus id for max quality)
- `PREP_ITEMS` — new Q&A per file per day (default `4`)

## Safety
- **Append-only:** files are opened in append mode; original bytes are never rewritten.
- **Secrets:** API key in gitignored `.env`; never committed.
- Add more `.md` files to the repo and each automatically gets its own sub-agent — no code changes.
