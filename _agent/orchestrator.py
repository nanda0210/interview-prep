"""
Common agent (orchestrator). Runs daily:
  1. git pull (get others' changes first)
  2. discover every .md file in the repo
  3. run one sub-agent per file (append fresh dated Q&A, never delete)
  4. collect each sub-agent's report
  5. write a timestamped changelog highlighting changed files + newly added content
  6. git commit + push (unless --no-push)

Usage:
  python3 orchestrator.py            # full run (append + changelog + commit/push)
  python3 orchestrator.py --no-push  # do everything but don't push
  python3 orchestrator.py --dry-run  # no API calls, no writes — just show what it would do
"""
import os, sys, subprocess, datetime, pathlib, json

AGENT_DIR = pathlib.Path(__file__).resolve().parent
REPO = AGENT_DIR.parent
CHANGELOG = REPO / "AGENT-CHANGELOG.md"          # committed, human-readable
RUNLOG = AGENT_DIR / "logs" / "agent.log"        # local, verbose


def load_env():
    env = AGENT_DIR / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def git(*args, check=True):
    r = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


def runlog(msg):
    RUNLOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with RUNLOG.open("a") as f:
        f.write(f"[{ts}] {msg}\n")
    print(msg)


def discover_files():
    return sorted(p for p in REPO.glob("*.md")
                  if p.name not in ("AGENT-CHANGELOG.md",) and not p.name.startswith("_"))


def write_changelog(reports, pushed):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z").strip()
    changed = [r for r in reports if r["added"] and not r["error"]]
    errors = [r for r in reports if r["error"]]
    lines = [f"\n## Run · {ts}\n"]
    if changed:
        lines.append(f"**{len(changed)} file(s) updated** by sub-agents:\n")
        for r in changed:
            lines.append(f"### 📄 {r['file']}  ·  +{r['added']} Q&A  ({r['chars_added']} chars)")
            if r.get("added_questions"):
                for q in r["added_questions"]:
                    lines.append(f"- {q}")
            elif r.get("preview"):
                lines.append("```md")
                lines.append(r["preview"].strip()[:400])
                lines.append("```")
            lines.append("")
    else:
        lines.append("_No content appended this run._\n")
    if errors:
        lines.append("**Sub-agent errors:**")
        for r in errors:
            lines.append(f"- ⚠️ {r['file']}: {r['error']}")
        lines.append("")
    lines.append(f"_Committed & pushed: {'yes' if pushed else 'no'}_")

    header = ""
    if not CHANGELOG.exists():
        header = "# Agent Changelog\n\nDaily log of content appended by the interview-prep monitoring agent.\n"
    with CHANGELOG.open("a", encoding="utf-8") as f:
        if header:
            f.write(header)
        f.write("\n".join(lines) + "\n")


def main():
    load_env()
    no_push = "--no-push" in sys.argv
    dry = "--dry-run" in sys.argv
    runlog(f"=== orchestrator start (dry={dry}, no_push={no_push}) ===")

    # 1. pull latest
    try:
        git("pull", "--rebase", "--autostash", check=False)
        runlog("pulled origin/main")
    except Exception as e:
        runlog(f"pull warning: {e}")

    files = discover_files()
    runlog(f"discovered {len(files)} file(s): {', '.join(p.name for p in files)}")

    reports = []
    if dry:
        for p in files:
            reports.append({"file": p.name, "added": 0, "error": "dry-run (no changes)",
                            "chars_added": 0, "preview": "", "subject": p.stem})
        runlog("dry-run: skipping generation, writes, and push")
        return

    # 2-4. one sub-agent per file, collect reports
    from subagent import run_subagent
    for p in files:
        runlog(f"→ sub-agent: {p.name}")
        rep = run_subagent(p)
        if rep["error"]:
            runlog(f"   ⚠️ {rep['error']}")
        else:
            runlog(f"   ✓ appended {rep['added']} Q&A ({rep['chars_added']} chars)")
        reports.append(rep)

    # 5. changelog
    any_change = any(r["added"] and not r["error"] for r in reports)
    pushed = False

    # 6. commit + push
    if any_change and not no_push:
        try:
            git("add", "-A")
            write_changelog(reports, pushed=True)   # write before commit so it's included
            git("add", "-A")
            msg = f"Agent: daily prep update {datetime.date.today().isoformat()}"
            git("commit", "-m", msg)
            git("push", "origin", "HEAD")
            pushed = True
            runlog("committed & pushed ✓")
        except Exception as e:
            runlog(f"git commit/push failed: {e}")
            write_changelog(reports, pushed=False)
    else:
        write_changelog(reports, pushed=False)
        runlog("changelog written; push skipped" if no_push else "no changes to push")

    runlog(f"=== orchestrator done: {sum(1 for r in reports if r['added'] and not r['error'])} file(s) updated ===")


if __name__ == "__main__":
    main()
