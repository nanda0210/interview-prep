# Interview Agent (skill)

Turns a Jira epic + its child tickets + linked PRs into an interview-prep
document for an SRE / Platform Engineer role.

## TL;DR

```bash
# 1. Get tickets out of Jira (PAT in env)
export JIRA_PAT=...   # Bearer token (Jira Data Center / on-prem PAT pattern)
bash scripts/fetch_tickets.sh FSRE-20 > artifacts/fsre-20/tickets.json

# 2. Generate the doc
python scripts/generate_interview_doc.py \
  --tickets artifacts/fsre-20/tickets.json \
  --clusters examples/cluster-compare-fsre-20.json \
  --out INTERVIEW-PREP-FSRE-20.md
```

See `SKILL.md` for the full contract.
