#!/usr/bin/env python3
"""
enrich_prs.py
=============

Reads a tickets.json (from fetch_tickets.sh) and for each issue:

  1. Scans every text field (description, comments) for GitHub PR URLs of the
     form  https://github.com/<owner>/<repo>/pull/<number>.
  2. Optionally also reads explicit `pr_urls: [...]` per issue if present.
  3. Calls `gh api` per unique (owner, repo, number) to fetch PR metadata and
     `gh pr view --json files` for the changed-file list.
  4. Auto-tags each PR with `tech_tags` based on filename heuristics
     (terraform, eks, iam, helm, argocd, etc.) using the controlled vocabulary
     from tech_taxonomy.json.
  5. Merges results back into the issue's `prs[]` array (de-duplicated).
  6. Writes the enriched tickets.json (in place by default; --out to redirect).

Requirements:
  - `gh` CLI authenticated (gh auth status) with repo: read scope on the
    relevant orgs.
  - Python 3.10+.

Usage:
  python enrich_prs.py --tickets artifacts/fsre-20/tickets.json
  python enrich_prs.py --tickets in.json --out out.json --concurrency 8 --dry-run

Notes:
  - The script is idempotent: re-running on the same file is safe.
  - PRs that 404 (private fork, deleted, no access) are recorded with a
    "summary" of "<UNREACHABLE>" so you can see what failed.
  - Never invents data: if the PR body is empty, summary is left as
    the PR title only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

PR_URL_RE = re.compile(
    r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/(\d+)"
)

SCRIPT_DIR = Path(__file__).resolve().parent
TAXONOMY_PATH = SCRIPT_DIR / "tech_taxonomy.json"


# ---------------------------------------------------------------------------
# Tech-tag heuristics (filename -> tags)
# ---------------------------------------------------------------------------

# Order matters slightly; first matching wins for "primary" but we keep all hits.
_FILENAME_RULES: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"\.tf$|\.tf\.json$|terragrunt\.hcl$"), ["terraform", "terragrunt"]),
    (re.compile(r"(^|/)vpc/"), ["vpc", "cidr", "subnet"]),
    (re.compile(r"(^|/)subnets?/"), ["subnet"]),
    (re.compile(r"(^|/)nat[-_]?gateway"), ["nat-gateway"]),
    (re.compile(r"(^|/)internet[-_]?gateway"), ["internet-gateway"]),
    (re.compile(r"(^|/)transit[-_]?gateway"), ["transit-gateway"]),
    (re.compile(r"(^|/)vpn"), ["vpn"]),
    (re.compile(r"(^|/)security[-_]?group|sg[-_]?rules?"), ["security-group", "ingress-rule", "egress-rule"]),
    (re.compile(r"(^|/)nacl"), ["nacl"]),
    (re.compile(r"(^|/)route[-_]?table"), ["route-table"]),
    (re.compile(r"(^|/)alb|application[-_]?load[-_]?balancer"), ["alb", "load-balancer"]),
    (re.compile(r"(^|/)nlb|network[-_]?load[-_]?balancer"), ["nlb", "load-balancer"]),
    (re.compile(r"(^|/)target[-_]?group"), ["target-group"]),
    (re.compile(r"(^|/)listener"), ["listener-rule"]),
    (re.compile(r"(^|/)eks/|eks[-_]?cluster"), ["eks"]),
    (re.compile(r"karpenter"), ["karpenter"]),
    (re.compile(r"managed[-_]?node[-_]?group|mng"), ["managed-node-group"]),
    (re.compile(r"fargate"), ["fargate-profile"]),
    (re.compile(r"(^|/)iam/|iam[-_]?role"), ["iam", "iam-role"]),
    (re.compile(r"irsa|service[-_]?account[-_]?role"), ["irsa", "iam"]),
    (re.compile(r"pod[-_]?identity"), ["pod-identity", "iam"]),
    (re.compile(r"trust[-_]?policy"), ["trust-policy"]),
    (re.compile(r"argocd|argo[-_]?cd|application[-_]?set"), ["argocd"]),
    (re.compile(r"app[-_]?of[-_]?apps"), ["app-of-apps", "argocd"]),
    (re.compile(r"helm|charts?/|values.*\.ya?ml$"), ["helm"]),
    (re.compile(r"kustomization\.ya?ml$|overlays/|bases/"), ["kustomize"]),
    (re.compile(r"\.github/workflows/.*\.ya?ml$"), ["github-actions", "ci-cd"]),
    (re.compile(r"Jenkinsfile|cloudbees|\.cloudbees/"), ["cloudbees", "ci-cd"]),
    (re.compile(r"external[-_]?secrets?"), ["external-secrets"]),
    (re.compile(r"secrets?[-_]?manager"), ["secrets-manager"]),
    (re.compile(r"ssm|parameter[-_]?store"), ["ssm-parameter-store"]),
    (re.compile(r"vault"), ["vault"]),
    (re.compile(r"coredns"), ["coredns", "configmap-coredns"]),
    (re.compile(r"kube[-_]?proxy"), ["kube-proxy", "configmap-kube-proxy"]),
    (re.compile(r"vpc[-_]?cni|amazon[-_]?vpc[-_]?cni|aws[-_]?node"), ["vpc-cni", "configmap-amazon-vpc-cni"]),
    (re.compile(r"aws[-_]?auth"), ["aws-auth-configmap", "configmap-aws-auth"]),
    (re.compile(r"efs"), ["efs"]),
    (re.compile(r"ebs"), ["ebs"]),
    (re.compile(r"csi[-_]?driver"), ["csi-driver"]),
    (re.compile(r"storage[-_]?class"), ["storage-class"]),
    (re.compile(r"acm|certificate-manager|cert[-_]?manager"), ["cert-manager", "tls"]),
    (re.compile(r"route53|external[-_]?dns"), ["route53", "dns"]),
    (re.compile(r"prometheus|grafana|alertmanager"), ["monitoring"]),
    (re.compile(r"fluent[-_]?bit|fluentd|cloudwatch[-_]?logs"), ["logging"]),
    (re.compile(r"otel|opentelemetry|signalfx"), ["tracing"]),
]


def tags_for_files(files: list[str]) -> list[str]:
    """Return a deduped, ordered list of tech tags for a set of file paths."""
    seen: dict[str, None] = {}
    for f in files:
        for rule, tags in _FILENAME_RULES:
            if rule.search(f):
                for t in tags:
                    seen.setdefault(t, None)
    return list(seen.keys())


# ---------------------------------------------------------------------------
# gh shell-out helpers
# ---------------------------------------------------------------------------

async def gh_api(path: str) -> dict | None:
    """Call `gh api <path>`. Returns dict on success, None on 4xx/5xx."""
    proc = await asyncio.create_subprocess_exec(
        "gh", "api", path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        msg = err.decode(errors="replace").strip()
        print(f"  gh api {path} -> exit {proc.returncode}: {msg[:200]}", file=sys.stderr)
        return None
    try:
        return json.loads(out.decode())
    except json.JSONDecodeError as e:
        print(f"  gh api {path} -> JSON decode error: {e}", file=sys.stderr)
        return None


async def fetch_pr(owner: str, repo: str, number: int) -> dict:
    """Fetch PR metadata + files; return a dict in our schema (or marked unreachable)."""
    base = f"repos/{owner}/{repo}/pulls/{number}"
    pr = await gh_api(base)

    if pr is None:
        return {
            "repo": f"{owner}/{repo}",
            "number": number,
            "title": "<UNREACHABLE>",
            "url": f"https://github.com/{owner}/{repo}/pull/{number}",
            "state": "unknown",
            "merged_at": None,
            "additions": 0,
            "deletions": 0,
            "files_changed": [],
            "summary": "<UNREACHABLE>",
            "tech_tags": [],
        }

    files_resp = await gh_api(f"{base}/files?per_page=100") or []
    files = [f.get("filename", "") for f in files_resp if isinstance(f, dict)]

    # Collapse PR.body to a 1-3 sentence summary (no LLM here; just heuristic).
    body = (pr.get("body") or "").strip()
    summary = pr.get("title", "")
    if body:
        # First non-empty paragraph, capped.
        first_para = next((p.strip() for p in body.split("\n\n") if p.strip()), "")
        if first_para:
            summary = (first_para[:400] + ("…" if len(first_para) > 400 else ""))

    state = "merged" if pr.get("merged_at") else pr.get("state", "open")

    return {
        "repo": f"{owner}/{repo}",
        "number": number,
        "title": pr.get("title", ""),
        "url": pr.get("html_url", f"https://github.com/{owner}/{repo}/pull/{number}"),
        "state": state,
        "merged_at": pr.get("merged_at"),
        "additions": pr.get("additions", 0),
        "deletions": pr.get("deletions", 0),
        "files_changed": files,
        "summary": summary,
        "tech_tags": tags_for_files(files),
    }


# ---------------------------------------------------------------------------
# PR URL discovery
# ---------------------------------------------------------------------------

def _walk_strings(obj: Any):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_strings(v)


def discover_pr_refs(issue: dict) -> set[tuple[str, str, int]]:
    """Find every (owner, repo, number) referenced anywhere in the issue."""
    found: set[tuple[str, str, int]] = set()

    # Explicit pr_urls field if present
    for url in issue.get("pr_urls", []) or []:
        m = PR_URL_RE.search(str(url))
        if m:
            found.add((m.group(1), m.group(2), int(m.group(3))))

    # Existing PRs already enriched (we'll skip re-fetching these)
    for pr in issue.get("prs", []) or []:
        repo = pr.get("repo", "")
        if "/" in repo and isinstance(pr.get("number"), int):
            owner, name = repo.split("/", 1)
            found.add((owner, name, pr["number"]))

    # Free-text scan
    for s in _walk_strings({k: v for k, v in issue.items() if k not in ("prs",)}):
        for m in PR_URL_RE.finditer(s):
            found.add((m.group(1), m.group(2), int(m.group(3))))

    return found


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def enrich(tickets_path: Path, out_path: Path, concurrency: int, dry_run: bool) -> int:
    epic = json.loads(tickets_path.read_text(encoding="utf-8"))
    issues = epic.get("issues", []) or []
    if not issues:
        print("No issues in input.", file=sys.stderr)
        return 1

    # Build full deduped fetch set across all issues
    issue_refs: list[tuple[dict, set[tuple[str, str, int]]]] = []
    all_refs: set[tuple[str, str, int]] = set()
    for issue in issues:
        refs = discover_pr_refs(issue)
        issue_refs.append((issue, refs))
        all_refs |= refs

    print(f"Discovered {len(all_refs)} unique PR references across {len(issues)} tickets.")
    if dry_run:
        for owner, repo, num in sorted(all_refs):
            print(f"  - {owner}/{repo}#{num}")
        return 0

    sem = asyncio.Semaphore(concurrency)
    cache: dict[tuple[str, str, int], dict] = {}

    async def one(ref: tuple[str, str, int]) -> None:
        async with sem:
            owner, repo, num = ref
            print(f"  fetching {owner}/{repo}#{num}")
            cache[ref] = await fetch_pr(owner, repo, num)

    await asyncio.gather(*(one(r) for r in all_refs))

    # Re-attach to each issue (preserving any pre-existing manual fields)
    enriched = 0
    for issue, refs in issue_refs:
        existing_by_key = {
            (pr.get("repo", ""), pr.get("number", -1)): pr
            for pr in issue.get("prs", []) or []
        }
        merged: list[dict] = []
        for ref in sorted(refs):
            owner, repo, num = ref
            key = (f"{owner}/{repo}", num)
            fetched = cache.get(ref, {})
            if key in existing_by_key:
                # Manual fields win for summary/tech_tags if non-empty; everything else = fetched
                base = dict(fetched)
                for fld in ("summary", "tech_tags"):
                    val = existing_by_key[key].get(fld)
                    if val:
                        base[fld] = val
                merged.append(base)
            else:
                merged.append(fetched)
        if merged:
            issue["prs"] = merged
            enriched += 1

    out_path.write_text(json.dumps(epic, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK: enriched {enriched}/{len(issues)} tickets; wrote {out_path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tickets", required=True, type=Path,
                    help="Input tickets.json (from fetch_tickets.sh).")
    ap.add_argument("--out", required=False, type=Path, default=None,
                    help="Output path (default: overwrite input in place).")
    ap.add_argument("--concurrency", type=int, default=6,
                    help="Max parallel `gh api` calls (default: 6).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Discover PR refs only; do not call GitHub.")
    args = ap.parse_args()

    if not args.tickets.exists():
        print(f"ERROR: {args.tickets} not found", file=sys.stderr)
        return 2

    out = args.out or args.tickets
    return asyncio.run(enrich(args.tickets, out, args.concurrency, args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
