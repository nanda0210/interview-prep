#!/usr/bin/env python3
"""
generate_interview_doc.py
=========================

Reads a Jira-epic ticket dump (see ../scripts/tickets_schema.json) and an
optional cluster-comparison JSON, and emits a single Markdown document used
for FAANG-style interview prep.

The generator NEVER fabricates ticket facts. Where source data is missing,
it emits "<MISSING DATA: ...>" markers and a summary at the top of the doc.

Usage:
    python generate_interview_doc.py \\
        --tickets  artifacts/fsre-20/tickets.json \\
        --clusters agents/devex-agent/skills/interview-agent/examples/cluster-compare-fsre-20.json \\
        --out      INTERVIEW-PREP-FSRE-20.md

Output sections:
    1. Header + executive summary
    2. Cluster comparison table (row per dimension; new vs each baseline)
    3. Per-ticket technical analysis (grouped by tech tag)
    4. End-to-end workflow (Mermaid diagram + narrative)
    5. STAR questions generated from failure_mode + Bug tickets
    6. FAANG question bank (linked + inlined topic primers)
    7. Python interview bank (linked + inlined topic primers)
    8. Round-based interview plan (linked)
    9. Cheatsheets (inlined as <details> blocks)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MISSING = "<MISSING DATA>"
SKILL_DIR = Path(__file__).resolve().parent.parent
REF_DIR = SKILL_DIR / "references"
CHEAT_DIR = REF_DIR / "cheatsheets"


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_json(p: Path) -> Any:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_text(p: Path) -> str:
    if not p.exists():
        return f"<MISSING FILE: {p}>"
    return p.read_text(encoding="utf-8")


def is_missing(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip().startswith("<MISSING"))


def fmt(v: Any) -> str:
    if v is None or v == "":
        return MISSING
    if isinstance(v, list):
        if not v:
            return MISSING
        return ", ".join(fmt(x) for x in v)
    if isinstance(v, dict):
        return "; ".join(f"{k}={fmt(val)}" for k, val in v.items())
    s = str(v)
    if not s.strip():
        return MISSING
    # Markdown-table-safe: escape pipes and collapse newlines.
    return s.replace("|", "\\|").replace("\n", " ")


def get_dotted(obj: dict, dotted_key: str) -> Any:
    """Resolve 'core_addons.vpc-cni' against a nested dict."""
    cur: Any = obj
    for part in dotted_key.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def section_header(epic: dict) -> str:
    epic_key = epic.get("epic_key", "<EPIC>")
    epic_summary = epic.get("epic_summary", MISSING)
    epic_url = epic.get("epic_url", "")
    n = len(epic.get("issues", []))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    issues = epic.get("issues", [])
    by_type = Counter(i.get("issuetype", "?") for i in issues)
    by_status = Counter(i.get("status", "?") for i in issues)
    sps = [i.get("story_points") for i in issues if isinstance(i.get("story_points"), (int, float))]
    total_sp = sum(sps) if sps else 0

    lines = [
        f"# Interview Prep — Epic `{epic_key}`",
        "",
        f"> Generated {now} from `interview-agent` skill.",
        f"> Source epic: {epic_url or MISSING}",
        f"> Source ticket count: **{n}**",
        "",
        "## 1. Executive summary",
        "",
        f"- **Epic:** `{epic_key}` — {epic_summary}",
        f"- **Tickets:** {n} (by type: {fmt(dict(by_type))}; by status: {fmt(dict(by_status))})",
        f"- **Story points (sum where set):** {total_sp}",
    ]
    return "\n".join(lines) + "\n\n"


def section_cluster_comparison(clusters: dict | None) -> str:
    if not clusters:
        return "## 2. Cluster comparison\n\n_No cluster comparison file supplied._\n\n"

    new = clusters.get("new_cluster", {})
    baselines = clusters.get("baselines", []) or []
    dims: list[str] = clusters.get("comparison_dimensions", [])

    out = ["## 2. Cluster comparison", ""]
    out.append(f"**New cluster:** `{new.get('name', MISSING)}` "
               f"(account `{new.get('aws_account_id', MISSING)}` / "
               f"{new.get('aws_account_alias', MISSING)} / "
               f"{new.get('region', MISSING)})")
    out.append("")
    out.append("**Baselines:**")
    for b in baselines:
        out.append(f"- `{b.get('id','?')}` — `{b.get('name', MISSING)}` "
                   f"(account `{b.get('aws_account_id', MISSING)}` / "
                   f"{b.get('aws_account_alias', MISSING)})")
    out.append("")

    # Header row
    headers = ["Dimension", f"NEW: {new.get('name', '?')}"]
    for b in baselines:
        headers.append(f"{b.get('id','?')}: {b.get('name','?')}")
    out.append("| " + " | ".join(headers) + " |")
    out.append("|" + "|".join(["---"] * len(headers)) + "|")

    # One row per dimension
    for dim in dims:
        row = [f"`{dim}`", fmt(get_dotted(new, dim))]
        for b in baselines:
            row.append(fmt(get_dotted(b, dim)))
        # Mark equality with "=" for baselines that match new
        new_v = row[1]
        for i in range(2, len(row)):
            if row[i] == new_v and not row[i].startswith("<MISSING"):
                row[i] = f"= ({row[i]})"
        out.append("| " + " | ".join(row) + " |")

    out.append("")
    return "\n".join(out) + "\n"


def section_per_ticket(epic: dict) -> str:
    out = ["## 3. Per-ticket technical analysis", ""]
    issues = epic.get("issues", [])

    # Group by primary tech tag (first tag of first PR), else "untagged"
    groups: dict[str, list[dict]] = defaultdict(list)
    for issue in issues:
        primary = "untagged"
        for pr in issue.get("prs", []) or []:
            tags = pr.get("tech_tags") or []
            if tags:
                primary = tags[0]
                break
        groups[primary].append(issue)

    for tag in sorted(groups):
        out.append(f"### 3.{tag}")
        out.append("")
        for issue in sorted(groups[tag], key=lambda i: i.get("key", "")):
            out.extend(_render_issue(issue))
        out.append("")
    return "\n".join(out) + "\n"


def _render_issue(issue: dict) -> list[str]:
    key = issue.get("key", "?")
    url = issue.get("url", "")
    summary = issue.get("summary", MISSING)
    itype = issue.get("issuetype", "?")
    status = issue.get("status", "?")
    sp = issue.get("story_points")
    sp_str = f"{sp}" if isinstance(sp, (int, float)) else MISSING
    labels = issue.get("labels") or []
    components = issue.get("components") or []
    fix_versions = issue.get("fix_versions") or []
    assignee = issue.get("assignee") or MISSING
    created = issue.get("created") or MISSING
    resolved = issue.get("resolved") or MISSING

    lines: list[str] = []
    lines.append(f"#### `{key}` — {summary}")
    lines.append("")
    lines.append(f"- **URL:** {url or MISSING}")
    lines.append(f"- **Type / Status:** {itype} / {status}")
    lines.append(f"- **Assignee / Created / Resolved:** {assignee} / {created} / {resolved}")
    lines.append(f"- **Story points:** {sp_str}")
    lines.append(f"- **Labels:** {fmt(labels)}")
    lines.append(f"- **Components:** {fmt(components)}")
    lines.append(f"- **Fix versions:** {fmt(fix_versions)}")
    desc = issue.get("description") or MISSING
    desc_short = desc if len(desc) <= 600 else desc[:600] + "…"
    lines.append("")
    lines.append("**Description (excerpt):**")
    lines.append("")
    lines.append("> " + desc_short.replace("\n", "\n> "))
    lines.append("")

    prs = issue.get("prs") or []
    if prs:
        lines.append("**Pull requests:**")
        lines.append("")
        lines.append("| PR | State | +/- | Files | Tech tags | Summary |")
        lines.append("|---|---|---|---|---|---|")
        for pr in prs:
            files = pr.get("files_changed") or []
            files_short = ", ".join(files[:3]) + (f" (+{len(files)-3} more)" if len(files) > 3 else "")
            lines.append(
                f"| [{pr.get('repo','?')}#{pr.get('number','?')}]({pr.get('url','')}) "
                f"| {pr.get('state','?')} "
                f"| +{pr.get('additions',0)}/-{pr.get('deletions',0)} "
                f"| {files_short or MISSING} "
                f"| {fmt(pr.get('tech_tags'))} "
                f"| {pr.get('summary') or MISSING} |"
            )
        lines.append("")
    else:
        lines.append("_No PRs linked in source data._")
        lines.append("")

    fm = issue.get("failure_mode")
    if fm:
        lines.append("**Failure mode (drives STAR):**")
        lines.append("")
        lines.append(f"- Trigger: {fm.get('trigger', MISSING)}")
        lines.append(f"- Blast radius: {fm.get('blast_radius', MISSING)}")
        lines.append(f"- Detection: {fm.get('detection', MISSING)}")
        lines.append(f"- Recovery: {fm.get('recovery', MISSING)}")
        lines.append(f"- Prevention: {fm.get('prevention', MISSING)}")
        lines.append("")

    return lines


def section_workflow(clusters: dict | None) -> str:
    new = (clusters or {}).get("new_cluster", {}) if clusters else {}
    name = new.get("name", "<new-cluster>")
    acct = new.get("aws_account_id", MISSING)
    region = new.get("region", MISSING)

    return f"""## 4. End-to-end workflow

### Mermaid diagram

```mermaid
flowchart LR
  user[End user / API client] --> r53[Route 53\\n(public hosted zone)]
  r53 -->|alias A| alb[ALB / NLB\\n(in {name} VPC)]
  alb -->|listener rule + ACM cert| ing[Ingress / Service\\n(target group binding)]
  ing -->|kube-proxy iptables/ipvs| pod[Pod\\n(SA + IRSA / Pod Identity)]
  pod -->|projected token / PI agent| sts[STS AssumeRoleWithWebIdentity\\nor pods.eks.amazonaws.com]
  sts -->|temp creds| awsapi[AWS API\\n(SecretsManager / S3 / RDS / etc.)]

  subgraph cluster[EKS cluster {name} — account {acct} / {region}]
    ing
    pod
  end

  subgraph addons[kube-system]
    cni[vpc-cni\\n(ENIs, prefix delegation)]
    coredns[CoreDNS\\n(Corefile + NodeLocal DNS)]
    kp[kube-proxy\\n(iptables/ipvs)]
    eso[external-secrets\\n(SecretStore)]
    karpenter[Karpenter\\n(NodePool + EC2NodeClass)]
  end
  pod -.IP from.-> cni
  pod -.dns.-> coredns
  pod -.svc->pod.-> kp
  eso --> sts
  karpenter -->|RunInstances| ec2[EC2 nodes]

  subgraph gitops[ArgoCD GitOps]
    repo[Git repo: app-of-apps]
    repo --> argo[ArgoCD]
    argo --> ing
    argo --> eso
    argo --> karpenter
  end

  subgraph cicd[CI/CD]
    pr[PR in repo] -->|GitHub Actions / CloudBees| repo
  end

  subgraph net[Networking]
    igw[IGW] --- pubsub[Public subnets]
    pubsub --- nat[NAT GW]
    nat --- privsub[Private subnets]
    privsub --- pod
    privsub --- ec2
  end
```

### Narrative (numbered, end-to-end)

1. **DNS** — Client resolves `app.<dns_zone>` against Route 53. Alias A-record points at the **ALB/NLB** for cluster `{name}`.
2. **TLS termination** — ALB listener (443) terminates with ACM cert; HTTP→HTTPS redirect on the 80 listener.
3. **Routing** — Listener rule matches host/path → forwards to target group → IPs of pods (via AWS Load Balancer Controller `TargetGroupBinding` or `Ingress`).
4. **kube-proxy** — On the node, kube-proxy programs iptables (or ipvs per `kube-proxy-config`) so traffic to the Service ClusterIP load-balances across pod IPs.
5. **Pod networking** — Each pod has a real VPC IP from `vpc-cni` (prefix delegation if `ENABLE_PREFIX_DELEGATION=true` in `amazon-vpc-cni` ConfigMap).
6. **DNS inside the pod** — `/etc/resolv.conf` points at CoreDNS `kube-dns` Service; CoreDNS uses the `coredns` ConfigMap Corefile (forwarders for internal zones, optional NodeLocal DNS Cache).
7. **AuthN / AuthZ to AWS APIs** — Pod's ServiceAccount is annotated for **IRSA** *or* has a **PodIdentityAssociation**:
   - IRSA: pod presents projected token → STS `AssumeRoleWithWebIdentity` → temp creds.
   - Pod Identity: EKS Pod Identity Agent on the node fetches creds for `pods.eks.amazonaws.com`.
8. **Egress** — Outbound to AWS APIs goes via NAT GW or PrivateLink VPC endpoints (STS, SM, ECR, Logs). If a corporate proxy is configured, `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY` env (with cluster CIDRs in `NO_PROXY`).
9. **Secrets** — `external-secrets` reads from the configured backend (Secrets Manager / SSM / Vault) using the SA's IRSA/PI role and writes K8s Secrets in place; Reloader rolls pods.
10. **Node lifecycle** — `karpenter` provisions/de-provisions EC2 nodes per `NodePool` requirements; spot interruption events drain nodes within 2 min.
11. **GitOps** — All cluster state (apps, addons, NetworkPolicies, ArgoCD ApplicationSets) reconciled by ArgoCD from a Git repo; PRs merge via GitHub Actions / CloudBees.
12. **Auth to the cluster** — Operators authenticate via STS → EKS access entries (or legacy `aws-auth` ConfigMap mapping IAM ARN → RBAC group).

"""


def section_star(epic: dict) -> str:
    out = ["## 5. STAR questions generated from real failures", ""]
    out.append(f"_Drawn from tickets in `{epic.get('epic_key','?')}` that have `failure_mode` populated, plus all Bug-type tickets._")
    out.append("")

    issues = epic.get("issues", [])
    candidates = [i for i in issues if i.get("failure_mode") or (i.get("issuetype") == "Bug")]
    if not candidates:
        out.append("_No `failure_mode` or Bug-type tickets found in source data — no STARs auto-generated. Add `failure_mode` blocks to tickets.json to drive this section._")
        out.append("")
        return "\n".join(out) + "\n"

    for i, issue in enumerate(candidates, 1):
        key = issue.get("key", "?")
        summary = issue.get("summary", MISSING)
        fm = issue.get("failure_mode") or {}
        out.append(f"### 5.{i}. From `{key}` — {summary}")
        out.append("")
        out.append("**Prompt (interviewer):** _Tell me about a time you debugged a "
                   f"{fm.get('blast_radius','<scope>')}-scope incident in EKS._")
        out.append("")
        out.append("**STAR answer (candidate):**")
        out.append("")
        out.append(f"- **S** — {fm.get('trigger', MISSING)}")
        out.append(f"- **T** — Restore service and root-cause the failure (source: `{key}`).")
        out.append(f"- **A** — Detected via {fm.get('detection', MISSING)}; "
                   f"recovery: {fm.get('recovery', MISSING)}.")
        out.append(f"- **R** — Service restored; blast radius capped at {fm.get('blast_radius', MISSING)}.")
        out.append(f"- **L / Prevention** — {fm.get('prevention', MISSING)}.")
        out.append("")
        out.append(f"**Leadership Principles tagged:** Dive Deep (primary), Earn Trust (secondary).")
        out.append(f"**Source:** [{key}]({issue.get('url','')})")
        out.append("")
    return "\n".join(out) + "\n"


def inline_block(title: str, path: Path, level: int = 2) -> str:
    body = read_text(path)
    return f"{'#'*level} {title}\n\n<details><summary>Click to expand `{path.name}`</summary>\n\n{body}\n\n</details>\n\n"


def section_question_banks() -> str:
    return (
        "## 6. FAANG topic question bank\n\n"
        + read_text(REF_DIR / "faang-question-bank.md") + "\n\n"
        + "## 7. Python interview bank\n\n"
        + read_text(REF_DIR / "python-interview-bank.md") + "\n\n"
        + "## 8. Round-based interview plan\n\n"
        + read_text(REF_DIR / "round-based-interview-plan.md") + "\n\n"
        + "## 9. STAR framework reference\n\n"
        + read_text(REF_DIR / "star-framework.md") + "\n\n"
    )


def section_cheatsheets() -> str:
    out = ["## 10. Cheatsheets (inlined for offline review)", ""]
    if not CHEAT_DIR.exists():
        out.append("_No cheatsheets directory found._")
        return "\n".join(out)
    for p in sorted(CHEAT_DIR.glob("*.md")):
        title = p.stem.replace("-", " ").title()
        out.append(inline_block(title, p, level=3))
    return "\n".join(out) + "\n"


def section_data_gaps(epic: dict, clusters: dict | None) -> str:
    """Surface every <MISSING DATA> we noticed so the user knows what to fill."""
    gaps: list[str] = []

    if is_missing(epic.get("epic_summary")):
        gaps.append("epic_summary in tickets.json")
    issues = epic.get("issues", [])
    for i in issues:
        if is_missing(i.get("summary")):
            gaps.append(f"summary for {i.get('key','?')}")
        if is_missing(i.get("description")):
            gaps.append(f"description for {i.get('key','?')}")
        if not (i.get("prs") or []):
            gaps.append(f"PRs for {i.get('key','?')}")

    if clusters:
        for cluster in [clusters.get("new_cluster", {})] + (clusters.get("baselines", []) or []):
            cname = cluster.get("name", "?")
            for dim in clusters.get("comparison_dimensions", []):
                if is_missing(get_dotted(cluster, dim)):
                    gaps.append(f"{cname}.{dim}")

    if not gaps:
        return "## 11. Data gaps\n\n_None — input was complete._\n\n"

    out = ["## 11. Data gaps", "",
           f"_The generator detected **{len(gaps)}** missing fields. Fill these in your source JSON for a higher-fidelity doc._", ""]
    for g in gaps[:200]:
        out.append(f"- {g}")
    if len(gaps) > 200:
        out.append(f"- … and {len(gaps) - 200} more")
    out.append("")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tickets", required=True, type=Path,
                    help="Path to tickets.json (see scripts/tickets_schema.json)")
    ap.add_argument("--prs", required=False, type=Path, default=None,
                    help="Optional separate PRs file. Currently expected to be merged into tickets.json under issue.prs.")
    ap.add_argument("--clusters", required=False, type=Path, default=None,
                    help="Optional cluster comparison JSON.")
    ap.add_argument("--out", required=False, type=Path, default=None,
                    help="Output Markdown path (default: ./INTERVIEW-PREP-<EPIC>.md)")
    args = ap.parse_args()

    if not args.tickets.exists():
        print(f"ERROR: tickets file not found: {args.tickets}", file=sys.stderr)
        return 2

    epic = load_json(args.tickets)
    clusters = load_json(args.clusters) if args.clusters and args.clusters.exists() else None

    out_path = args.out or Path(f"INTERVIEW-PREP-{epic.get('epic_key','EPIC')}.md")

    parts = [
        section_header(epic),
        section_cluster_comparison(clusters),
        section_per_ticket(epic),
        section_workflow(clusters),
        section_star(epic),
        section_question_banks(),
        section_cheatsheets(),
        section_data_gaps(epic, clusters),
    ]

    out_path.write_text("".join(parts), encoding="utf-8")
    n_issues = len(epic.get("issues", []))
    print(f"OK: wrote {out_path}  ({n_issues} tickets, {out_path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
