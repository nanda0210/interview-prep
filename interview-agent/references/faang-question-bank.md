# FAANG-Style Technical Question Bank — SRE / EKS Platform

> **How to use:** Each section follows the format
> **Q** → **What they're testing** → **Strong answer** → **Follow-ups**.
> "Strong answer" is what a senior IC at AWS / Amazon / Salesforce / Google / Meta
> would consider a passing answer in 3–5 minutes. Memorise the *shape*, not the words.

Topics covered (in order):
1. EKS architecture & control plane
2. EKS networking (VPC CNI, pod CIDR, ENI exhaustion)
3. Security groups, NACLs, route tables
4. Load balancers (ALB vs NLB, TargetGroupBinding)
5. IAM — IRSA vs Pod Identity vs Node Role
6. Karpenter
7. ArgoCD & GitOps
8. Helm & release management
9. CoreDNS, kube-proxy, vpc-cni addon
10. The `aws-auth` ConfigMap and access entries
11. External Secrets Operator
12. EFS / EBS CSI drivers
13. Fargate
14. Terraform / Terragrunt
15. CI/CD (GitHub Actions vs CloudBees)
16. TLS, ACM, cert-manager, Route 53
17. Cluster lifecycle (create / upgrade / decommission)
18. Failure / recovery scenarios

---

## 1. EKS architecture & control plane

**Q1.1** What does AWS manage vs what you manage in EKS?
- *Testing:* shared-responsibility model.
- *Strong answer:* AWS manages the control plane (3× HA API server, etcd, controller-manager, scheduler) across 3 AZs; you don't see the EC2 instances. You manage data plane (worker nodes / Fargate profiles), addons (CNI, CoreDNS, kube-proxy unless using EKS-managed addons), IAM (IRSA / Pod Identity), and all workloads. AWS exposes the API via a regional endpoint with public/private/both modes.
- *Follow-ups:* what's the SLA (99.95 %)? What lives in etcd? Can you ssh to control plane (no)?

**Q1.2** Walk me from `kubectl apply` to a Pod running on a node.
- *Strong answer:* (1) kubectl resolves cluster endpoint via kubeconfig → (2) STS GetCallerIdentity via `aws-iam-authenticator` / EKS IAM webhook → (3) request hits API server, validated, mutating then validating admission webhooks → (4) object persisted in etcd → (5) controllers reconcile (Deployment → ReplicaSet → Pod) → (6) scheduler binds Pod to a Node → (7) kubelet on node pulls images, calls CRI (containerd) → (8) CNI (vpc-cni) allocates an ENI / secondary IP, plumbs veth → (9) kube-proxy / iptables programs Service ClusterIP → (10) readiness probe passes → endpoints updated.

**Q1.3** What's an EKS access entry and how does it relate to `aws-auth`?
- *Strong answer:* Pre-2023 the `aws-auth` ConfigMap mapped IAM ARNs to RBAC groups; brittle, race-prone. EKS access entries (API-driven) replace it: each entry maps an IAM principal to access policies (e.g. `AmazonEKSClusterAdminPolicy`) and/or Kubernetes groups. You set `authenticationMode = API` or `API_AND_CONFIG_MAP`. Migrating: keep `API_AND_CONFIG_MAP` during cutover, then switch to `API`.

---

## 2. EKS networking

**Q2.1** Why can a `t3.small` only run ~11 pods and how do you fix it?
- *Strong answer:* VPC CNI gives every pod a real VPC IP from a secondary ENI; max pods = `(maxENIs × (IPsPerENI − 1)) + 2`. For t3.small that's small. Fix options: bigger instance, **prefix delegation** (`ENABLE_PREFIX_DELEGATION=true`) which assigns a /28 per ENI (×16 IPs), or custom networking with secondary CIDR.

**Q2.2** Pod-to-pod traffic across AZs — does it leave the VPC?
- No. VPC CNI uses native VPC routing; cross-AZ traffic is intra-VPC but does incur cross-AZ data charges.

**Q2.3** You're seeing `IPAMD: failed to allocate IP address` on new pods. Diagnose.
- *Strong answer:* check `aws-node` DaemonSet logs; look at WARM_IP_TARGET / MINIMUM_IP_TARGET; check ENI limits on instance type; check subnet free IPs (`describe-subnets`); check IAM policy on node role (`AmazonEKS_CNI_Policy`); consider prefix delegation; check if SG attached to ENI is full.

---

## 3. Security groups, NACLs, route tables

**Q3.1** SG vs NACL — when to use which?
- *Strong answer:* SGs are stateful, attached to ENIs, allow-only, evaluated as a whole. NACLs are stateless, attached to subnets, allow + deny + ordered rules. Default to SGs; reach for NACLs only for blanket deny (e.g. block a CIDR), DDoS triage, or defense in depth.

**Q3.2** Cluster SG vs node SG vs additional cluster SG?
- Cluster SG: created by EKS, attached to control-plane ENIs and (by default) all node ENIs and pods using SG-for-pods → enables CP↔node and intra-cluster traffic. Node SG: extra SG you attach to the launch template. Additional cluster SGs: extra SGs you attach to control plane.

**Q3.3** A pod can't reach an RDS in the same VPC. Walk through diagnosis.
- *Answer:* (1) `kubectl exec` → `nc -vz rds-host 5432`; (2) check pod's SG (could be node SG or pod SG via `SecurityGroupPolicy`); (3) check RDS SG inbound for source SG / CIDR; (4) check route tables for the subnet — is there a route to RDS subnet?; (5) NACL on either subnet; (6) DNS resolution via CoreDNS — `kubectl exec ... nslookup`; (7) check VPC endpoint policy if RDS Proxy via PrivateLink.

---

## 4. Load balancers — ALB vs NLB

| Dimension | ALB | NLB |
|---|---|---|
| Layer | 7 (HTTP/HTTPS/gRPC) | 4 (TCP/UDP/TLS) |
| Routing | Host/path/header/query | 5-tuple |
| TLS termination | Yes | Yes (or pass-through) |
| Static IP | No (use NLB) | Yes (one EIP per AZ) |
| Source IP preserved | No (X-Forwarded-For) | Yes |
| Target types | instance, ip, lambda | instance, ip, alb |
| Latency | Higher | Lower (~ms) |

**Q4.1** Two services on the same ALB, different paths — how?
- *Answer:* one Ingress per service (or one IngressGroup) — annotate `alb.ingress.kubernetes.io/group.name`; the AWS Load Balancer Controller merges them into one ALB with separate listener rules.

**Q4.2** Why use TargetGroupBinding?
- Decouples LB lifecycle from K8s — you create the TG/listener via Terraform once, then bind pods to it from K8s. Survives namespace deletion; useful for blue/green at LB layer.

---

## 5. IAM — IRSA vs Pod Identity vs Node Role

**Q5.1** Compare IRSA vs Pod Identity.

| | IRSA | Pod Identity |
|---|---|---|
| How | OIDC federation; SA annotation `eks.amazonaws.com/role-arn` | EKS Pod Identity Agent DaemonSet + association API |
| Trust policy | Per-cluster OIDC provider, conditioned on `sub` | Single principal `pods.eks.amazonaws.com`, no per-cluster OIDC |
| Cross-cluster reuse | Re-issue trust per cluster | Same role, attach association per cluster |
| Token | Projected SA token, exchanged for STS | EKS Pod Identity Agent fetches creds locally |
| When to use | Older clusters, tooling that expects projected tokens | New clusters, simpler trust mgmt |

**Q5.2** Show the IRSA trust policy condition.
```json
"Condition": {
  "StringEquals": {
    "oidc.eks.us-west-2.amazonaws.com/id/EXAMPLE:sub": "system:serviceaccount:my-ns:my-sa",
    "oidc.eks.us-west-2.amazonaws.com/id/EXAMPLE:aud": "sts.amazonaws.com"
  }
}
```
*Common bug:* missing `:aud` claim → `WebIdentityErr`. Missing `sub` → any pod in the cluster can assume the role.

**Q5.3** Why is the node instance role dangerous to attach S3 admin?
- All pods on the node inherit it via IMDS (unless IMDSv2 hop limit = 1 + token required). Use IRSA / Pod Identity to scope per-workload.

---

## 6. Karpenter

**Q6.1** Karpenter vs Cluster Autoscaler?
- Karpenter is provisioner-driven and instance-agnostic — picks the cheapest fitting instance; Cluster Autoscaler scales preconfigured ASGs. Karpenter is faster (~30–60 s vs minutes), supports consolidation (bin-packing), and handles spot interruption natively.

**Q6.2** What's a `NodePool` and a `NodeClass`?
- `EC2NodeClass` (v1): launch template (AMI family, subnets, SGs, IAM role, blockDeviceMappings). `NodePool` (v1): scheduling constraints (taints, labels, requirements like `karpenter.k8s.aws/instance-family In [m6i, m7i]`), disruption budget, expireAfter.

**Q6.3** Spot interruption — what happens?
- Karpenter watches the EventBridge interruption event (2 min warning), cordons + drains the node, and provisions replacement before termination. You also need pod disruption budgets and graceful termination handlers.

**Q6.4** A pending pod won't schedule. Karpenter logs say "no instance type satisfied requirements." Diagnose.
- Check pod requests vs NodePool `requirements`; check `topologySpreadConstraints`; check taints/tolerations; check resource limits (gpu? arm64?); check `nodeSelector`.

---

## 7. ArgoCD & GitOps

**Q7.1** App-of-apps vs ApplicationSet?
- *App-of-apps:* one ArgoCD Application that templates child Applications via Helm/Kustomize. Manual.
- *ApplicationSet:* CRD with generators (list, cluster, git, matrix) that *generates* Applications. Use for multi-cluster fan-out.

**Q7.2** A sync is stuck "Progressing." How do you debug?
- `argocd app get <app>`; check resource health (e.g. Deployment progressDeadlineSeconds); check sync waves; check hooks (PreSync/PostSync); look at `argocd-application-controller` logs; check resource hooks not finishing.

**Q7.3** Self-heal and auto-sync — risks?
- Drift correction can fight with HPA, manual hotfixes; use `ignoreDifferences` for replica counts. Self-heal can re-create resources you intentionally deleted.

---

## 8. Helm

**Q8.1** Helm 3 vs Helm 2?
- No tiller; release state in K8s Secrets in the release namespace; CRD support; library charts.

**Q8.2** Three-way merge — what does Helm actually compare?
- Old release manifest (in Secret) vs new rendered manifest vs live cluster state. Helps catch out-of-band drift.

**Q8.3** What does `helm rollback` do under the hood?
- Reads the previous release Secret, re-applies its manifest, runs hooks, increments revision.

---

## 9. CoreDNS, kube-proxy, vpc-cni

**Q9.1** Why is CoreDNS sometimes the SPOF of an EKS cluster?
- Because every pod's DNS resolution goes through it; if CoreDNS pods are CPU-throttled or evicted, every service-to-service call breaks. Mitigations: NodeLocal DNSCache DaemonSet, autoscale CoreDNS, set proper requests/limits, distribute across AZs with `topologySpreadConstraints`.

**Q9.2** kube-proxy modes?
- `iptables` (default), `ipvs` (better perf at scale), `nftables` (newer). On EKS, default iptables. Switch to ipvs when service count > ~5000.

**Q9.3** Custom CoreDNS Corefile — how to add upstream zone?
```yaml
# ConfigMap: coredns
data:
  Corefile: |
    .:53 {
      errors
      health { lameduck 5s }
      kubernetes cluster.local in-addr.arpa ip6.arpa { pods insecure }
      forward . /etc/resolv.conf
      cache 30
      reload
      loadbalance
    }
    internal.example.com:53 {
      forward . 10.0.0.2 10.0.0.3
    }
```

---

## 10. The `aws-auth` ConfigMap and access entries

**Q10.1** Show a minimal `aws-auth` mapping.
```yaml
apiVersion: v1
kind: ConfigMap
metadata: { name: aws-auth, namespace: kube-system }
data:
  mapRoles: |
    - rolearn: arn:aws:iam::111122223333:role/eks-node-role
      username: system:node:{{EC2PrivateDNSName}}
      groups: [system:bootstrappers, system:nodes]
    - rolearn: arn:aws:iam::111122223333:role/sre-admin
      username: sre-admin
      groups: [system:masters]
```

**Q10.2** Why are access entries safer?
- `aws-auth` is a single ConfigMap — concurrent edits race; a malformed YAML can lock everyone out. Access entries are API-driven, atomic, auditable in CloudTrail, and can be IaC'd.

---

## 11. External Secrets Operator

**Q11.1** ESO architecture?
- `SecretStore` (or `ClusterSecretStore`) defines a backend (AWS SM, SSM, Vault, GCP SM). `ExternalSecret` references a `SecretStore` and a remote key, ESO syncs into a native K8s `Secret` on a refresh interval.

**Q11.2** Auth to AWS Secrets Manager from ESO?
- `SecretStore.spec.provider.aws.auth.jwt.serviceAccountRef` → IRSA / Pod Identity → STS → SM.

**Q11.3** Rotate a secret without restarting pods?
- Use `reloader` (or Stakater Reloader) — annotates Deployments to roll on Secret/ConfigMap change. Or use mounted secrets that the app reads on each request.

---

## 12. EFS / EBS CSI

| | EBS | EFS |
|---|---|---|
| Type | Block | NFSv4 |
| Access | RWO | RWX (multi-AZ) |
| AZ | Single | Regional |
| Cost | $/GB/mo | $/GB/mo (higher) + throughput |
| Latency | Low | Higher |
| Use case | Postgres, Mongo PVC | Shared assets, model files |

**Q12.1** PVC stuck `Pending`. Diagnose.
- Check StorageClass exists and is default; check CSI driver pods running; check IRSA on `ebs-csi-controller-sa`; check `kubectl describe pvc` for events; check zone affinity (EBS) — pod scheduled in AZ where volume can't be created.

---

## 13. Fargate

**Q13.1** When use Fargate over Karpenter nodes?
- Bursty, low pod-density workloads (CronJobs, low-traffic APIs); when you don't want to manage a node IAM role / SSH; PCI / strict isolation. Caveats: no DaemonSets, no privileged, slower pod start (60–90s), per-pod billing rounded up.

**Q13.2** A Fargate pod's SG?
- Comes from the Fargate profile's pod execution role + cluster SG; no per-pod SG (you can use SG-for-pods on EC2 nodes only).

---

## 14. Terraform / Terragrunt

**Q14.1** Why Terragrunt?
- DRY backend config, DRY provider blocks, dependency graph between modules, `run-all` for multi-stack pipelines, `before_hook` for `terraform fmt`.

**Q14.2** State locking — what backend?
- S3 + DynamoDB; the lock is a DynamoDB item with `LockID = <bucket>/<key>-md5`.

**Q14.3** Drift between TF state and reality — strategies?
- `terraform plan` regularly in CI (drift detection); for one-off drift, `terraform import` + state-mv; for resources that *must* be mutable out-of-band (e.g. SG rules added by emergency hotfix), use `lifecycle.ignore_changes`.

**Q14.4** Why is `terragrunt run-all apply` dangerous in prod?
- Parallel execution, no atomicity across modules; partial failure leaves you mid-deploy. Use `--terragrunt-include-dir` or run serially in CI with explicit ordering.

---

## 15. CI/CD

**Q15.1** GitHub Actions OIDC to AWS — show the trust policy:
```json
{
  "Effect": "Allow",
  "Principal": { "Federated": "arn:aws:iam::ACCT:oidc-provider/token.actions.githubusercontent.com" },
  "Action": "sts:AssumeRoleWithWebIdentity",
  "Condition": {
    "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
    "StringLike":   { "token.actions.githubusercontent.com:sub": "repo:org/repo:ref:refs/heads/main" }
  }
}
```
**Common bug:** wildcard on `sub` — any branch / any fork can assume the role.

**Q15.2** CloudBees pipeline talking to EKS — how does it authenticate?
- Either via static IAM user (anti-pattern), via assume-role from a CloudBees IAM role (preferred — uses STS), or via OIDC if CloudBees supports it.

---

## 16. TLS / DNS

**Q16.1** ACM cert + ALB + Route 53 — flow.
- Request public ACM cert → DNS validation CNAME in Route 53 → ACM auto-validates → attach cert ARN to ALB listener → external-dns / manual A-record (alias) `app.example.com → ALB DNS`.

**Q16.2** cert-manager vs ACM?
- cert-manager issues + rotates inside the cluster (Let's Encrypt, Vault, ACM Private CA). Use cert-manager when certs are consumed by pods (mTLS) or by NLB (ACM only integrates with ALB/NLB/CloudFront); use ACM when termination is at the LB.

---

## 17. Cluster lifecycle

**Q17.1** EKS upgrade — order of operations.
- 1. Read upgrade guide for n→n+1; 2. Upgrade control plane (API call); 3. Upgrade core addons (vpc-cni, coredns, kube-proxy) to versions matching new k8s version; 4. Upgrade managed node groups (or rotate Karpenter nodes by bumping AMI hash → expire); 5. Smoke test; 6. Drift-check ArgoCD apps.

**Q17.2** Decommission a cluster safely.
- 1. Move workloads off (ArgoCD point at new cluster); 2. Drain DNS (lower TTL → repoint A-record); 3. Snapshot PVs (EBS snapshots, EFS backup); 4. Delete K8s resources via ArgoCD; 5. `terraform destroy` of node groups, then EKS, then VPC; 6. Remove access entries / aws-auth; 7. Archive logs.

---

## 18. Failure / recovery

**Q18.1** "All pods in `kube-system` are CrashLooping after upgrade." Walk through.
- Likely vpc-cni / coredns / kube-proxy version mismatch with new k8s version → roll back addon, then upgrade again with correct version. Check `kubectl logs aws-node -n kube-system`.

**Q18.2** EKS API endpoint suddenly returns 401 for everyone.
- Likely `aws-auth` ConfigMap was overwritten with malformed YAML or missing `system:nodes` mapping → nodes go NotReady, then API still works for IAM principals with access entries but not for kubeconfig users mapped via aws-auth. Recover via cluster creator IAM role (always has access).

**Q18.3** ArgoCD shows "OutOfSync" but `kubectl diff` shows no diff.
- Likely a mutating webhook (e.g. Istio sidecar injector) is adding fields ArgoCD doesn't expect. Use `ignoreDifferences` with JSON path or `respectIgnoreDifferences=true`.

---

# Part 2 — Extended Bank (FAANG bar-raiser depth)

> Sections 19–32 add depth interviewers go for after candidates pass the basics.
> Format unchanged: **Q** → **Strong answer** → **Follow-up**.

---

## 19. Linux internals an SRE must know

**Q19.1** What does the Linux OOM killer do, and how do you protect a process from it?
- Kernel watches per-cgroup (and global) memory pressure; when limits are breached, walks tasks, scores them via `oom_score = oom_score_adj + heuristics(rss, runtime, root)`, kills the highest. Protect by setting `oom_score_adj = -1000` (immune; only for PID 1 / critical agents) or by giving the cgroup a higher memory limit / reservation. In K8s, set Pod `priorityClassName: system-cluster-critical` and ensure `requests = limits` (Guaranteed QoS) so it's last to be evicted.

**Q19.2** Walk through what happens when a process opens a file.
- `open(2)` syscall → VFS layer → resolves path through dcache → checks DAC permissions → calls fs-specific `inode_operations->lookup` → allocates `struct file` → returns smallest free fd from per-process fd table. The `struct file` holds offset, flags, and points to a kernel-side `inode`. `close(2)` decrements refcount; reaching zero releases the entry.

**Q19.3** Difference between `fork()` and `clone()`?
- `fork(2)` is shorthand for `clone(SIGCHLD)` with full COW of address space. `clone(2)` lets you choose what to share: `CLONE_VM` (memory), `CLONE_FILES` (fd table), `CLONE_NEWNET`/`CLONE_NEWPID`/`CLONE_NEWUTS` (namespaces — this is what containers use). Threads = `clone(CLONE_VM | CLONE_FILES | CLONE_SIGHAND | ...)`.

**Q19.4** What's a cgroup, and what's the difference between v1 and v2?
- cgroup = kernel mechanism to apply resource limits + accounting to a set of PIDs. v1: per-controller hierarchies (cpu, memory, blkio each in their own tree) — flexible but inconsistent. v2: unified single hierarchy, proper IO/memory/CPU coordination, PSI metrics, `memory.high` (soft throttle vs hard kill). EKS AL2023 / Bottlerocket use v2.

**Q19.5** A pod's `cpu: 500m` limit — what does the kernel actually enforce?
- CFS bandwidth control: `cpu.cfs_period_us=100000` (100 ms) + `cpu.cfs_quota_us=50000` → up to 50 ms of CPU time per 100 ms window per cgroup. If exceeded, **throttling** (not killing) — visible as `nr_throttled` and `throttled_time` in `cpu.stat`. Common bug: bursty workload on tight quota → p99 latency spikes from throttling; fix by raising quota or removing CPU limit (controversial — see Q19.6).

**Q19.6** Should you set CPU limits in K8s?
- Two camps. Pro-limits: predictable, prevents noisy neighbour. Anti-limits (gaining ground): CFS throttling causes latency spikes; better to set requests + use Guaranteed QoS for critical pods + rely on node-level capacity planning. Tim Hockin (K8s lead) leans anti-limits; Google SRE book agrees for latency-sensitive services.

**Q19.7** TCP three-way handshake — what state is each side in?
- Client: `CLOSED → SYN_SENT → ESTABLISHED`. Server: `LISTEN → SYN_RCVD → ESTABLISHED`. SYN flood DoS exploits the half-open `SYN_RCVD` queue; mitigated with SYN cookies (`net.ipv4.tcp_syncookies=1`).

**Q19.8** What's `TIME_WAIT` and why does it matter at scale?
- After active close, the closer enters `TIME_WAIT` for 2×MSL (60s on Linux) to absorb stragglers. Burns an ephemeral port per connection. With high-RPS short-lived connections (e.g. Envoy → upstream) you exhaust ports. Fix: connection pooling, `SO_REUSEPORT`, `net.ipv4.tcp_tw_reuse=1` (safe for client side), bigger `net.ipv4.ip_local_port_range`.

**Q19.9** `strace` vs `ltrace` vs `bpftrace`?
- `strace`: syscalls (kernel boundary). `ltrace`: library calls (libc). `bpftrace`: eBPF — programmable, low-overhead, traces both kernel + userland. Modern SRE: prefer `bpftrace` / `bcc` for production (strace adds 10–100× overhead via ptrace).

**Q19.10** Walk through `ss -s` output meaning.
- Summary of socket usage: `Total`, `TCP estab/closed/orphaned/timewait`, transports (`TCP/UDP/RAW/FRAG`). High `orphaned` = app not closing connections; high `timewait` = see Q19.8; rising `closed` queue = backlog overflow.

---

## 20. Kubernetes primitives interviewers love

**Q20.1** What's a `Job` vs `CronJob` vs `Deployment` — and when's each wrong?
- `Deployment`: long-running replicas, rolling update. Wrong for batch workloads (no completion semantics; restartPolicy: Always).
- `Job`: run-to-completion; `parallelism`, `completions`, `backoffLimit`, `activeDeadlineSeconds`. Wrong for streaming.
- `CronJob`: schedule wrapping `Job`. Wrong for sub-minute frequency (use a sidecar or work queue).

**Q20.2** PDB vs PriorityClass vs PreemptionPolicy.
- **PDB** (`PodDisruptionBudget`): protects against *voluntary* disruption (drain, upgrade) — `minAvailable` or `maxUnavailable`. Doesn't help on node hardware failure.
- **PriorityClass**: scheduling priority + (with `globalDefault`) default priority. Higher priority pod can preempt lower.
- **PreemptionPolicy**: `PreemptLowerPriority` (default) vs `Never` (queue-only).

**Q20.3** `topologySpreadConstraints` vs `podAntiAffinity` — which wins?
- Both can express "spread my pods." TSC is newer, more declarative, supports `whenUnsatisfiable: DoNotSchedule | ScheduleAnyway`, integrates with `topologyKey: topology.kubernetes.io/zone`. PodAntiAffinity is older, expresses pairs ("don't co-locate with X"). Modern best practice: TSC for spread, anti-affinity for "never together with this label."

**Q20.4** Readiness vs Liveness vs Startup probe — when does each fire and what does failure do?

| Probe | When | On fail |
|---|---|---|
| Startup | At boot until first success; suspends others | restart container |
| Liveness | Continuous after startup | restart container |
| Readiness | Continuous | remove from Service Endpoints (no restart) |

Common bug: liveness probe misconfigured → constant restarts during slow GC. Startup probe was added precisely to handle slow-starting JVMs.

**Q20.5** What's a `headless` Service?
- `clusterIP: None`. No virtual IP; DNS returns A records for each Pod IP. Used by StatefulSets for stable per-pod DNS (`pod-0.svc.ns.svc.cluster.local`) and for clients that want to do their own load balancing (gRPC, Cassandra).

**Q20.6** ServiceAccount, Role, ClusterRole, RoleBinding, ClusterRoleBinding — diagram in 30 seconds.
- `SA` is the identity, lives in a namespace.
- `Role` = permissions in one namespace; `ClusterRole` = cluster-wide (or reusable across namespaces).
- `RoleBinding` binds a (Cluster)Role to subjects (SA, user, group) in **one namespace**; `ClusterRoleBinding` does it cluster-wide.
- Common pattern: ClusterRole `view` + RoleBinding per namespace = portable read-only role.

**Q20.7** What's an admission webhook chain?
- API server → mutating admission webhooks (in order, can modify object) → schema validation → validating admission webhooks (no modify, only allow/deny) → persist to etcd. Failure modes: webhook timeout, webhook unavailable + `failurePolicy: Fail` → all writes blocked. Always set `failurePolicy: Ignore` on non-security webhooks.

**Q20.8** Why is `kubectl apply` not the same as `kubectl replace`?
- `apply` does three-way merge: last-applied annotation + live state + new manifest → preserves fields managed by other controllers (HPA's replicas). `replace` overwrites the entire object → wipes those fields. Use `apply` always; `replace` only for emergency.

**Q20.9** Server-Side Apply (SSA) — what problem does it solve?
- Three-way merge breaks down with multiple controllers managing different fields of the same object. SSA: each "field manager" claims ownership of fields; conflicts are detected (`Conflict: field is managed by another applier`). ArgoCD has a `ServerSideApply=true` syncOption that uses this.

**Q20.10** Difference between `kubectl rollout restart deploy/x` and editing the Deployment?
- `rollout restart` adds/updates `kubectl.kubernetes.io/restartedAt` annotation on the pod template → triggers a rollout (because pod template changed) without changing any spec. Cleanest way to roll without editing.

**Q20.11** What's a finalizer and when does it bite you?
- String list on `metadata.finalizers`. Object can't be GC'd until all finalizers are removed. Common bug: namespace stuck "Terminating" forever because a finalizer points to a controller that no longer exists. Fix: `kubectl get ns x -o json | jq '.spec.finalizers=[]' | kubectl replace --raw "/api/v1/namespaces/x/finalize" -f -`.

**Q20.12** What's the API server's request flow for `kubectl get pods -w`?
- `GET /api/v1/pods?watch=true` → API server opens long-poll → reads from etcd watch cache (in-memory) → streams `ADDED`/`MODIFIED`/`DELETED` events. Etcd is **not** queried on each pod change (that would melt etcd) — the watch cache fans out.

---

## 21. Observability & SLOs

**Q21.1** Define SLI / SLO / SLA / Error Budget.
- **SLI**: a metric (e.g. `successful_requests / total_requests`).
- **SLO**: an internal target on the SLI (`99.9% over 30d`).
- **SLA**: external contract with refund/credit (looser than SLO).
- **Error budget**: `1 − SLO` — the allowed unreliability (e.g. 0.1% × 30d = 43 min/month). Burned faster than budget → freeze releases.

**Q21.2** Multi-window multi-burn-rate alerting — why?
- Naive "alert when SLO violated for 1h" either fires too late (slow burn) or too noisy (fast burn). Multi-burn: alert if `1h burn ≥ 14.4 × budget` OR `5min burn ≥ 36 × budget` — catches both fast incidents and slow leaks. Google SRE book chapter 5.

**Q21.3** RED vs USE method.
- **RED** (services): Rate, Errors, Duration. For request-driven systems.
- **USE** (resources): Utilisation, Saturation, Errors. For nodes/disks/CPUs.
- A complete dashboard has both.

**Q21.4** Metrics vs logs vs traces — what do you reach for first?
- Metrics for "is something wrong?" (cheap, aggregate). Logs for "what exactly happened in this one request?" (expensive, detailed). Traces for "where in the call graph did time go?" (correlates across services). Mature stack ties them via shared trace_id.

**Q21.5** Why is high-cardinality bad in Prometheus?
- Each unique label combination is a separate time series. `userId` as a label → millions of series → memory blow-up + scrape failures + slow queries. Rule: ≤ 10 labels, < 100 distinct values per label, no unbounded values.

**Q21.6** Recording rule vs alerting rule?
- Recording rule precomputes an expensive expression every interval and stores it as a new series — used for dashboards / nested alerts.
- Alerting rule evaluates an expression and fires `ALERTS{}` series + sends to Alertmanager.

**Q21.7** OpenTelemetry — what are spans, traces, baggage?
- **Span**: one operation with start/end time + attributes + status; child of a parent span.
- **Trace**: tree of spans sharing a `trace_id`.
- **Baggage**: key/value pairs propagated alongside trace context (e.g. `tenant_id=acme`) — careful, baggage isn't free (header bytes on every hop).

**Q21.8** Sampling strategies for traces?
- **Head-based** (decide at root): cheap, can miss interesting tail. **Tail-based** (decide after full trace assembled): captures errors/slow traces but needs a trace collector with buffer (e.g. OTel Collector tail sampler). **Probabilistic** for baseline; tail for outliers.

**Q21.9** What's a histogram vs summary in Prometheus?
- **Histogram**: pre-defined buckets + counters → server-side aggregable percentiles via `histogram_quantile()`. Use this.
- **Summary**: client computes percentiles → not aggregable across replicas. Avoid unless you have a single producer.

**Q21.10** Prometheus federation vs remote_write — when?
- **Federation**: parent Prometheus scrapes `/federate` from leaves → simple but doesn't scale past a few leaves; pull-only.
- **remote_write**: leaves push to long-term store (Mimir, Thanos, VictoriaMetrics, AMP) → real horizontal scale. Modern multi-cluster: remote_write to a central store + Grafana queries that store.

---

## 22. Incident response

**Q22.1** Define MTTD, MTTR, MTBF.
- **MTTD** (mean time to detect): page → human ack. Driven by alerting quality.
- **MTTR** (mean time to recover): page → service back to normal.
- **MTBF** (mean time between failures): inverse of incident rate. SLO targets.

**Q22.2** Walk me through the first 10 minutes of a SEV-1 page.
1. Acknowledge page; declare incident in chat; assign IC, comms lead, SME.
2. Open the runbook for the alert. Capture: scope (which service / region / customer), magnitude (% errors), trend (improving/worse).
3. Mitigate first, RCA later: disable the deploy, traffic-shift away from bad region, scale up, roll back.
4. Comms: status page within 5 min; internal stakeholders.
5. When stable, schedule blameless RCA; assign action items.

**Q22.3** What's a "blast radius" and how do you reduce it architecturally?
- The set of users / services affected by a single failure. Reduce via cell-based architecture (independent shards), regional isolation, circuit breakers, bulkheads (separate thread pools per dependency), feature flags for kill switches.

**Q22.4** A rollback fails — your release is broken **and** your prior release is broken. What now?
- Stop the bleeding: traffic-shift to a region/cell that still works; scale that to absorb load. If no good cell, freeze writes (read-only mode) to prevent data corruption. Identify the smallest cherry-pick fix (no full rebuild). Communicate publicly. After: post-mortem on why rollback wasn't tested.

**Q22.5** Blameless post-mortem — what does "blameless" actually mean?
- Names of people are facts in a timeline, not assignment of blame. Focus on system / process failures: "the deploy tool let an unreviewed change through" not "X pushed bad code." Action items target systems, not training. Reference: Etsy's blameless post-mortem culture.

**Q22.6** What's a "runbook" — and what makes one useful?
- A step-by-step recovery doc keyed off a specific alert. Useful = (1) starts with mitigation, not RCA; (2) every step copy-pasteable; (3) decision tree for branches; (4) tested in a game day in the last quarter.

**Q22.7** Game day vs chaos engineering vs DiRT?
- **Game day**: humans simulate an incident, run runbooks. Tests process.
- **Chaos engineering** (Netflix): inject real failures (kill nodes, latency) in prod-like envs to find weaknesses. Tests system.
- **DiRT** (Google Disaster Recovery Test): full-region simulated failure across the org. Tests both + dependencies.

**Q22.8** A noisy alert wakes you up nightly for 2 weeks. What do you do?
- Two questions: is it a real problem, or noise? If noise: tune threshold, add hysteresis, longer evaluation window, or delete the alert (if the underlying SLO is met). If real but not actionable at 3 AM: downgrade to ticket. Track alert quality with `paged_minutes / actionable_paged_minutes`.

---

## 23. Scalability & performance

**Q23.1** Vertical vs horizontal scaling — when each?
- **Vertical** (bigger nodes): simple, no app change, but ceiling and blast radius (one big node fails = bigger impact). Good for stateful (DB).
- **Horizontal** (more nodes): scales beyond single node, fault-isolated. Needs stateless app or sticky session / sharding.

**Q23.2** What's amplification and why does it matter?
- Read/write amplification: 1 user request triggers N downstream calls/IO. A 10× amplification turns 1k RPS user load into 10k RPS DB load. Find via tracing; reduce via batching, caching, denormalisation.

**Q23.3** Caching strategies — name 4 and a tradeoff for each.
- **Cache-aside**: app reads cache, falls back to DB, writes to cache. Simple; thundering herd on miss.
- **Read-through**: cache fronts DB, fetches on miss itself. Cleaner; cache must know schema.
- **Write-through**: write to cache + DB synchronously. Strong consistency; slow writes.
- **Write-back**: write to cache, async to DB. Fast; data loss on cache crash.

**Q23.4** What's a thundering herd and how do you stop it?
- Cache miss for a hot key → 1000 concurrent requests all hit the DB. Mitigations: request coalescing (single-flight), early refresh ("probabilistic early expiration"), background refresh, in-process locks per key, jittered TTLs.

**Q23.5** When does latency dominate vs throughput?
- Latency dominates user-facing systems (page load, API response). Throughput dominates pipelines (analytics, ETL). Improving one often hurts the other (batching = better throughput, worse latency). Know which you're optimising.

**Q23.6** What's tail latency and why is p99 not enough?
- Mean / p50 hide the bad cases. p99 = 1 in 100 requests. p99.9 = 1 in 1000. For systems with fan-out (1 user request → 10 backend calls), p99 of backend = ~10% of user requests slow → user-perceived p99 is much worse. "The Tail at Scale" (Dean & Barroso 2013).

**Q23.7** Backpressure — define and give an example.
- Downstream signals upstream to slow down. TCP does it (window). HTTP does it via 429 + `Retry-After`. Kafka does it via consumer lag. Without it, queues grow unboundedly until OOM. Anti-pattern: dropping messages silently.

**Q23.8** Little's Law — state it and why it matters.
- L = λW (concurrent items in system = arrival rate × time in system). Implication: if arrival rate stays the same and service time doubles, concurrency doubles. Tells you max concurrency you need to size for given RPS and p99 latency.

**Q23.9** What does a load shedder do, where does it sit?
- Protects the system from overload by dropping low-priority requests early. Sits at the edge (LB, API gateway) or in-process (Envoy admission control). Decisions based on CPU / queue depth / dependency latency. Better than crashing.

**Q23.10** Token-bucket vs leaky-bucket rate limiter?
- **Leaky bucket**: requests drained at constant rate; smooths bursts. Good for outbound to a strict-rate API.
- **Token bucket**: tokens added at constant rate, request consumes tokens; allows bursts up to bucket size. Good for user-facing rate limits.

---

## 24. AWS services beyond EKS

**Q24.1** S3 strong vs eventual consistency — current state.
- Since Dec 2020 S3 has **strong read-after-write consistency** for all operations (PUT, DELETE, LIST). No more "wait a bit after write." Older interview prep that says "eventual" is outdated.

**Q24.2** S3 storage classes — pick for: 1y archive logs / hot website / 90d retention.
- 1y archive: **Glacier Deep Archive** (~$0.00099/GB).
- Hot website: **S3 Standard** (or **S3 Express One Zone** for latency-sensitive < 10 ms).
- 90d retention: **S3 Standard-IA** (Infrequent Access; minimum 30d billed, retrieval fee).

**Q24.3** DynamoDB — explain partition key, sort key, GSI, LSI.
- **PK**: hash → distributes across partitions; all items with same PK live together.
- **SK**: range → ordered within a PK; enables `BETWEEN`, `BEGINS_WITH`.
- **LSI**: alternate sort key on same PK; created at table-creation, shares partition's 10GB limit.
- **GSI**: alternate PK + SK; eventual consistency, separate throughput, can be added anytime.

**Q24.4** Why does a hot DynamoDB partition throttle even though table capacity isn't exhausted?
- Capacity is divided across partitions. One PK getting 80% of traffic exceeds the partition's share → throttle. Mitigate: write sharding (suffix `-1..-N` to PK), adaptive capacity (mostly automatic now), or DAX cache.

**Q24.5** Aurora vs RDS — pick one and why.
- **Aurora**: storage decoupled from compute, 6-way replication across 3 AZs, faster failover, read replicas share storage (no replication lag). Pay more per hour.
- **RDS** (Postgres/MySQL): traditional, EBS-backed, slower failover, replicas via stream replication. Cheaper.
- For new high-traffic OLTP: Aurora.

**Q24.6** SQS vs SNS vs EventBridge — when each.
- **SQS**: durable point-to-point queue; one consumer group; FIFO option.
- **SNS**: pub/sub fan-out to many subscribers (SQS, Lambda, HTTP).
- **EventBridge**: event bus with rich filtering, schema registry, partner sources. Use for cross-service event-driven architectures.
- Common pattern: SNS → multiple SQS queues (fan-out + per-consumer durability).

**Q24.7** Lambda cold start — what's the breakdown and how do you minimise?
- Cold start = init phase: download code, init runtime (~100–500 ms), run init code (your imports / global state). Minimise: smaller package (tree-shake, layers), provisioned concurrency (always-warm pool), keep init lean (lazy import), choose ARM Graviton + smaller runtime.

**Q24.8** KMS — symmetric vs asymmetric, envelope encryption.
- **Symmetric** (AES-256): cheap, fast; default. **Asymmetric** (RSA, ECC): for signing or encryption-without-shared-secret.
- **Envelope encryption**: data encrypted with a Data Encryption Key (DEK); DEK encrypted with KMS Customer Master Key (CMK). DEK shipped alongside ciphertext. Why: KMS is rate-limited and slow; envelope keeps KMS out of the data path.

**Q24.9** VPC Endpoint Gateway vs Interface — pick for: S3, Secrets Manager, ECR.
- S3 / DynamoDB → **Gateway endpoint** (free, route-table-based).
- Secrets Manager / ECR / STS → **Interface endpoint** (PrivateLink, ENI in subnet, $/hour). Always enable **private DNS** so SDKs route automatically.

**Q24.10** ELB pre-warm — still a thing?
- Mostly historical. ALB/NLB auto-scale capacity but have a ramp-up time (~minutes) under sudden load. For predictable traffic spikes (Black Friday, product launch), open AWS Support case for pre-warming. NLB scales faster than ALB.

**Q24.11** Route 53 routing policies — name 5.
- **Simple**, **Weighted** (A/B), **Latency** (closest region), **Failover** (active/passive), **Geolocation**, **Geoproximity** (Traffic Flow), **Multi-value answer** (poor man's LB).

**Q24.12** What's an SCP and how does it differ from an IAM policy?
- **SCP** (Service Control Policy): Org-level guardrail; defines max permissions for accounts in an OU. **Cannot grant** permissions, only restrict. IAM policy: grants within an account. Effective permission = intersection of IAM ∪ resource-policy ∪ session-policy ∪ permission-boundary, capped by SCP.

**Q24.13** Cross-account access patterns — pick the safest.
- **AssumeRole** with trust policy (account A grants account B permission to assume role X). External ID for confused-deputy protection if a third party assumes on your behalf. Avoid: long-lived IAM users in another account, sharing secrets.

---

## 25. Container internals

**Q25.1** What are the 7 Linux namespaces?
- `pid`, `net`, `mnt`, `uts`, `ipc`, `user`, `cgroup`. (Plus newer `time` ns since 5.6.) A container = process(es) sharing a set of these.

**Q25.2** What's a container image — concretely?
- Tarball of layers (each layer = filesystem diff) + a JSON manifest + a config blob (env, cmd, labels). Stored in OCI registry. `docker pull` walks layers, untars in order, applies overlay. Layers are immutable + content-addressed (SHA256) — same layer reused across images.

**Q25.3** Why is `latest` tag dangerous?
- Mutable. Two pulls a day apart can return different images → reproducibility broken, rollback can't be by tag. Always pin to a digest (`@sha256:...`) for prod.

**Q25.4** Init system in containers — why use `tini` / `dumb-init`?
- PID 1 in a container has special responsibility: reap zombies (orphaned children), forward signals. Most app processes don't do this → zombies accumulate, SIGTERM ignored. `tini` is a 200-line PID-1 that does both correctly.

**Q25.5** containerd vs CRI-O vs Docker shim?
- All implement Kubernetes' CRI (Container Runtime Interface).
- **Docker shim** removed in K8s 1.24 (Docker not directly used).
- **containerd** is the most common (extracted from Docker, used by Docker itself, EKS, GKE).
- **CRI-O** is OpenShift's choice — minimalist, k8s-only.

**Q25.6** What's a runtime class and when use it?
- `RuntimeClass` selects a different container runtime per pod (e.g. `gvisor` for sandboxing untrusted code, `kata-containers` for VM-level isolation). Set via `pod.spec.runtimeClassName`.

**Q25.7** rootless containers — how and why?
- User namespace remaps container UID 0 to an unprivileged host UID. Without it, a container escape grants host root. Bottlerocket and modern AL2023 + EKS support; Pod Security Standard `restricted` requires `runAsNonRoot: true`.

**Q25.8** A pod can't write to `/data`, even though the volume is mounted. Diagnose.
- Order: (1) check `mountPath` matches; (2) check `readOnly` flag; (3) check fs perms (`fsGroup`, `runAsUser` vs file owner); (4) for hostPath, host file perms; (5) for EFS, IAM perms on the access point; (6) PSP / Pod Security Standard blocking root.

---

## 26. Multi-tenancy & platform engineering

**Q26.1** Hard vs soft multi-tenancy — define and pick a use case.
- **Soft**: shared cluster + namespace per tenant + RBAC + ResourceQuota + NetworkPolicy. Cheap; risk: shared kernel, escape = bad.
- **Hard**: cluster per tenant, or VM-level isolation (gvisor, kata, EC2 per tenant). Expensive; required for untrusted code (CI/build farms, customer code execution).

**Q26.2** Design tenant isolation in a shared EKS cluster.
- Namespace per tenant + (a) `ResourceQuota` (CPU/mem/PVC/secret count), (b) `LimitRange` (default container limits), (c) `NetworkPolicy` default-deny + allow only same-ns + egress, (d) IRSA per tenant SA (no shared role), (e) PodSecurityStandard `restricted`, (f) admission policy (Kyverno / OPA Gatekeeper) blocking hostPath / hostNetwork / privileged, (g) tenant-aware logging/metrics labels for chargeback.

**Q26.3** What's a `Tenant` CRD pattern?
- Custom controller (Capsule, vcluster, Crossplane) reconciles a `Tenant` resource into namespaces, quotas, role bindings, etc. Lets platform team expose a self-service abstraction; tenant owns one resource.

**Q26.4** Onboard a new team to your platform — first 5 things you set up.
1. AWS account (Org → OU → SCPs applied).
2. ArgoCD ApplicationSet entry (Git repo for tenant).
3. Namespace + ResourceQuota + NetworkPolicy + IRSA roles.
4. CI pipeline template (PR checks, image scanning, signed image).
5. Observability defaults: Prometheus scrape annotation, log shipping label, alerting routing key.

---

## 27. Cost & FinOps

**Q27.1** Three biggest EKS cost drivers and how to reduce each.
1. **Compute**: Spot (50–90% cheaper) + Karpenter consolidation + right-size requests (most clusters request 2× what they use).
2. **Inter-AZ data transfer**: pin chatty pods to same AZ via topology hints / `topologyAwareHints`; cache cross-AZ reads.
3. **NAT Gateway $/GB**: VPC endpoints for S3, ECR, STS, Logs (gateway free, interface < NAT for high volume).

**Q27.2** Spot vs On-Demand vs Savings Plans vs RIs.
- **Spot**: cheapest, can be reclaimed in 2 min. Stateless, fault-tolerant only.
- **On-Demand**: full price, no commit.
- **Savings Plans (Compute)**: commit $/hr for 1 or 3 years; flexible across services + regions.
- **RIs**: instance-type-specific, less flexible. SPs replaced most RI use cases.

**Q27.3** What's a "compute optimizer" and how do you use it?
- AWS Compute Optimizer: ML-driven right-sizing recs for EC2, EBS, Lambda, ASG, ECS. For EKS: enable, look at over-provisioned nodes, apply to Karpenter `NodePool` requirements.

**Q27.4** Cost allocation in shared clusters — how?
- Tag-based: every resource tagged `Team=X`, `CostCenter=Y`. AWS Cost Explorer groups by tag. Inside cluster: Kubecost / OpenCost ingests Prometheus + AWS pricing → per-namespace $/day. Show-back vs charge-back: show-back (visibility) first, charge-back (real billing) once data is trusted.

---

## 28. Security deep-dive

**Q28.1** STRIDE — what's it for and name each letter.
- Threat modelling framework. **S**poofing, **T**ampering, **R**epudiation, **I**nformation disclosure, **D**enial of service, **E**levation of privilege. Walk a system through each lens.

**Q28.2** What's the difference between authn and authz, and where do they live in K8s?
- **AuthN** (who): TLS client cert, bearer token, OIDC, webhook. Configured at API server flags.
- **AuthZ** (what): RBAC, ABAC, webhook, Node authorizer. RBAC is the universal answer.

**Q28.3** Pod Security Standard — name the 3 levels.
- **Privileged** (no restriction), **Baseline** (basic anti-foot-gun: no hostPath, no hostNetwork, etc.), **Restricted** (hardened: runAsNonRoot, drop ALL caps, seccompProfile RuntimeDefault). Enforced via `pod-security.kubernetes.io/<mode>=<level>` namespace label (modes: `enforce`, `audit`, `warn`).

**Q28.4** Image signing — Cosign / Sigstore flow.
- Sign at build time with Cosign → signature stored in registry alongside image (or in separate Rekor transparency log). Admission controller (Kyverno, OPA, Connaisseur) verifies signature against your public key (or Fulcio short-lived cert) before allowing the pod.

**Q28.5** SBOM — what is it and why required now?
- Software Bill of Materials. List every dependency + version + license in an image. SPDX or CycloneDX format. US Executive Order 14028 mandates for federal supply chain. Generated by `syft`, scanned by `grype` / Trivy.

**Q28.6** Secret rotation — design for a Postgres password.
1. Secrets Manager rotation Lambda generates new pwd, updates RDS, writes new version to SM.
2. ESO syncs new K8s Secret (1h refresh).
3. Reloader rolls Deployment.
4. Old pwd kept active for `awsrotate` overlap window (10 min) so in-flight pods finish.
5. RDS revokes old pwd after window.

**Q28.7** Network policy — write one for a 3-tier app.
```yaml
# Tier: web. Allow ingress from ingress-nginx, egress to api.
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: { name: web, namespace: app }
spec:
  podSelector: { matchLabels: { tier: web } }
  policyTypes: [Ingress, Egress]
  ingress:
    - from: [{ namespaceSelector: { matchLabels: { name: ingress-nginx } } }]
      ports: [{ protocol: TCP, port: 8080 }]
  egress:
    - to: [{ podSelector: { matchLabels: { tier: api } } }]
      ports: [{ protocol: TCP, port: 9000 }]
    - to: [{ namespaceSelector: { matchLabels: { name: kube-system } } }]
      ports: [{ protocol: UDP, port: 53 }]   # CoreDNS
```
Default-deny first, allow-list selectively.

**Q28.8** What's a confused deputy attack and how does External ID fix it?
- A privileged service does work on behalf of multiple clients; one client tricks the service into using its privileges against another. AWS example: third-party SaaS assumes a role in your account → another customer guesses your role ARN, gets the SaaS to operate on your account. **External ID** is a shared secret between you and the SaaS, encoded in the trust policy condition; attacker can't supply it.

**Q28.9** IMDSv1 vs v2 — what's the attack and the fix?
- IMDSv1: SSRF in your app → fetches `http://169.254.169.254/latest/meta-data/iam/security-credentials/` → exfil node creds.
- IMDSv2: token-based, requires PUT to get a token first, plus a hop limit (default 1). SSRF via standard HTTP GET fails.
- EKS: enforce `httpTokens: required, httpPutResponseHopLimit: 1` on launch template.

---

## 29. Data & state

**Q29.1** ACID vs BASE.
- **ACID**: Atomicity, Consistency, Isolation, Durability — relational DB defaults.
- **BASE**: Basically Available, Soft state, Eventual consistency — typical of NoSQL / distributed.

**Q29.2** CAP theorem — restate accurately.
- During a network **partition** between replicas, you must choose Consistency or Availability — you can't have both. (When no partition, CAP doesn't apply; you can have CA.) Modern restatement: PACELC adds latency-vs-consistency tradeoff in normal operation.

**Q29.3** Consistency levels in distributed DBs — name 4.
- **Strong / linearizable**, **sequential**, **causal**, **eventual**. DynamoDB offers strong (per-PK) and eventual reads. Cassandra offers tunable per-query (`ONE`, `QUORUM`, `ALL`).

**Q29.4** Two-phase commit — works, doesn't work?
- Works for atomic commit across distributed nodes; doesn't work in face of coordinator failure (blocked indefinitely). Modern alternative: Saga pattern (compensating transactions) for long-running cross-service flows.

**Q29.5** Outbox pattern — what problem does it solve?
- Atomically publish an event when DB write succeeds. Problem: write to DB then publish to Kafka — if publish fails, lost event; if write fails after publish, ghost event. Outbox: write event to an `outbox` table in same DB transaction; a separate poller reads outbox + publishes + marks sent. Atomic.

**Q29.6** Backup strategies — 3-2-1 rule.
- 3 copies, on 2 different media, 1 off-site. For AWS: S3 (3 copies via durability) + cross-region replication + Glacier for off-site.

**Q29.7** RTO vs RPO.
- **RTO** (Recovery Time Objective): how long after disaster until service restored.
- **RPO** (Recovery Point Objective): how much data loss is acceptable (last N minutes).
- Drives backup frequency + DR architecture (warm standby vs pilot light vs multi-region active-active).

---

## 30. Git, releases, change management

**Q30.1** Trunk-based vs GitFlow vs release branches — pick for a SaaS.
- **Trunk-based**: short-lived feature branches → main → CD on every merge. Best for SaaS with small change-sets and feature flags.
- **GitFlow**: long-lived `develop`, `release`, `hotfix` branches. Heavy; bad for CD.
- **Release branches**: cut a branch per release (1.x, 2.x). Necessary for shipped software with multiple supported versions.

**Q30.2** Semantic versioning — what does each part mean and what's the tricky part?
- `MAJOR.MINOR.PATCH`. MAJOR = breaking, MINOR = additive features, PATCH = bug fix. Tricky: every team disagrees on what "breaking" means for an internal API. Be conservative (bump MAJOR if any consumer might break).

**Q30.3** Squash vs rebase vs merge commit?
- **Squash**: clean main history (1 commit per feature); loses fine-grained history. Good for product repos.
- **Rebase**: linear history without merge bubbles; rewrites SHAs (don't on shared branches). Good for personal feature branches before merge.
- **Merge commit**: preserves true history including parallel work. Good for releases / long-running branches.

**Q30.4** A force-push to `main` happened. How do you recover?
- `git reflog` on a clone that has the old SHA → `git push origin <old-sha>:main --force-with-lease` (after disabling protection temporarily). Or restore from a CI runner's checkout. Prevent: enable branch protection (no force push), CODEOWNERS for sensitive paths.

**Q30.5** Canary vs blue-green vs rolling deployment.
- **Rolling**: replace pods N at a time. K8s default. Risk: bad version live for a chunk of users until rollout finishes.
- **Blue-green**: two full envs; switch traffic atomically. Fast rollback; 2× resources during cutover.
- **Canary**: route 1% / 10% / 50% / 100% gradually; compare metrics. Best for risky changes; needs traffic-splitting (Istio, Argo Rollouts, ALB weighted target groups).

**Q30.6** Feature flags — when do they bite you?
- Death by a thousand flags: combinatorial test matrix. Stale flags become permanent forks. Ownership: every flag must have an expiry date and an owner; CI fails if a flag is older than 90 days without renewal.

---

## 31. AWS networking deep-dive

**Q31.1** Walk the lifecycle of a packet from a pod to S3 (via Gateway endpoint).
- Pod → veth → host eth → routed via private subnet route table: `pl-xxxxx (S3 prefix list) → vpce-xxxxx (gateway endpoint)` → S3 backend over AWS backbone → response back. No NAT GW, no IGW.

**Q31.2** Same packet, but to S3 via NAT GW (no endpoint).
- Pod → veth → node eth → private subnet route → `0.0.0.0/0 → nat-xxxxx` → NAT GW (in public subnet) → IGW → public S3 endpoint. $/GB egress + NAT processing $.

**Q31.3** Same packet, but to RDS in another VPC via TGW.
- Pod → veth → node eth → private subnet RT → `<rds-cidr> → tgw-xxxxx` → Transit Gateway → peer VPC's TGW route → RDS subnet → RDS ENI. SGs at both ends must allow.

**Q31.4** What's a VPC peering connection's limitation vs TGW?
- Peering is 1:1, non-transitive (A↔B + B↔C ≠ A↔C). TGW is hub-and-spoke, transitive, supports inspection VPCs, route tables per attachment. Use TGW for >3 VPCs.

**Q31.5** Cross-region traffic — privately?
- TGW peering (cross-region attachment) → encrypted over AWS backbone. Or VPC peering (cross-region, still 1:1). Or PrivateLink across regions for service-to-service.

**Q31.6** What's a prefix list and why does it help with rule limits?
- Named, versioned set of CIDRs. Reference one prefix list in an SG rule instead of N CIDR rules. AWS-managed prefix lists for S3, DynamoDB. Customer-managed for office IPs. Each entry counts toward SG rule limit (60 default) once.

**Q31.7** What's the VPC reachability analyzer for?
- Native AWS tool: pick source ENI + dest ENI + port → it explains exactly why traffic is/isn't reaching, walking SGs, NACLs, route tables, etc. Faster than manual debugging.

---

## 32. Behavioural / leadership rapid-fire

> Each is a 1-line "right shape" answer. Pair with a real STAR (see star-framework.md).

**Q32.1** When you joined a team and found tech debt — first 30 days?
- Listen, ask "what hurts most?" in 1:1s, fix one small visible pain quickly to earn trust, then propose a quarter-roadmap with measurable outcomes.

**Q32.2** A senior engineer disagrees with your design. What do you do?
- Steelman their view, write the trade-off doc, ask for one more reviewer's input, decide as a team. Commit fully whichever way. Keep a "decision log" for posterity.

**Q32.3** Junior engineer keeps making the same mistake?
- Pair with them on the next instance, write a checklist together, add a CI check or a linter that enforces it. Don't escalate first — system over individual.

**Q32.4** Manager pressures you to ship before you think it's ready.
- Quantify the risk (probability × blast radius), offer a smaller-blast-radius version (canary, feature flag, internal launch), agree on what "ready enough" means in numbers.

**Q32.5** You broke prod. What's your immediate action?
- Mitigate first (rollback, kill switch). Comms second (status page + chat). RCA third (blameless). Personal accountability without self-flagellation.

**Q32.6** Asked to do something you think is unethical or unsafe.
- Raise concern in writing, escalate one level, document. If unaddressed, escalate further (skip-level, security, ethics board). Don't execute silently.

**Q32.7** You don't know the answer in an interview.
- "I don't know, but here's how I'd find out / here's a related thing I do know." Honesty > bluffing. Bar-raisers explicitly look for candidates who can scope their unknowns.

---

# Index

- Section 1–18: foundational technical (covered in Part 1 above).
- Section 19: Linux internals (10 Q).
- Section 20: K8s primitives (12 Q).
- Section 21: Observability & SLOs (10 Q).
- Section 22: Incident response (8 Q).
- Section 23: Scalability & perf (10 Q).
- Section 24: AWS beyond EKS (13 Q).
- Section 25: Container internals (8 Q).
- Section 26: Multi-tenancy / platform eng (4 Q).
- Section 27: Cost / FinOps (4 Q).
- Section 28: Security deep-dive (9 Q).
- Section 29: Data & state (7 Q).
- Section 30: Git / releases (6 Q).
- Section 31: AWS networking deep-dive (7 Q).
- Section 32: Behavioural rapid-fire (7 Q).

**Total: ~115 technical Q&A** plus rapid-fire behavioural prompts.
