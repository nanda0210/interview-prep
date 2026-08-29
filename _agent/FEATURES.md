# Interview-Prep Agent — Features & Skillset

An autonomous daily agent that keeps a set of interview-preparation documents
growing with fresh, non-duplicated senior-level Q&A. Runs unattended in the
cloud and commits its output back to this repository.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Daily autonomous runs** | Executes every day at **15:00 UTC (8 AM PDT)** with no human involvement. |
| **Cloud-hosted** | Runs on **GitHub Actions** — works even when your Mac is asleep or off. No local scheduler, no macOS permission issues. |
| **Append-only, never destructive** | Adds a new dated section per run; existing content is never edited or deleted. |
| **De-duplication** | Tracks previously asked questions (in-file scan + `state.json`) and instructs the model not to repeat or paraphrase them. |
| **Multi-file, one sub-agent each** | Discovers every root-level `*.md` topic file and runs an independent sub-agent per file. |
| **Human-readable changelog** | Writes `AGENT-CHANGELOG.md` each run: which files changed, how many Q&A added, and the new questions. |
| **Self-committing** | Pulls latest, generates, commits, and pushes back to `main` automatically (as `github-actions[bot]`). |
| **On-demand runs** | Trigger anytime with `gh workflow run daily-prep.yml` or the repo's Actions tab (`workflow_dispatch`). |
| **Configurable** | Model and items-per-run set via `PREP_MODEL` / `PREP_ITEMS` (env vars / workflow). |
| **Prompt caching** | The system prompt is marked `cache_control: ephemeral` to cut token cost on repeated runs. |
| **Safe secret handling** | API key lives only in the gitignored `_agent/.env` locally and as an encrypted GitHub Actions secret — never committed. |

---

## 🧠 Skillset / Capabilities

- **Content generation** — produces realistic senior-level interview questions with concise model answers, mixing systems, troubleshooting, design, trade-offs, and behavioral angles.
- **State awareness** — remembers up to ~200 prior questions per file to keep new material fresh.
- **Subject inference** — derives each document's topic from its `# H1` heading (emoji-stripped) or filename.
- **Git orchestration** — rebase-pull → generate → commit → push, with graceful handling if push fails.
- **Failure resilience** — per-file errors are captured and reported in the changelog without aborting the whole run.

---

## 🏗️ Architecture

```
GitHub Actions (cron: 0 15 * * *)
        │
        ▼
_agent/orchestrator.py        ← pulls, discovers *.md, writes changelog, commits & pushes
        │  (one per file)
        ▼
_agent/subagent.py            ← calls Claude API, appends dated Q&A, updates state.json
        │
        ▼
<Topic>.md  +  AGENT-CHANGELOG.md   ← committed back to main
```

**Components**
- `_agent/orchestrator.py` — the "common agent": discovery, changelog, git.
- `_agent/subagent.py` — one instance per file: generation, append, de-dup state.
- `_agent/run.sh` — local entry point (`--no-push` / `--dry-run` supported).
- `.github/workflows/daily-prep.yml` — the cloud schedule.
- `_agent/.env` — local secrets/config (gitignored). `.env.example` is the template.
- `_agent/state.json` — de-dup memory (gitignored).

---

## ⚙️ Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | — | Claude API key (required). |
| `PREP_MODEL` | `claude-sonnet-4-6` | Model used for generation. |
| `PREP_ITEMS` | `4` | New Q&A items added per file per run. |

---

## 🕹️ Operating it

```bash
# See recent runs
gh run list --workflow=daily-prep.yml

# Run on demand (cloud)
gh workflow run daily-prep.yml

# Local run without pushing
bash _agent/run.sh --no-push

# Get the latest generated content onto your machine
git pull
```

> **Note on timezone:** GitHub cron is UTC and does not observe DST, so the
> job fires at 8 AM PDT in summer and 7 AM PST in winter. Change the cron to
> `0 16 * * *` to keep it at 8 AM year-round in winter.
