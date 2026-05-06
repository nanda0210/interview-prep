# STAR Framework — Interview Stories that Land

> **STAR = Situation · Task · Action · Result.**
> FAANG variants add **Reflection / Learning** at the end (sometimes called STAR-L or SOAR).
> Amazon explicitly wants STAR + Leadership Principles tagged.
> Google wants STAR + measurable impact + your specific contribution (use "I" not "we").

---

## 1. The shape of a strong STAR

| Beat | Length | What goes in | Common failure |
|---|---|---|---|
| **S — Situation** | 20–30 s | One concrete sentence of context: which system, which env, which scale, what was at stake. | Vague ("our team had reliability issues"). |
| **T — Task** | 10–20 s | Your specific responsibility — not the team's. | Switching to "we." Interviewer can't tell what *you* did. |
| **A — Action** | 60–120 s | 3–5 specific technical actions, in order, with the *why* behind each. | Listing tools without showing decisions/trade-offs. |
| **R — Result** | 20–40 s | Quantified outcome (latency, $, MTTR, deploys/day, blast radius). | Soft results ("things improved"). |
| **L — Learning** | 10–20 s | What you'd do differently / how it changed your playbook. | Skipping it — Amazon bar-raisers explicitly look for it. |

Total: **2–3 minutes**. Practise with a stopwatch.

---

## 2. Tagging stories to Leadership Principles (Amazon-style)

Each story should map cleanly to **1 primary + 1 secondary** LP. The shortlist:

| LP | When to claim it |
|---|---|
| Customer Obsession | You traced a decision back to a user/SLO impact |
| Ownership | You acted outside your lane to prevent harm |
| Invent and Simplify | You replaced a complex system with a simpler one |
| Are Right, A Lot | You made a non-obvious call that turned out right |
| Learn and Be Curious | You picked up a new tech under pressure |
| Hire and Develop | You mentored someone or raised the team's bar |
| Insist on the Highest Standards | You blocked a release / pushed back on shortcuts |
| Think Big | You proposed/built something beyond your immediate scope |
| Bias for Action | You acted on incomplete info to prevent a worse outcome |
| Frugality | You cut cost / reduced toil with a simple change |
| Earn Trust | You owned a failure publicly, fixed it, communicated |
| Dive Deep | You went past the symptom to the root cause |
| Have Backbone; Disagree and Commit | You disagreed in a meeting, lost, executed anyway |
| Deliver Results | You shipped under constraint with measurable outcome |

---

## 3. STAR templates (fill from real tickets)

### Template A — Incident-driven STAR (from a Bug ticket with `failure_mode`)

```
S: <env / cluster / service>; <user impact in 1 line>; happened on <date>; <severity>.
T: I was the on-call SRE / tech lead for <component>; my job was to <restore | RCA | prevent recurrence>.
A:
  1. Detected via <signal>; first action was <triage step> because <hypothesis>.
  2. Ruled out <X> by <evidence>; pivoted to <Y>.
  3. Mitigated by <action> within <minutes>; this restored <metric>.
  4. Root caused to <root cause> via <log/trace/k8s evidence>.
  5. Permanent fix: <PR / config / process change>; landed in <ticket>.
R: <quantified> — MTTR <X min>, blast radius limited to <scope>, no recurrence in <window>.
L: We added <preventive control>; updated runbook; what I'd do differently is <X>.
LP (primary): Dive Deep. (secondary): Earn Trust.
Source: <FSRE-XXXX>
```

### Template B — Build / project STAR (from a Story ticket)

```
S: We were standing up <new cluster / capability> in <account/region>; goal was <business outcome>.
T: I owned <module/component>: <design | implementation | rollout>.
A:
  1. Surveyed existing <baseline cluster A and B> and identified <N differences> that mattered: <list>.
  2. Decided to <choice> over <alternative> because <trade-off>.
  3. Implemented via <Terraform module | Helm chart | ArgoCD app>; PR <#> reviewed by <peers>.
  4. Rolled out behind <feature flag | canary cluster>; verified with <tests | smoke | canary>.
  5. Documented in <runbook / arch doc>; trained <N> teammates.
R: <env live by date>, <cost / latency / reliability outcome>, picked up by <N> downstream teams.
L: Next time I'd <X>; the playbook is now <reusable artifact>.
LP (primary): Deliver Results. (secondary): Insist on the Highest Standards.
Source: <FSRE-XXXX>
```

### Template C — Disagreement STAR (Backbone / Disagree & Commit)

```
S: A change was proposed: <change>. I believed it would <risk>.
T: I had to either accept it or push back, knowing the team wanted to ship.
A:
  1. Wrote a 1-pager with <data / past incident> showing the risk.
  2. Proposed alternative: <X>, with cost/benefit.
  3. We met, debated; the team chose <original / mine / hybrid>.
  4. <If I lost:> I committed and helped execute; added monitoring for the risk I'd flagged.
R: <Outcome>. <If risk materialised, my monitoring caught it in <X min>; if not, I learned <Y>.>
L: <Insight about pushing back constructively.>
LP (primary): Have Backbone; Disagree and Commit.
```

---

## 4. Worked example (using FSRE-2702 sample failure_mode)

> Note: this example uses the placeholder data in `examples/sample-tickets.json`. Replace
> with your real ticket facts — never ship STAR with fabricated details.

**S** (FSRE-2702): During the bootstrap of `cx-usw2-dev01-apps-eks-01` in account `851725553396`, External Secrets pods went into CrashLoopBackOff right after ArgoCD synced the platform app-of-apps. Onboarding teams were blocked from getting secrets into the new cluster.

**T**: I was the platform on-call. My job: restore External Secrets so onboarding teams could land workloads, and root-cause the trust failure.

**A**:
1. Detected the failure via ArgoCD app health degraded + kube-state-metrics alert on container restarts.
2. `kubectl logs` showed `WebIdentityErr: failed to assume role`. Hypothesis: IRSA trust policy mismatch.
3. Inspected the trust policy in the new account; found two issues — wrong OIDC provider thumbprint (the apps account has its own provider, not the platform account's) and missing `:aud` claim.
4. Patched the Terraform `eks-irsa` module condition to assert both `:sub` (`system:serviceaccount:external-secrets:external-secrets`) and `:aud` (`sts.amazonaws.com`), plus the new account's OIDC provider URL. PR merged in <X> minutes.
5. Rotated the SA token; pods re-rolled and went healthy.
6. Added a Terratest case asserting the trust condition matches expected `sub`/`aud` for any new cluster.

**R**: External Secrets healthy within <Y> minutes of detection; blast radius capped at one namespace; no other workload affected; the regression test now blocks any future cluster with a malformed trust policy.

**L**: The bug was caused by copy-pasting the platform account's IRSA module without re-pointing OIDC. The fix is mechanical; the *real* fix was the regression test. I now treat "first cluster in a new account" as a high-risk class of change and require a peer-paired bootstrap.

**LP**: primary — Dive Deep; secondary — Insist on the Highest Standards.

**Source**: FSRE-2702.

---

## 5. STAR question prompts (interviewer side)

Ask the candidate one from each row. Strong candidates can produce a STAR per prompt within 30 seconds of thinking.

| # | Prompt | Looking for |
|---|---|---|
| 1 | Tell me about a time you stood up a new EKS cluster and what surprised you. | Build STAR (Template B). |
| 2 | Walk me through your worst on-call incident in the last year. | Incident STAR (Template A). |
| 3 | A time you disagreed with a senior engineer on a design choice. | Backbone STAR (Template C). |
| 4 | A time you cut cost or toil materially. | Frugality / Bias for Action. |
| 5 | A time your fix failed in production and what you did. | Earn Trust / Dive Deep. |
| 6 | A time you simplified something that was over-engineered. | Invent & Simplify. |
| 7 | A time you owned something outside your team's scope. | Ownership. |
| 8 | A time you mentored someone past a hard problem. | Hire & Develop. |
| 9 | A time you had to learn a new tech under deadline. | Learn & Be Curious. |
| 10 | The change you're most proud of and the one you regret. | Self-awareness + Reflection. |

---

## 6. Anti-patterns interviewers downgrade

- **Pronoun drift:** "we built a Karpenter rollout" — interviewer can't grade. Use *I*.
- **Tool soup:** "I used Terraform, Helm, ArgoCD, Karpenter, External Secrets, Vault…" — list of nouns, no verbs.
- **No metric:** "performance got better." → How much? Compared to what? Cost?
- **Missing trade-off:** every senior decision has a trade-off; if you don't name one, you sound junior.
- **Hero narrative:** if every story has you saving the day alone, the bar-raiser will probe and find inconsistencies.
- **Stale STAR:** > 3 years old reads as "haven't grown since." Mix recent + classic.
