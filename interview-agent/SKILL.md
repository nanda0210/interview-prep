# Interview Agent

> A skill that turns a real epic + its child tickets + linked PRs into an
> evidence-grounded interview-prep document for an SRE / Platform / Cloud role.
>
> **Hiring lens:** AWS, Amazon, Salesforce, GE, PayPal, Google, Meta, Apple, NVIDIA.
> The skill assumes the candidate is being interviewed for a senior SRE / EKS
> Platform Engineer position and the epic represents 6–12 months of real work.

---

## 1. When to use this skill

Use this skill when **all** of the following are true:

1. You have a real Jira epic (e.g. `FSRE-20`) with child tickets and linked PRs.
2. You have, or can produce, a JSON dump of those tickets (see `scripts/tickets_schema.json`).
3. You want a single Markdown document a candidate can revise from, that:
   - Summarises every ticket and the technical change it introduced.
   - Compares the *new* environment with the *existing* baseline environments.
   - Generates a **technical workflow** stitching every resource together.
   - Generates **STAR questions with answers** drawn from real failures and recoveries in the tickets.
   - Adds **FAANG-style technical questions**, **Python questions**, **round-based interview plans**, and **cheat sheets**.

Do **not** use this skill if you do not have ticket data. The skill refuses to
fabricate ticket content; the generator script will emit `<MISSING DATA>`
markers wherever input is missing rather than guess.

---

## 2. Inputs

| Input | Where | Required |
|---|---|---|
| Tickets JSON | `./artifacts/<epic>/tickets.json` | Yes |
| Pull Request JSON (optional but recommended) | `./artifacts/<epic>/prs.json` | No |
| Cluster comparison context | CLI arg `--clusters cluster_compare.json` | No |
| Output path | CLI arg `--out` (default `./INTERVIEW-PREP-<EPIC>.md`) | No |

The schema for `tickets.json` is in `scripts/tickets_schema.json`. A worked
example is in `examples/sample-tickets.json`.

---

## 3. Outputs

A single self-contained Markdown file (default `INTERVIEW-PREP-<EPIC>.md`) with:

1. **Executive summary** — epic intent, scope, time window, headcount footprint.
2. **Per-ticket technical analysis** — for each child ticket:
   - Summary, status, story points, fix versions
   - PRs linked, repos touched, Terraform / Helm / ArgoCD / IAM / SG / DNS / TLS deltas
   - Risk classification (low / medium / high) and blast radius
3. **Cluster comparison table** — new cluster vs each existing cluster across
   account, VPC, CIDR, subnets, NAT/IG, SG inbound/outbound, EKS version, addons,
   Karpenter NodePools, External Secrets, IRSA vs Pod Identity, ArgoCD app-of-apps,
   ConfigMaps (`amazon-vpc-cni`, `aws-auth`, `coredns`, `extension-apiserver-authentication`,
   `kube-apiserver-legacy-sa-token-tracking`, `kube-proxy`, `kube-proxy-config`).
4. **End-to-end workflow** — a Mermaid diagram + numbered narrative tracing a
   request from DNS → ALB/NLB → SG → Service → Pod → IAM → downstream AWS service.
5. **STAR questions with answers** — generated from real ticket failures and
   recoveries. Each STAR is tagged with the ticket(s) it derives from.
6. **FAANG topic question bank** — see `references/faang-question-bank.md`.
7. **Python interview bank** — see `references/python-interview-bank.md`.
8. **Round-based interview plan** — phone screen → coding → systems design →
   deep-dive → bar-raiser. See `references/round-based-interview-plan.md`.
9. **Cheat sheets** — one-page references inlined per topic. See
   `references/cheatsheets/`.

---

## 4. Workflow

```
+------------------+      +-------------------+      +-------------------------+
| tickets.json     | ---> | generate_         | ---> | INTERVIEW-PREP-<EPIC>.md|
| prs.json (opt.)  |      | interview_doc.py  |      | (single Markdown file)  |
| cluster_compare  |      |                   |      |                         |
+------------------+      +-------------------+      +-------------------------+
        ^                          |
        |                          v
        |                +-------------------+
        |                | references/*.md  |
        |                | cheatsheets/*.md |
        |                +-------------------+
        |
   (you produce this from Jira REST or by paste)
```

---

## 5. Step-by-step usage

### Step 1 — Produce `tickets.json`

Option A (Jira REST, recommended):

```bash
JQL='"Epic Link" = FSRE-20 OR key = FSRE-20'
curl -s -H "Authorization: Bearer $JIRA_PAT" \
     -G "https://cisco-cxe.atlassian.net/rest/api/3/search" \
     --data-urlencode "jql=$JQL" \
     --data-urlencode "fields=summary,status,issuetype,priority,labels,components,fixVersions,assignee,description,created,resolutiondate,customfield_10016" \
     --data-urlencode "maxResults=100" \
  | jq '{epic_key:"FSRE-20", issues: .issues}' \
  > artifacts/fsre-20/tickets.json
```

Option B (paste): hand-build the JSON following `scripts/tickets_schema.json`.

### Step 2 — (Optional) produce `prs.json`

For each ticket, fetch its remote-link PRs via Jira's `remotelink` endpoint, then
fetch each PR diff via `gh pr view --json` or GitHub REST. Save as a list of
`{ticket_key, repo, pr_number, title, files_changed, additions, deletions, summary }`.

### Step 3 — Run the generator

```bash
python agents/devex-agent/skills/interview-agent/scripts/generate_interview_doc.py \
  --tickets artifacts/fsre-20/tickets.json \
  --prs     artifacts/fsre-20/prs.json \
  --clusters agents/devex-agent/skills/interview-agent/examples/cluster-compare-fsre-20.json \
  --out     INTERVIEW-PREP-FSRE-20.md
```

### Step 4 — Review

Open `INTERVIEW-PREP-FSRE-20.md`. Sections marked `<MISSING DATA: ...>` indicate
where the source JSON did not provide enough signal — fill them in by hand if
needed.

---

## 6. Authoring rules (the skill's contract)

1. **Never fabricate** ticket facts, PR diffs, account IDs, CIDRs, or SG rules.
   When source data is missing, write `<MISSING DATA: <what>>`.
2. Every STAR answer that claims a real incident **must** cite the ticket key it
   came from in the form `(source: FSRE-2702)`.
3. Every cheat sheet is a single screen — if it grows past ~60 lines, split it.
4. Every FAANG / Python question must have a real answer (no "left as exercise").
5. The cluster comparison table must call out **every difference** between the
   new cluster and each baseline; equality is shown explicitly with `=`.

---

## 7. References

- `references/faang-question-bank.md`
- `references/python-interview-bank.md`
- `references/star-framework.md`
- `references/round-based-interview-plan.md`
- `references/cheatsheets/aws-eks.md`
- `references/cheatsheets/iam-irsa-podidentity.md`
- `references/cheatsheets/networking-vpc-sg.md`
- `references/cheatsheets/karpenter.md`
- `references/cheatsheets/argocd-helm.md`
- `references/cheatsheets/external-secrets.md`
- `references/cheatsheets/eks-configmaps.md`
- `references/cheatsheets/terraform.md`
- `references/cheatsheets/python-sre.md`
