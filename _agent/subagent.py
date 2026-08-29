"""
Sub-agent: one instance per file. Generates fresh interview-prep Q&A relevant
to that file's subject via the Claude API and APPENDS it under a dated section.
Never edits or deletes existing content. Reports a summary back to the orchestrator.
"""
import os, re, json, datetime, hashlib, pathlib

MODEL = os.environ.get("PREP_MODEL", "claude-sonnet-4-6")
ITEMS_PER_RUN = int(os.environ.get("PREP_ITEMS", "4"))
STATE_PATH = pathlib.Path(__file__).resolve().parent / "state.json"

SYSTEM = (
    "You are a senior technical interviewer and prep author. You extend an existing "
    "interview-preparation Markdown document with NEW, high-quality question-and-answer "
    "items on the same subject. Rules:\n"
    "- Do NOT repeat any question already covered (a list of prior questions is provided).\n"
    "- Each item: a realistic senior-level interview question, then a concise model answer "
    "(4-8 sentences or tight bullets) covering the key points an interviewer wants to hear.\n"
    "- Mix difficulty and angles: systems, troubleshooting, design, trade-offs, and behavioral.\n"
    "- Output ONLY Markdown for the new items. Start each with '### Q: '. No preamble, no closing remarks."
)


def _load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            return {}
    return {}


def _save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2))


def _subject(path, text):
    m = re.search(r"^#\s+(.+)$", text, re.M)
    if m:
        return re.sub(r"[^\w\s/&+.-]", "", m.group(1)).strip()  # drop emoji
    return path.stem.replace("-", " ")


def _prior_questions(text, state_key, state):
    # questions already in the file + everything the agent has tracked before
    infile = re.findall(r"^#{2,4}\s*(?:Q:)?\s*(.+)$", text, re.M)
    tracked = state.get(state_key, {}).get("questions", [])
    seen = [q.strip()[:120] for q in infile if "?" in q] + tracked
    # dedup, keep most recent ~60
    out, s = [], set()
    for q in reversed(seen):
        k = q.lower()
        if k not in s:
            s.add(k); out.append(q)
    return out[:60]


def run_subagent(path: pathlib.Path):
    """Returns a report dict for the orchestrator."""
    report = {"file": path.name, "subject": None, "added": 0, "preview": "", "error": None, "chars_added": 0}
    try:
        import anthropic
    except Exception as e:
        report["error"] = f"anthropic SDK missing: {e}"; return report
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        report["error"] = "ANTHROPIC_API_KEY not set (add to _agent/.env)"; return report

    text = path.read_text(encoding="utf-8", errors="ignore")
    subject = _subject(path, text)
    report["subject"] = subject
    state = _load_state()
    state_key = path.name
    prior = _prior_questions(text, state_key, state)

    prompt = (
        f"Subject of this document: **{subject}**.\n\n"
        f"Add {ITEMS_PER_RUN} NEW interview Q&A items on this subject.\n\n"
        f"Questions already covered (do NOT repeat or paraphrase these):\n"
        + ("\n".join(f"- {q}" for q in prior) if prior else "(none yet)")
    )

    client = anthropic.Anthropic(api_key=key)
    resp = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    )
    new_md = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    if not new_md:
        report["error"] = "model returned no content"; return report

    today = datetime.date.today().isoformat()
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    section = f"\n\n---\n\n## 🗓️ Added {today} (auto-generated · {ITEMS_PER_RUN} new Q&A)\n\n<!-- agent:{ts} -->\n\n{new_md}\n"
    with path.open("a", encoding="utf-8") as f:      # APPEND-ONLY — never truncates
        f.write(section)

    added_qs = re.findall(r"^###\s*Q:\s*(.+)$", new_md, re.M)
    st = state.setdefault(state_key, {"questions": []})
    st["questions"] = (st["questions"] + [q.strip()[:120] for q in added_qs])[-200:]
    st["last_run"] = ts
    _save_state(state)

    report["added"] = len(added_qs) or ITEMS_PER_RUN
    report["chars_added"] = len(section)
    report["preview"] = new_md[:500]
    report["added_questions"] = [q.strip() for q in added_qs]
    return report
