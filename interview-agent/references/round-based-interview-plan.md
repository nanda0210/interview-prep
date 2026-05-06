# Round-Based Interview Plan

> A 5-round loop modelled on AWS / Amazon / Google / Meta / Salesforce SRE-Platform loops.
> Each round lists: **goal · interviewer profile · question pool · grading rubric · time budget**.

---

## Round 1 — Recruiter / Hiring Manager phone screen (30–45 min)

**Goal:** culture fit, broad scope check, salary alignment, motivation.

**Interviewer:** recruiter + sometimes the hiring manager.

**Questions:**
- Walk me through your last 18 months.
- Why this role / why this company / why now?
- Biggest impact you've shipped — 90 seconds.
- A time you had to push back. (Mini-STAR.)
- What does your ideal team look like?
- Compensation expectations.

**Rubric:**
- Story arc and clarity (can you summarise yourself in 90 s without rambling?).
- Scope of ownership (single service vs platform vs org).
- Authentic motivation, not buzzwords.

---

## Round 2 — Coding (60 min)

**Goal:** can you write working, tested Python under a clock?

**Interviewer:** mid/senior IC.

**Setup:** shared editor (CoderPad, HackerRank). Expect 1 medium + 1 follow-up.

**Question pool (pick 1):**
- Implement a token-bucket rate limiter (class with `try_acquire(tokens=1) -> bool`).
- Parse an EKS audit-log JSONL stream and find users with > N denied actions in a 5-min window.
- Given a list of S3 keys + sizes, group by prefix and return top-K largest prefixes (heap).
- Implement a thread-safe LRU.
- Walk a directory tree, hash files, return duplicate sets.
- Implement an exponential-backoff retry decorator with jitter (see `python-interview-bank.md` B5).

**Rubric (each weighted):**
| Dimension | Weight | What strong looks like |
|---|---|---|
| Clarifying Qs | 10% | Asks about input scale, edge cases, single-vs-multi-thread before coding |
| Approach narration | 15% | States plan in 60 s before typing |
| Correctness | 30% | Passes provided + 2 self-generated edge cases |
| Code quality | 20% | Functions < 30 lines, types, no dead branches |
| Complexity reasoning | 15% | States Big-O without prompting |
| Testing | 10% | Writes at least one assertion / pytest case |

---

## Round 3 — Systems / Cloud Design (60 min)

**Goal:** can you design a non-trivial AWS / EKS system end-to-end and defend trade-offs?

**Interviewer:** staff IC / architect.

**Question pool (pick 1):**
- Design a multi-region EKS platform with one app-of-apps repo and bounded blast radius per cluster.
- Design an external-secrets rotation pipeline with zero-downtime pod refresh.
- Design a tenant onboarding flow: create namespace, IRSA roles, ArgoCD ApplicationSet entry, NetworkPolicy, ResourceQuota — all from one PR.
- Design an EKS upgrade pipeline (control plane + addons + Karpenter AMI rotation) with automated rollback.
- Design a CI/CD pipeline that promotes a Helm chart from dev → nprd → prod with policy gates.
- Design observability for 100 EKS clusters: where does Prometheus live, how do you federate, what about logs and traces?

**Expected artifacts you draw on the whiteboard / Excalidraw:**
- Box diagram: VPC, subnets, EKS, node groups / Karpenter, ALB/NLB, R53, ACM, ECR, S3, KMS.
- Sequence diagram for the critical path (e.g. user → R53 → ALB → ingress → service → pod → IAM/IRSA → AWS API).
- Failure-mode table: what breaks, blast radius, MTTD, MTTR, recovery.

**Rubric:**
| Dimension | Weight |
|---|---|
| Requirements clarification (functional + non-functional) | 15% |
| API / data model | 10% |
| Scalability + bottleneck analysis | 20% |
| Failure modes + recovery | 20% |
| Security (IAM, networking, secrets) | 15% |
| Cost / operability | 10% |
| Trade-off articulation | 10% |

**Red flags interviewers note:**
- Picking a tool without saying why.
- Skipping failure modes ("happy path only").
- No mention of cost.
- "We'd just use AWS X" — without explaining how it's configured.

---

## Round 4 — Deep dive / domain (60 min)

**Goal:** prove you've actually shipped at depth, not just at surface.

**Interviewer:** senior IC in your specialty.

**Format:** 5–10 min on a real project of your choice → 50 min of interrogation.

**Topics they'll probe:**
- IRSA vs Pod Identity trust-policy specifics.
- Karpenter `NodePool` requirements + disruption budget.
- AWS LB Controller IngressGroup vs TargetGroupBinding — when each.
- VPC CNI `WARM_IP_TARGET` tuning, prefix delegation.
- CoreDNS NodeLocal DNS Cache architecture.
- ArgoCD sync waves, hooks, ignoreDifferences.
- Terraform state poisoning recovery.
- EKS upgrade gotchas (e.g. removed APIs in 1.29, IPv6, AL2023 migration).

**Rubric:**
- 5 layers deep on the candidate's claimed expertise without "I don't know" — or honest "I don't know but here's how I'd find out."
- Real numbers (cluster count, pod count, $/mo, latency p99).
- Owns trade-offs and failures from the project.

---

## Round 5 — Behavioural / Bar Raiser (45–60 min)

**Goal:** judgement, leadership, culture add.

**Interviewer:** Bar Raiser (Amazon) / leadership-principle interviewer (Google "Googleyness", Meta "Drive").

**Question pool — every prompt should get a STAR (see `star-framework.md` §5):**
- Tell me about a time you owned something nobody else would.
- A time you took a calculated risk that didn't pan out.
- A time you had to give hard feedback to a peer.
- A time customer / SLO needs forced you to delay a feature.
- A time you simplified an over-engineered system.
- A time you disagreed with your manager.
- A time you hired / mentored someone who exceeded expectations.
- A time you reduced cost meaningfully.
- A time you missed a deadline — what happened and what changed.

**Rubric (STAR-L):**
- Specificity (one project, one time, real names of systems).
- "I" not "we."
- Quantified result.
- Reflection / learning.
- LP coverage: across all stories you should hit ≥ 6 distinct LPs.

---

## Round 0 — Take-home (sometimes)

**Goal:** see real code style; reduces phone-screen noise.

**Typical brief (4–6 hours):** "Write a small Python service that consumes a stream of EKS events from a file, deduplicates by `(reason, involvedObject.name)` over a 5-min sliding window, and exposes Prometheus counters. Include tests + a README + a Dockerfile."

**Rubric:**
- README clarity (assumptions, how to run, trade-offs).
- Tests + coverage of edge cases.
- Idiomatic Python (types, asyncio if appropriate, no globals).
- Observability (logs at INFO, metrics counters).
- Containerised + non-root user + small image.
- Git hygiene (small commits, sensible messages).

---

## Loop-level guidance

| Signal | Loop-level outcome |
|---|---|
| 5/5 strong (≥ "Lean Hire") | Strong Hire — fast-track offer |
| 4/5 strong, 1 mixed | Hire — most common offer |
| 3/5 strong, 2 mixed | Discuss in debrief; usually No Hire unless mixed rounds were soft skills |
| Any "No Hire" from Bar Raiser | No Hire (Amazon) |
| Inconsistent stories (different timelines/numbers) across rounds | Auto No Hire — perceived as fabrication |

---

## What to bring to every round

- One 30-second pitch about yourself.
- Three project STARs ready: a build, an incident, a disagreement.
- Two "favourite" diagrams you can draw blindfolded (your last platform's request path; your IAM model).
- Numbers memorised: cluster count, RPS, p50/p99, error budget, $/mo, deploy frequency, MTTR.
- Two thoughtful questions per round that show you'd thrive there (not "what's the tech stack").
