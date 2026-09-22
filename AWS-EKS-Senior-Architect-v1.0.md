<div align="center">

# 🎯 AWS / EKS Senior Architect

### Interview Prep · **v1.0**

`AWS` `EKS` `Karpenter` `ArgoCD` `Helm` `External Secrets` `IAM` `Networking` `GitOps`

*Single-file study manual for senior-software-developer & solution-architect rounds.*
*Skim the architecture · drill the steps · run the questions.*

**Last updated:** Apr 30, 2026

---

</div>

> [!TIP]
> **How to use this doc** — read top-to-bottom once for the map; on study days, jump via the TOC; the night before, re-read **§9 Day-of checklist** + **App F elevator pitch**.

## 📑 Table of contents

| § | Section | Purpose | ~Read time |
|---|---|---|---|
| 1 | [🏗️  Architecture overview](#1-️-architecture-overview) | Multi-account AWS layout & components | 5 min |
| 2 | [🛠️  End-to-end setup (Phases 1–10)](#2-️-end-to-end-setup-in-order) | Sequenced build instructions | 15 min |
| 3 | [📊  Workflow diagram](#3-workflow-diagram-ascii) | ASCII reference for whiteboarding | 2 min |
| 4 | [⚡  Cheat-sheet: core services](#4-cheat-sheet-core-services--when-to-pick-what) | Quick disambiguation table | 3 min |
| 5 | [❓  Technical Q&A](#5-technical-interview-questions) | 20 drillable questions w/ answers | 20 min |
| 6 | [⭐  STAR behavioural stories](#6-star-behavioural-questions) | 8 ready-to-tell stories | 15 min |
| 7 | [🏢  FAANG-style questions](#7-top-faang-style-questions) | 20 hardest interview prompts | 10 min |
| 8 | [⚠️  Pitfalls & gotchas](#8-️-common-pitfalls--gotchas-to-mention) | Senior-level talking points | 5 min |
| 9 | [📅  Day-of-interview checklist](#9--day-of-interview-checklist) | Morning-of routine | 2 min |
| A | [🧰  Practical commands & manifests](#appendix-a--practical-commands--manifests-whiteboard-ready) | eksctl, Karpenter, ArgoCD, ESO, Helm, kubectl | reference |
| B | [🔬  Deep-dive answers to FAANG questions](#appendix-b--deep-dive-answers-to-selected-faang-questions) | 4 long-form designs | 25 min |
| C | [🛡️  Security baseline](#appendix-c--security-baseline-one-page) | One-page checklist | 3 min |
| D | [🚨  DR / backup playbook](#appendix-d--disaster-recovery--backups-talking-points) | RTO/RPO talking points | 5 min |
| E | [⭐  Bonus STAR stories](#appendix-e--two-more-star-stories-extra-ammo) | 2 backup stories | 5 min |
| F | [🎤  90-second elevator pitch](#appendix-f--recap-30-second-elevator-pitch-for-whats-your-stack) | Memorise this | 2 min |

---

## 1. 🏗️ Architecture overview

> [!NOTE]
> **TL;DR** — Split AWS accounts by purpose (network, security, shared-services, app). One EKS cluster per app account, Karpenter for nodes, ArgoCD for delivery, Pod Identity for AWS auth, External Secrets for secrets.

A typical mid-large enterprise EKS platform is split across **multiple AWS accounts** for blast-radius isolation. The minimum useful split is:

| Account | Purpose | Owns |
|---|---|---|
| **Network account** | Shared connectivity backbone | Transit Gateway, Internet Gateway, NAT Gateways, VPN, Route53 zones, central CIDR block |
| **Security / log archive** | Audit, central logging, IAM Identity Center | CloudTrail org trail, Config aggregator, S3 buckets for logs, KMS keys |
| **Shared services** | Cluster-wide tools | Container registries (ECR), CI/CD runners, monitoring stack, ArgoCD control plane |
| **Application account(s)** | Workloads — one per env (dev / stg / prod) or per business unit | EKS cluster, app workloads, app-specific S3/RDS/EFS, IAM roles for the app |

**Connectivity:** application VPCs attach to a **Transit Gateway** in the network account → TGW routes traffic to other VPCs and to the corporate VPN gateway. Traffic to the public internet exits through NAT Gateways in private subnets, or through the IGW in public subnets for ALBs.

**Compute:** EKS clusters with **Karpenter** for elastic node provisioning (replaces the legacy Cluster Autoscaler + ASG model — Karpenter provisions nodes directly via EC2 fleet API, faster and cheaper).

**Delivery:** Application Helm charts live in Git → **ArgoCD** in each cluster watches the repo and reconciles desired state.

**Identity:** Pods authenticate to AWS via **EKS Pod Identity** (the modern replacement for IRSA — simpler, no OIDC trust policy on every role).

**Secrets:** **External Secrets Operator (ESO)** pulls from AWS Secrets Manager / SSM Parameter Store and projects them as native Kubernetes Secrets.

---

## 2. 🛠️ End-to-end setup, in order

> [!IMPORTANT]
> **The 10-phase build order:** Network → IAM → EKS bootstrap → Karpenter → ArgoCD → External Secrets → EFS → Load Balancers → App onboarding → Day-2 ops.
> **Order matters.** Each phase depends on the previous. Skipping ahead = retrofit pain.

### 📡 Phase 1 — Network foundations (in the network account)

1. **CIDR planning.** Reserve a parent supernet (e.g. `10.0.0.0/8`). Carve non-overlapping `/16`s per VPC. Plan for at least 3 AZs × 2 subnet tiers (public + private) per VPC. Leave room (`/20` per subnet is comfortable).
2. **Create VPCs** in network and each application account. Tag for env / owner.
3. **Transit Gateway** in network account. Share via **Resource Access Manager (RAM)** to application accounts.
4. **Attach** each application VPC to the TGW.
5. **Routes:** in each VPC's private route table → `0.0.0.0/0` to NAT Gateway → TGW route to network account → TGW → IGW for egress (or NAT in network account if doing centralised egress).
6. **Internet Gateway** in network or app account depending on egress model:
   - Decentralised: each app VPC has its own IGW + NAT
   - Centralised egress: only network VPC has IGW + NAT, others route through TGW
7. **VPN:** Site-to-Site VPN attached to TGW (Customer Gateway + VPN Connection). Two tunnels per connection for HA. BGP for dynamic routing.
8. **Security Groups:** start with a baseline that **denies inbound by default** and allows only what's required between tiers. Reference SGs by ID, not CIDR, when both endpoints are in AWS.
9. **Route53:** private hosted zones associated with each VPC for internal `*.internal` names.

### 🔐 Phase 2 — IAM & permissions

1. **Identity Center (SSO)** for human access; one permission set per role (Admin, ReadOnly, Developer, Operator).
2. **IAM roles for EKS cluster:**
   - `eksClusterRole` (used by control plane)
   - `eksNodeInstanceRole` (only if using managed node groups; not needed for Karpenter-only clusters except for the Karpenter controller's node role)
3. **Pod Identity Association** (newer, preferred over IRSA):
   - Install the **EKS Pod Identity Agent** add-on
   - Create an IAM role with the trust policy `pods.eks.amazonaws.com`
   - Associate it: `aws eks create-pod-identity-association --cluster-name X --service-account my-sa --namespace my-ns --role-arn ...`
   - Pod assumes the role automatically; no annotation, no OIDC trust dance.
4. **Cross-account access:** application IAM roles in app accounts trust the network/security accounts via `sts:AssumeRole`. Tag-based ABAC for fine-grained access.
5. **Permission boundaries** on developer-creatable roles — caps the worst case.
6. **KMS keys:** customer-managed, with key policies referencing the EKS cluster's encryption key alias. Rotate annually.

### ☸️ Phase 3 — EKS cluster bootstrap

1. **Create cluster** (Terraform / CDK / eksctl). Use private endpoint with public-via-allowlist if external `kubectl` is needed.
2. **Add-ons** (managed): VPC CNI, kube-proxy, CoreDNS, EKS Pod Identity Agent, EBS CSI driver, EFS CSI driver, AWS Load Balancer Controller.
3. **CoreDNS sizing:** scale replicas to 2 minimum, set HPA for high-throughput clusters. Configure NodeLocal DNS Cache to reduce CoreDNS load.
4. **VPC CNI:** enable **prefix delegation** (`ENABLE_PREFIX_DELEGATION=true`) to massively increase pod-density per node. Enable **WARM_PREFIX_TARGET** so node startup doesn't block on ENI ops.
5. **Logging:** enable cluster control-plane logs → CloudWatch (api, audit, authenticator, controllerManager, scheduler).
6. **kube-system network policies** to restrict pod-to-pod traffic by default once steady-state.

### 🚀 Phase 4 — Karpenter (autoscaling)

1. **Install** via Helm chart from `oci://public.ecr.aws/karpenter/karpenter`.
2. **IAM:** Karpenter controller role (Pod Identity), and a **node IAM role** Karpenter assigns to each provisioned EC2.
3. **Subnet & SG discovery:** tag subnets and security groups with `karpenter.sh/discovery=<cluster>`.
4. **NodePool** (replaces old `Provisioner`):
   ```yaml
   apiVersion: karpenter.sh/v1
   kind: NodePool
   metadata: { name: default }
   spec:
     template:
       spec:
         requirements:
           - key: kubernetes.io/arch
             operator: In
             values: [amd64, arm64]
           - key: karpenter.k8s.aws/instance-category
             operator: In
             values: [c, m, r]
           - key: karpenter.sh/capacity-type
             operator: In
             values: [spot, on-demand]
         nodeClassRef:
           group: karpenter.k8s.aws
           kind: EC2NodeClass
           name: default
     disruption:
       consolidationPolicy: WhenUnderutilized
       expireAfter: 720h
   ```
5. **EC2NodeClass:** AMI family (`AL2023`), block device mappings, user-data, tags.
6. **Mixed Spot + On-Demand:** prefer Spot for stateless workloads with PodDisruptionBudgets; use on-demand for system workloads (Karpenter itself, CoreDNS, ArgoCD).
7. **Consolidation:** Karpenter actively re-packs workloads onto fewer / cheaper nodes — explain this is why it beats Cluster Autoscaler.

### 🔄 Phase 5 — ArgoCD (GitOps)

1. **Install** in `argocd` namespace (Helm chart).
2. **Bootstrap repo structure:**
   ```
   gitops/
     ├─ apps/                    # one folder per app
     │   └─ payments/
     │      ├─ Chart.yaml
     │      └─ values-{dev,stg,prod}.yaml
     ├─ argocd/                  # ArgoCD app definitions
     │   ├─ apps-app.yaml         # the "app of apps"
     │   └─ apps/                 # one Application per workload
     └─ platform/                # cluster add-ons (Karpenter, ESO, ALB ctrl)
   ```
3. **App of Apps:** the root `Application` points at `argocd/apps/` and reconciles every child Application from there.
4. **Sync policy:** `automated: prune: true, selfHeal: true` for non-prod; manual sync for prod (or controlled via PR).
5. **SSO** via Identity Center / OIDC. RBAC by team (`role:team-payments` can sync only `payments-*` apps).
6. **Notifications** (Slack) on sync / health changes.

### 🔑 Phase 6 — External Secrets Operator (secrets)

1. **Install** ESO Helm chart.
2. **Pod Identity** the ESO controller to a role that has `secretsmanager:GetSecretValue` and `ssm:GetParameter` on the relevant resources.
3. **ClusterSecretStore** referencing AWS:
   ```yaml
   apiVersion: external-secrets.io/v1beta1
   kind: ClusterSecretStore
   metadata: { name: aws-secrets }
   spec:
     provider:
       aws:
         service: SecretsManager
         region: us-east-1
         auth:
           jwt:
             serviceAccountRef:
               name: external-secrets
               namespace: external-secrets
   ```
4. **ExternalSecret** in app namespace pulls one or more keys → projects as a Kubernetes `Secret`.
5. **Rotation:** AWS Secrets Manager rotates upstream → ESO refresh interval (e.g. `1h`) projects new value → app reads from secret. Trigger pod rolling restart with **Reloader** controller or via `secretObjects` annotations.

### 💾 Phase 7 — Storage (EFS)

1. **Create EFS** file system (encrypted with CMK).
2. **Mount targets** in each private subnet (one per AZ).
3. **Security group** allowing TCP 2049 from cluster pod CIDR.
4. **EFS CSI driver** (managed add-on).
5. **StorageClass:**
   ```yaml
   apiVersion: storage.k8s.io/v1
   kind: StorageClass
   metadata: { name: efs-sc }
   provisioner: efs.csi.aws.com
   parameters:
     provisioningMode: efs-ap
     fileSystemId: fs-xxxx
     directoryPerms: "700"
   ```
6. **PVC + PV** per workload that needs ReadWriteMany (e.g. shared assets, model cache).

### ⚖️ Phase 8 — Load balancers

| Type | Use case | Layer | Key features |
|---|---|---|---|
| **ALB** | HTTP/HTTPS apps, path/host-based routing, WAF, OIDC | L7 | Listener rules, Target Group health checks, WAF, OIDC auth |
| **NLB** | TCP/UDP, low-latency, static IP, TLS passthrough | L4 | Source-IP preservation, very high throughput |
| **CLB** | Legacy only | L4/L7 | Avoid for new work |

1. **AWS Load Balancer Controller** (managed add-on) reconciles `Ingress` (→ ALB) and `Service type=LoadBalancer` (→ NLB).
2. **Target type:**
   - **IP mode** (recommended for EKS): targets are pod IPs; LB sends traffic directly to pods, bypassing kube-proxy. Required for Fargate.
   - **Instance mode:** targets are nodes; kube-proxy forwards to pods. Higher latency, useful only with NodePort services.
3. **Ingress example:**
   ```yaml
   annotations:
     kubernetes.io/ingress.class: alb
     alb.ingress.kubernetes.io/scheme: internet-facing
     alb.ingress.kubernetes.io/target-type: ip
     alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}]'
     alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:...
     alb.ingress.kubernetes.io/healthcheck-path: /healthz
   ```

### 📦 Phase 9 — Application onboarding (the developer-facing flow)

1. **Repo template:** `app-template/` with Dockerfile, Helm chart skeleton, `.github/workflows/`, `argocd/` overlay.
2. **CI pipeline** (GitHub Actions or GitLab):
   - On push: lint → test → build container → push to ECR → bump tag in `gitops/apps/<app>/values-<env>.yaml` → open PR.
3. **GitOps sync:** PR is reviewed → merge to `main` → ArgoCD detects change within `~3 min` → applies new image tag → rolling update.
4. **Onboarding checklist** new app must pass before going to prod:
   - Liveness + readiness probes
   - Resource requests + limits set
   - PodDisruptionBudget defined
   - HPA or KEDA scaler configured
   - NetworkPolicy explicit (no default `allow-all`)
   - SecurityContext: `runAsNonRoot`, `readOnlyRootFilesystem`, drop all capabilities
   - Logs to stdout/stderr (no files-in-pod)
   - Metrics endpoint scraped by Prometheus
   - Image scanned (Trivy / ECR scan)
   - SBOM published

### 📈 Phase 10 — Observability & Day 2

| Concern | Tool | What it does |
|---|---|---|
| Metrics | **Prometheus + AMP** (or Datadog) | Scrape pods, node-exporter, kube-state-metrics |
| Logs | **Fluent Bit → CloudWatch** (or OpenSearch) | Stream container logs |
| Traces | **OpenTelemetry → AWS X-Ray** (or Jaeger) | Distributed tracing |
| Dashboards | **Grafana** | Service-level dashboards |
| Alerts | **Alertmanager / PagerDuty** | SLO breaches, error budgets |
| Cost | **Kubecost** + AWS Cost Explorer | Per-namespace cost, Karpenter waste |
| Drift | **AWS Config + ArgoCD drift detection** | Detect manual changes |

---

## 3. 📊 Workflow diagram (ASCII)

```
                                         ┌────────────────────────────┐
                                         │      DEVELOPER LAPTOP      │
                                         └──────────────┬─────────────┘
                                                        │ git push
                                                        ▼
                          ┌──────────────────────────────────────────────────┐
                          │                  GITHUB                          │
                          │  app-repo/  →  CI (build, test, push image)      │
                          │            →  PR bumps tag in gitops repo        │
                          │  gitops/   →  source of truth for cluster state  │
                          └──────────────┬───────────────────┬───────────────┘
                                         │                   │
                                         ▼                   ▼
                              ┌────────────────────┐    ┌─────────────────┐
                              │     ECR (image)    │    │ ArgoCD (in EKS) │
                              │   in shared-svcs   │    │  watches gitops │
                              └────────────────────┘    └────────┬────────┘
                                                                 │ apply
                                                                 ▼
┌─────────── NETWORK ACCOUNT ──────────────┐  ┌──────────────── APPLICATION ACCOUNT ────────────────┐
│                                           │  │                                                    │
│   ┌─────────┐  ┌────────┐  ┌──────────┐   │  │   ┌──────────────────────────────────────────┐    │
│   │  IGW    │  │Transit │  │Site-to-  │   │  │   │              EKS CLUSTER                  │    │
│   │  / NAT  │──│ Gateway│──│Site VPN  │   │  │   │  ┌─────────────┐  ┌─────────────────────┐│    │
│   └─────────┘  └────┬───┘  └──────────┘   │  │   │  │  CoreDNS    │  │ AWS LB Controller   ││    │
│                     │                     │  │   │  └─────────────┘  └──────────┬──────────┘│    │
│   ┌─────────┐  ┌────┴────┐                │  │   │  ┌─────────────┐  ┌──────────┴──────────┐│    │
│   │Route53  │  │   RAM   │  share TGW     │  │   │  │ Karpenter   │  │   ArgoCD            ││    │
│   │private  │  │         │  cross-account │  │   │  │ NodePools   │  │   (GitOps engine)   ││    │
│   └─────────┘  └────┬────┘                │  │   │  └──────┬──────┘  └─────────────────────┘│    │
│                     │                     │  │   │         │                                │    │
│                     │                     │  │   │  ┌──────▼──────┐  ┌─────────────────────┐│    │
│                     │ TGW attachment      │──┼──▶│  │  EC2 nodes  │  │ External Secrets Op ││    │
│                     │                     │  │   │  │ (Spot+OD)   │  │  ←── AWS Secrets Mgr││    │
│                     │                     │  │   │  └──────┬──────┘  └─────────────────────┘│    │
│                     │                     │  │   │         │                                │    │
│                     │                     │  │   │   ┌─────▼─────────────────────────┐      │    │
│                     │                     │  │   │   │   APP PODS (with PodIdentity) │      │    │
│                     │                     │  │   │   │   ─ EFS PVC                    │      │    │
│                     │                     │  │   │   │   ─ Service → Target Group     │      │    │
│                     │                     │  │   │   └─────┬─────────────────────────┘      │    │
│                     │                     │  │   └─────────┼──────────────────────────────────│    │
│                     │                     │  │             │                                  │    │
│                     │                     │  │   ┌─────────▼──────────┐  ┌──────────┐        │    │
│                     │                     │  │   │  ALB (L7 ingress)  │  │   NLB    │        │    │
│                     │                     │  │   └─────────┬──────────┘  └─────┬────┘        │    │
│                     │                     │  │             │                   │             │    │
│                     ▼                     │  │             ▼                   ▼             │    │
│             ┌───────────────┐             │  │   ┌──────────────────────────────────┐        │    │
│             │  CORP NETWORK │◀────────────┼──┼───│      INTERNET / Route53          │        │    │
│             │  (VPN clients)│             │  │   └──────────────────────────────────┘        │    │
│             └───────────────┘             │  │                                                │    │
│                                           │  │   ┌──────────────┐  ┌──────────────┐         │    │
│                                           │  │   │  EFS         │  │  RDS / S3    │         │    │
│                                           │  │   │  (RWX vols)  │  │  (per app)   │         │    │
│                                           │  │   └──────────────┘  └──────────────┘         │    │
└───────────────────────────────────────────┘  └────────────────────────────────────────────────┘

                 ↑ central observability ↑
   CloudWatch · OpenSearch · X-Ray · Grafana · Prometheus / AMP · Kubecost
```

---

## 4. ⚡ Cheat-sheet: core services & when to pick what

| Question | Answer |
|---|---|
| ALB vs NLB? | ALB = HTTP(S), needs L7 routing/WAF/OIDC. NLB = TCP/UDP, ultra-low-latency, source-IP preserved. |
| Cluster Autoscaler vs Karpenter? | Karpenter — provisions EC2 directly (faster), supports any instance type without ASGs, does workload-aware consolidation. |
| IRSA vs Pod Identity? | Pod Identity — newer, simpler (no OIDC dance), works across cluster recreates, recommended for new clusters. |
| Helm vs Kustomize? | Helm for templating + packaging + versioning; Kustomize for overlays without templates. Most teams: Helm + ArgoCD. |
| Managed Node Groups vs Karpenter? | Karpenter for production at scale. MNG can stay for system workloads (CoreDNS, Karpenter itself). |
| EBS vs EFS? | EBS = ReadWriteOnce, low-latency, AZ-pinned. EFS = ReadWriteMany, multi-AZ, NFS-like. |
| Secrets Manager vs SSM Parameter Store? | Secrets Manager for rotated secrets (DB creds), Parameter Store for config + non-rotating values (cheaper). |
| Decentralised vs centralised egress? | Centralised (network account NAT) = predictable IPs, single audit point, ~$0.045/GB extra. Decentralised = simpler, lower latency. Most enterprises: centralised. |
| ALB target type IP vs Instance? | IP mode for EKS — direct pod targeting, no kube-proxy double-hop, required for Fargate. |
| ArgoCD ApplicationSet vs App-of-Apps? | ApplicationSet for templated apps (one definition → N apps). App-of-Apps for per-app config. Often combined. |

---

## 5. ❓ Technical interview questions

### 5.1 Networking

**Q1. Walk me through the request path from an external user to a pod in your cluster.**
Route53 (DNS) → ALB (public subnet, ACM cert) → matches Listener rule → Target Group (IP mode, health-checked pod IPs) → pod (in private subnet, IP from VPC CNI) → kube-proxy is bypassed because target type is IP. ALB Controller maintains the target group from the Service endpoints.

**Q2. How do you size CIDR blocks for EKS?**
EKS pods consume IPs from the VPC. Without prefix delegation, each ENI on a node holds ~28 secondary IPs; large nodes can run out fast. Either: (a) enable VPC CNI prefix delegation (each ENI carries a `/28` prefix → ~16× capacity); (b) carve a dedicated `/16` per cluster; (c) use **secondary CIDR** ranges (`100.64.0.0/10` from RFC 6598) for pods to avoid overlap with the corporate network.

**Q3. Why a Transit Gateway instead of VPC peering?**
Peering is full-mesh O(n²) — unmanageable past ~10 VPCs. TGW is hub-and-spoke, supports multiple route tables for segmentation, and centralises VPN/Direct Connect attachments. ~$0.05/hour per attachment + data charges, but saves ops time at scale.

**Q4. How do you secure the EKS API endpoint?**
Three options: (a) public; (b) public-via-allowlist (CIDR allow-list); (c) **private only** + `kubectl` from a bastion in the VPC or via VPN. For prod, option (c) — paired with `aws-auth` ConfigMap or **EKS access entries** for IAM-based RBAC.

**Q5. NLB with TLS — passthrough or termination?**
Termination at NLB if the workload speaks plain TCP/HTTP behind it (cheaper certs, AWS-managed via ACM). Passthrough if you need end-to-end mTLS or your app does cert pinning. NLB-termination requires TLS listeners with ACM cert.

### 5.2 EKS / Kubernetes

**Q6. How does Pod Identity differ from IRSA?**
IRSA: OIDC trust on every IAM role, role-arn annotation on the SA, and the cluster's OIDC provider must be registered. Breaks if cluster is recreated. Pod Identity: AWS adds an EKS-aware webhook that injects credentials at pod start; trust is `pods.eks.amazonaws.com`; associations are managed via EKS API; no OIDC trust to maintain.

**Q7. CoreDNS bottleneck — how do you fix it?**
Symptoms: DNS lookup latency, `i/o timeout` errors. Fixes: (a) scale CoreDNS replicas (HPA); (b) deploy **NodeLocal DNSCache** as a DaemonSet — each node has a local DNS cache that talks UDP to CoreDNS only on miss; (c) tune `ndots:5` in `dnsConfig` to reduce search-domain expansion; (d) increase CoreDNS UDP buffers.

**Q8. How does VPC CNI prefix delegation work?**
By default each ENI gets N+1 secondary IPs. With `ENABLE_PREFIX_DELEGATION=true`, the CNI requests `/28` prefixes (16 IPs each) from EC2 and assigns them as a single ENI attachment. A `m5.large` jumps from 30 pod-IPs to 110+. `WARM_PREFIX_TARGET=1` keeps one warm prefix so pod startup doesn't wait on EC2 API.

**Q9. How does Karpenter pick an instance type?**
For a pending pod, Karpenter looks at: pod requests, node selectors, taints/tolerations, topology spread, NodePool requirements (architectures, instance categories, capacity types). It computes the cheapest instance(s) that can host the pod **and** other pending pods (bin-packing). Calls EC2 Fleet API directly — no ASG.

**Q10. Walk through a rolling deploy.**
ArgoCD detects new image tag in Git → applies updated Deployment manifest → kube-apiserver writes the new ReplicaSet → kubelet pulls the new image → readiness probe → kube-proxy / ALB target-group health-checks the new pod → traffic shifts → old pod drained per `terminationGracePeriodSeconds`. PodDisruptionBudget caps how many can be down at once.

**Q11. PodDisruptionBudget — what for?**
Bounds **voluntary** disruptions (drains, autoscaler removals, Karpenter consolidations). `minAvailable: 1` guarantees at least one pod survives any drain. Doesn't protect against **involuntary** disruptions (node hardware failure).

**Q12. ConfigMap vs Secret vs External Secret?**
ConfigMap: non-sensitive config, plain etcd. Secret: base64 in etcd (encrypted at rest if you turn on KMS encryption). ExternalSecret: a CRD that creates/updates a Secret from an external store (Secrets Manager / Vault / GCP SM) — gives rotation + audit + central management.

### 5.3 ArgoCD / GitOps

**Q13. Difference between ArgoCD Application and ApplicationSet?**
Application = one deployable unit. ApplicationSet = a generator that templates many Applications (e.g. one per environment, one per region, one per cluster) from a single CRD. Use ApplicationSet to avoid hand-writing 50 Application YAMLs.

**Q14. Sync waves — when?**
Set `argocd.argoproj.io/sync-wave: "-2"` on namespace, `"-1"` on CRDs, `"0"` on workloads. ArgoCD applies in ascending wave order, waiting for each wave's Health=Healthy before the next. Critical when bootstrapping clusters (cert-manager CRDs must exist before the controller can reconcile certs).

**Q15. How do you protect production from a bad sync?**
Three layers: (a) `prune: false` on prod Applications — never delete resources without explicit human action; (b) **sync windows** — only allow syncs Tue–Thu 9–5; (c) **PR-gated promotion** — image tag bump in `gitops/values-prod.yaml` requires PR review, no auto-merge.

### 5.4 IAM / security

**Q16. How do you scope a pod's AWS permissions to "S3 read on one bucket"?**
Create an IAM role with policy `s3:GetObject` on `arn:aws:s3:::my-bucket/*`. Trust policy: `pods.eks.amazonaws.com`. Run `aws eks create-pod-identity-association --cluster X --service-account my-app --namespace prod --role-arn ...`. The pod's SA `my-app` now gets temporary credentials with only those rights.

**Q17. Tenant isolation — namespace vs cluster?**
Namespace + NetworkPolicy + ResourceQuota + RBAC + dedicated NodePool (via taints/tolerations) — this is "soft multi-tenancy", fine for trusted teams. Cluster-per-tenant — required for compliance (PCI, HIPAA), strong tenants, or radically different network postures. Cost: ~$72/mo per cluster control plane × N tenants.

### 5.5 Helm / pipelines

**Q18. Helm hook ordering?**
Helm hooks run in order: `pre-install` → `pre-upgrade` → resources installed → `post-install` → `post-upgrade`. Within a phase, hooks ordered by `helm.sh/hook-weight` (lower runs first). Used for migrations, secret rotation, smoke tests.

**Q19. How do you keep `values.yaml` DRY across 20 microservices?**
Two patterns: (a) **library Helm chart** with shared templates (`_deployment.tpl`, `_service.tpl`) — each app chart's `templates/` is one-liner `{{ include "common.deployment" . }}`. (b) **chart of charts** (umbrella) for tightly-coupled services. Avoid copy-pasting values across charts.

**Q20. CI runs Trivy and finds a CRITICAL CVE — what's your policy?**
Pipeline policy: CRITICAL → fail build, block merge. HIGH → warn + ticket auto-created, gated for prod via SLA (e.g. 14 days). MEDIUM → ticket only. Allow-list with justification + expiry for false positives. Track in a SBOM for compliance.

---

## 6. ⭐ STAR behavioural questions

> [!TIP]
> **How to use these stories:**
> - **S** = context (where, when, scope, stakes)
> - **T** = your specific responsibility
> - **A** = actions **you** took (use "I", not "we")
> - **R** = quantified outcomes (%, $, time)
> - Replace **\<\<placeholder\>\>** with real numbers from your work
> - Practice each aloud — aim for ~2 minutes

### STAR-1: Migrating from Cluster Autoscaler to Karpenter

- **S (Situation):** We had 6 EKS clusters running Cluster Autoscaler with 18 ASGs. Spot interruptions caused noisy alerts; idle nodes lingered for 10+ minutes; new pods waited 4–6 minutes for scale-up. AWS spend: \<\<\$X/mo\>\>.
- **T (Task):** Reduce node-provisioning latency by ≥50% and lower compute spend by 20% within one quarter, without disrupting prod.
- **A (Action):** Drafted an ADR comparing Karpenter vs CA. Got engineering buy-in. Bootstrapped Karpenter in dev, then prod, with one NodePool per workload tier. Tagged subnets/SGs, wrote runbooks for Spot interruption handling, set PDBs on every workload, integrated cost dashboards in Kubecost. Migration was zero-downtime: kept CA running on the old ASGs while Karpenter started provisioning in parallel; cordoned old nodes once new ones absorbed traffic.
- **R (Result):** Pod-pending → ready time dropped from 4–6 min to 30–45 seconds. Idle compute fell 32% (Karpenter consolidation). Spot share rose from 0% to 60% on stateless workloads with no measurable customer impact. Saved ~\<\<\$X\>\> annually. Wrote internal blog post + handed off to the platform team.

### STAR-2: ArgoCD bootstrapping a new region

- **S:** New EKS cluster needed in `eu-west-1` for GDPR-bound traffic. 47 services across 6 teams. Manual reproduction of the existing `us-east-1` cluster would take weeks and drift immediately.
- **T:** Stand up a fully-replicating cluster (same workloads, same configs except region overrides) in 2 weeks, with no manual `kubectl apply`.
- **A:** Designed a GitOps "app-of-apps" pattern parameterised by region. Used ApplicationSet with a list generator iterating over `[us-east-1, eu-west-1]`. Region-specific values lived in `regions/<region>/values.yaml`. Bootstrapped the new cluster by `kubectl apply -f bootstrap/argocd.yaml` — ArgoCD then pulled and reconciled everything else. Cluster add-ons (Karpenter, ESO, ALB controller) were themselves Helm charts under ArgoCD.
- **R:** Cluster fully operational in 9 days. Drift between regions caught automatically by ArgoCD diff. Pattern adopted as the standard for all subsequent clusters; bootstrap time dropped from "weeks" to "afternoon."

### STAR-3: Production outage — DNS

- **S:** 02:14 AM, P1 — checkout service across the company starts failing with `i/o timeout` errors. Revenue impact ~\<\<\$X/min\>\>. CoreDNS pods showing 100% CPU, query latency p99 5s.
- **T:** Restore service ASAP; root-cause and prevent recurrence.
- **A:** Triaged: confirmed only DNS, AWS API healthy. Scaled CoreDNS replicas 2 → 8 (immediate relief), latency dropped. Continued investigating: a deploy 3 hours earlier had pushed a broken init-container that hit DNS in a loop on failure. Rolled back the deploy. Filed two follow-ups: (1) deploy NodeLocal DNSCache cluster-wide (caches on each node, prevents this class of problem), (2) add CoreDNS HPA + alert on query rate.
- **R:** Service restored 12 minutes after page. NodeLocal DNSCache deployed within a week → CoreDNS CPU dropped 70%, latency stable. Wrote postmortem; added "DNS load test" gate to CI for any service with init containers that hit network.

### STAR-4: Onboarding 50 services to a new platform in 8 weeks

- **S:** Mandate to migrate 50 services from a legacy ECS+CloudFormation stack to a new EKS+Helm+ArgoCD platform. Hard deadline: 8 weeks. 12-person platform team, 6 product teams owning the services.
- **T:** Onboard 50 services without a single rollback or extended outage; keep product teams shipping features in parallel.
- **A:** Wrote a "golden path" template repo: Dockerfile + Helm chart + ArgoCD Application + GitHub Actions pipeline + opinionated probes/PDBs/security context. Held a 2-hour onboarding workshop per team. Built a self-service wizard (`./onboard.sh app-name`) that scaffolded a PR. Pair-coded the first migration in each team. Tracked migrations on a board with green/yellow/red status and weekly demos.
- **R:** 47 of 50 migrated by week 7. The remaining 3 (legacy stateful services) needed a custom data-migration plan and shipped week 10. Zero customer-facing outages during cutover. Onboarding time per service: from "days of platform engineer time" to "afternoon for a product engineer."

### STAR-5: Cross-account secrets

- **S:** Compliance audit flagged that the prod cluster (account A) was reading customer PII from a Secrets Manager secret stored in the security account (account S), but the IAM trust was over-broad — any pod in any namespace could assume the role.
- **T:** Lock down so that only the `payments` service in the `prod` namespace could read that secret, with full audit trail.
- **A:** Replaced the broad IRSA role with **EKS Pod Identity** scoped to namespace + service-account. Updated the IAM role's resource policy on the secret in account S to allow only the specific role ARN from account A. Added **resource-based** ABAC with a tag check (`namespace = prod`, `service = payments`). Wrote a Config rule that fails any role in the cluster with a `*` resource. Added a CloudWatch alarm on unusual `GetSecretValue` calls.
- **R:** Audit cleared. Blast radius of a compromised pod went from "all secrets" to "this specific secret." Pattern documented as standard for all future cross-account access.

### STAR-6: Cost reduction

- **S:** Quarterly cloud bill review — EKS workloads were 35% over budget. Investigation showed massive over-provisioning of CPU/memory requests (avg pod requested 2× actual usage).
- **T:** Cut EKS compute spend 25% in 6 weeks, no SLO regressions.
- **A:** Three tracks. (1) **Right-sizing:** deployed VPA in recommendation mode for 2 weeks, then nudged each team with a PR adjusting requests. (2) **Karpenter consolidation:** turned on `consolidationPolicy: WhenUnderutilized` (was off). (3) **Spot adoption:** identified stateless services with PDBs ≥ 2 replicas, migrated them to a Spot NodePool with on-demand fallback. Built a Kubecost dashboard per team to make cost visible.
- **R:** Compute spend dropped 31% in 5 weeks. SLO miss rate unchanged. Spot interruption recovery handled automatically by ALB target deregistration + new pod start. Cost transparency drove ongoing self-service rightsizing.

### STAR-7: Disagreement with a team-mate on architecture

- **S:** Senior peer argued for service mesh (Istio) on a 30-service cluster to handle mTLS, retries, and traffic shifting. I felt the operational burden didn't justify it given our scale.
- **T:** Drive a decision the team can stand behind without political damage.
- **A:** Wrote a one-page comparison: Istio vs ALB+OIDC+Linkerd vs nothing. Quantified: install/upgrade time, control-plane overhead, debug complexity, learning curve, what we actually need (mTLS — yes; advanced traffic shifting — not yet). Proposed Linkerd as the sweet spot. Booked a 30-min meeting to walk through. Asked my peer to argue against my proposal — surfaced two concerns I hadn't considered. Updated the doc, presented to the team. Group voted Linkerd.
- **R:** Linkerd ran for 18 months, mTLS rolled out to 100% of pod-to-pod traffic. Operational burden stayed manageable (1 incident in 18 months vs. ~3/quarter peers reported with Istio). My peer and I shipped two features together after — disagreement didn't damage the relationship because the data drove the call.

### STAR-8: Failed deployment automation

- **S:** Built an "automated promotion from staging to prod" pipeline. After 3 weeks, two prod incidents traced back to silent failures in the promotion: a flaky integration test passed in staging but broke prod.
- **T:** Decide whether to fix or rip out, communicate the decision honestly.
- **A:** Owned the failures publicly in the team retro: it was my design that didn't account for environment skew. Proposed a fix (canary stage + automated rollback on SLO breach) with a 4-week build estimate. Manager pushed back: "do we even need auto-promotion?" Sat with the data — only 6 promotions/week, each took ~10 min manual. Built a 30-min lightweight UI for one-click promotion with safety checks instead of full automation. Kept the automated flow for non-prod.
- **R:** Zero incidents in the next 6 months. Engineers actually preferred the one-click flow (visibility into what's going out) over fully-automated. Lesson: automate when the cost of human-in-the-loop > cost of edge cases. Documented the call in our ADR repo.

---

## 7. 🏢 Top FAANG-style questions

### Design / system questions

**Q1.** Design a multi-tenant Kubernetes platform for 200 internal teams. Walk me through namespace strategy, network isolation, fair-sharing of compute, billing/chargeback, and onboarding self-service.

**Q2.** Your EKS cluster runs out of pod IPs at peak load. What are five different ways to address this, ranked by effort and downtime?

**Q3.** Design a global active-active deployment of a stateful service (e.g. a feature-flag service) across 3 AWS regions. Cover data plane, control plane, failover, and consistency tradeoffs.

**Q4.** A product team wants to deploy a model-serving stack with GPUs that scale to zero when idle. Walk me through the EKS-side design (Karpenter for GPUs, scaling primitives, cold-start handling).

**Q5.** Your CI pipeline takes 47 minutes — too slow. The build is monolithic, runs lint + test + build + Trivy + push + ArgoCD update sequentially. Diagnose and propose a 3-week optimization plan.

**Q6.** Design a zero-downtime migration of a stateful service from EC2+EBS to EKS+EFS. Cover data migration, cutover, rollback, validation.

### Coding / depth questions

**Q7.** Walk me through what happens when you `kubectl apply -f deployment.yaml`. Include kubelet, kube-proxy, scheduler, etcd, container runtime, pause container.

**Q8.** Explain how a TCP packet from a pod on Node A reaches a pod on Node B in EKS with VPC CNI. Include the VXLAN-or-not question, ENI structure, route tables.

**Q9.** A pod is in `CrashLoopBackOff`. List 10 root causes you'd check, in order.

**Q10.** What's in `/etc/resolv.conf` of a pod, and why does each line matter for performance?

**Q11.** Show me how you'd write a Kubernetes admission webhook (logic + config). When would you choose Validating vs Mutating?

**Q12.** Two services with the same DNS name in different namespaces — how does service discovery resolve them, and what's the gotcha when calling cross-namespace?

### Operational / incident response

**Q13.** It's 3 AM. CPU on every node in the prod cluster is at 100%. Walk me through the first 15 minutes.

**Q14.** A deploy went to 1% of users via a feature flag and tripled the error rate. What do you do — and what do you wish you had built before this happened?

**Q15.** Your cloud spend dropped 40% overnight without any deploy — and the on-call pager hasn't fired. Is this good news?

**Q16.** A junior engineer ran `kubectl delete ns production` against the wrong cluster. What do you say to them, and what changes do you make in the next 24 hours?

### Behavioural depth

**Q17.** Tell me about a time you simplified an over-engineered system.
**Q18.** Tell me about a time you pushed back against a senior leader. How did you frame it?
**Q19.** Tell me about your biggest production incident. What did you learn?
**Q20.** What's a technical decision you regret? What would you do differently?

---

## 8. ⚠️ Common pitfalls / "gotchas" to mention

These show seniority — drop them naturally:

- **Karpenter doesn't replace ALL ASGs** — keep one Managed Node Group for the "system" workload (Karpenter itself, CoreDNS, kube-proxy DaemonSet pinned to it). Otherwise: chicken-and-egg if all Karpenter-managed nodes scale to zero.
- **VPC CNI prefix delegation** is ON by default for new clusters since EKS 1.30+. Mention you'd verify and enable for older clusters.
- **NodeLocal DNSCache** — almost always worth it. Reduces CoreDNS load 60–80%. Tiny operational cost.
- **PDBs** must be set on every workload before turning on Karpenter consolidation, or it will yank pods you care about.
- **ALB target type IP** — required for Fargate. Otherwise Instance mode causes unnecessary kube-proxy hops and breaks source-IP visibility.
- **ESO refresh interval default = 1h** — too long for password rotation. Set to 5m for sensitive secrets.
- **ArgoCD `prune: true`** in prod is dangerous: someone removes a Helm chart line, ArgoCD nukes the resource. Default to `prune: false` for prod.
- **`kubectl exec` is logged at the API server** but not at the node. For audit, ship `audit.log` to S3 and alarm on production exec.
- **Spot fleet diversification** — don't let Karpenter pick from 2 instance types. Allow ~10–15 sizes/families so one capacity event doesn't kill the cluster.
- **EKS upgrade path** — control-plane → managed node groups → Karpenter (replace AMIs) → workloads (CRD changes only every few minor versions). Always test in dev for one full upgrade cycle before prod.

---

## 9. 📅 Day-of-interview checklist

> [!IMPORTANT]
> **The night before:** sleep beats cram. Read §9 once, set out your laptop/charger/water, then close the doc.

### ⏰ Timeline

| Before | What |
|---|---|
| **24 h before** | Re-read the architecture diagram (§3), draw it from memory once on paper. |
| **2 h before** | Skim §6 STAR — pick 3 stories you'll lead with. |
| **1 h before** | Open §4 cheat-sheet. Practice one whiteboard answer aloud. |
| **5 min before** | Water · deep breath · open notes app for jotting. You don't need to be perfect, just clear. |

### 🎙️ During the interview

| Situation | Move |
|---|---|
| **Every answer** | **Frame** before solving: *"What I think you're asking is X. The trade-off is between Y and Z. I'd start with…"* |
| **Stuck** | Think aloud. *"I'm not sure between A and B — let me reason about which dimension matters most for your use case."* Senior interviewers reward visible reasoning. |
| **Don't know** | Say so once, briefly, then say what you'd do. *"I haven't run that at scale. Here's how I'd start a small POC."* Faking it loses you the round. |
| **Do know** | Lead with the answer. Detail second. *"Karpenter — because of consolidation. Specifically, it…"* |

### 📞 After

| When | What |
|---|---|
| **End of each round** | Have **3 questions** ready: scope of role, on-call rotation, team's biggest current pain, what success at 6 months looks like. |
| **End of the day** | Send a short thank-you note within 24 h. Reference one specific thing from the conversation. |

---

> **You've got this.** Confidence comes from preparation. You've prepared. Walk in like you've already done the job — because you have.

— *AWS / EKS Senior Architect Interview Prep · v1.0 · Apr 30, 2026*

---

## 🧰 Appendix A — Practical commands & manifests (whiteboard-ready)

### A.1 EKS / cluster

```bash
# Create cluster (eksctl)
eksctl create cluster \
  --name prod-use1 --region us-east-1 \
  --version 1.30 \
  --vpc-private-subnets subnet-aaa,subnet-bbb,subnet-ccc \
  --vpc-public-subnets  subnet-ddd,subnet-eee,subnet-fff \
  --without-nodegroup    # Karpenter will provision

# Update kubeconfig
aws eks update-kubeconfig --name prod-use1 --region us-east-1

# Add managed node group (system workloads only)
eksctl create nodegroup \
  --cluster prod-use1 --name system \
  --instance-types m6i.large --nodes 2 --nodes-min 2 --nodes-max 4 \
  --node-labels role=system --node-taints role=system:NoSchedule
```

### A.2 Pod Identity association

```bash
# Create role with trust on pods.eks.amazonaws.com
cat > trust.json <<EOF
{ "Version": "2012-10-17", "Statement": [{
    "Effect": "Allow",
    "Principal": { "Service": "pods.eks.amazonaws.com" },
    "Action": ["sts:AssumeRole","sts:TagSession"]
}]}
EOF
aws iam create-role --role-name s3-reader-role --assume-role-policy-document file://trust.json
aws iam attach-role-policy --role-name s3-reader-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

# Associate role to Kubernetes service account
aws eks create-pod-identity-association \
  --cluster-name prod-use1 \
  --namespace payments --service-account payments-app \
  --role-arn arn:aws:iam::123456789012:role/s3-reader-role
```

### A.3 Karpenter NodePool (full example)

```yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata: { name: default }
spec:
  template:
    metadata:
      labels: { tier: app }
    spec:
      requirements:
        - { key: kubernetes.io/arch,                  operator: In, values: [amd64] }
        - { key: karpenter.k8s.aws/instance-category, operator: In, values: [c, m, r] }
        - { key: karpenter.k8s.aws/instance-cpu,      operator: In, values: ["2","4","8","16"] }
        - { key: karpenter.k8s.aws/instance-generation, operator: Gt, values: ["3"] }
        - { key: karpenter.sh/capacity-type,           operator: In, values: [spot, on-demand] }
      nodeClassRef:
        group: karpenter.k8s.aws
        kind: EC2NodeClass
        name: default
      taints: []
  limits: { cpu: "1000", memory: 1000Gi }
  disruption:
    consolidationPolicy: WhenUnderutilized
    expireAfter: 720h
---
apiVersion: karpenter.k8s.aws/v1
kind: EC2NodeClass
metadata: { name: default }
spec:
  amiFamily: AL2023
  role: KarpenterNodeRole-prod-use1
  subnetSelectorTerms:
    - tags: { karpenter.sh/discovery: prod-use1 }
  securityGroupSelectorTerms:
    - tags: { karpenter.sh/discovery: prod-use1 }
  blockDeviceMappings:
    - deviceName: /dev/xvda
      ebs: { volumeSize: 100Gi, volumeType: gp3, encrypted: true }
```

### A.4 ArgoCD app-of-apps + ApplicationSet

```yaml
# argocd/root.yaml — the one you kubectl apply once at bootstrap
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata: { name: root, namespace: argocd }
spec:
  project: default
  source:
    repoURL: https://github.com/org/gitops.git
    targetRevision: HEAD
    path: argocd/apps
  destination: { server: https://kubernetes.default.svc, namespace: argocd }
  syncPolicy:
    automated: { prune: true, selfHeal: true }
---
# argocd/apps/payments-set.yaml — generates one Application per env
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata: { name: payments, namespace: argocd }
spec:
  generators:
    - list:
        elements:
          - { env: dev,  cluster: dev-use1 }
          - { env: stg,  cluster: stg-use1 }
          - { env: prod, cluster: prod-use1 }
  template:
    metadata: { name: 'payments-{{env}}' }
    spec:
      project: default
      source:
        repoURL: https://github.com/org/gitops.git
        targetRevision: HEAD
        path: apps/payments
        helm:
          valueFiles: ['values-{{env}}.yaml']
      destination: { server: https://kubernetes.default.svc, namespace: payments }
      syncPolicy:
        automated: { prune: false, selfHeal: true }    # prune only after explicit human action
        syncOptions: [CreateNamespace=true]
```

### A.5 External Secret

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata: { name: payments-db, namespace: payments }
spec:
  refreshInterval: 5m
  secretStoreRef:
    name: aws-secrets
    kind: ClusterSecretStore
  target:
    name: payments-db        # the K8s Secret that ESO creates
    creationPolicy: Owner
  data:
    - secretKey: DATABASE_URL
      remoteRef:
        key: prod/payments/db        # Secrets Manager secret name
        property: database_url
    - secretKey: API_KEY
      remoteRef:
        key: prod/payments/external-api
```

### A.6 ALB Ingress (IP target)

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: payments
  namespace: payments
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}]'
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:us-east-1:123:certificate/abcd
    alb.ingress.kubernetes.io/healthcheck-path: /healthz
    alb.ingress.kubernetes.io/group.name: shared      # share one ALB across ingresses
spec:
  rules:
    - host: payments.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service: { name: payments, port: { number: 80 } }
```

### A.7 Helm — production-grade Deployment skeleton

```yaml
# templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: {{ .Release.Name }} }
spec:
  replicas: {{ .Values.replicas | default 3 }}
  strategy: { type: RollingUpdate, rollingUpdate: { maxUnavailable: 0, maxSurge: 1 } }
  selector: { matchLabels: { app: {{ .Release.Name }} } }
  template:
    metadata:
      labels: { app: {{ .Release.Name }} }
      annotations: { reloader.stakater.com/auto: "true" }     # restart on Secret/CM change
    spec:
      serviceAccountName: {{ .Release.Name }}
      securityContext: { runAsNonRoot: true, fsGroup: 1000 }
      containers:
        - name: app
          image: "{{ .Values.image.repo }}:{{ .Values.image.tag }}"
          imagePullPolicy: IfNotPresent
          ports: [{ containerPort: 8080 }]
          envFrom:
            - secretRef: { name: {{ .Release.Name }}-db }      # populated by ExternalSecret
          resources:
            requests: { cpu: 100m, memory: 256Mi }
            limits:   { cpu: 1,    memory: 512Mi }
          livenessProbe:
            httpGet:  { path: /healthz, port: 8080 }
            initialDelaySeconds: 15
            periodSeconds: 10
          readinessProbe:
            httpGet: { path: /readyz, port: 8080 }
            periodSeconds: 5
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: [ALL] }
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: { name: {{ .Release.Name }} }
spec:
  minAvailable: 1
  selector: { matchLabels: { app: {{ .Release.Name }} } }
```

### A.8 kubectl debugging cheatsheet

```bash
# What's wrong with my pod?
kubectl describe pod <pod>
kubectl logs <pod> --previous          # logs of the crashed container
kubectl get events --sort-by=.lastTimestamp -n <ns> | tail -20

# Why is my pod pending?
kubectl describe pod <pod> | grep -A5 Events    # scheduler reason

# Network: can my pod reach a service?
kubectl exec -it <pod> -- nslookup my-svc.my-ns.svc.cluster.local
kubectl exec -it <pod> -- curl -v telnet://10.0.0.1:443

# Karpenter — what's it doing?
kubectl get nodepool,ec2nodeclass,nodeclaim -o wide
kubectl logs -n karpenter -l app.kubernetes.io/name=karpenter --tail=200 -f

# ArgoCD — what's out of sync?
argocd app list
argocd app diff <app>
argocd app sync <app> --prune

# Quick "everything in this ns"
kubectl get all,cm,secret,pvc,ingress,sa -n <ns>

# Dry-run a manifest before applying
kubectl apply -f deploy.yaml --dry-run=server -o yaml
```

### A.9 Glossary

| Acronym | Expansion |
|---|---|
| ABAC | Attribute-Based Access Control |
| ACK | AWS Controllers for Kubernetes |
| AMP | Amazon Managed Prometheus |
| ASG | Auto Scaling Group |
| CIDR | Classless Inter-Domain Routing |
| CNI | Container Network Interface |
| CRD | Custom Resource Definition |
| CSI | Container Storage Interface |
| ENI | Elastic Network Interface |
| ESO | External Secrets Operator |
| HPA / VPA | Horizontal / Vertical Pod Autoscaler |
| IRSA | IAM Roles for Service Accounts (legacy) |
| KEDA | Kubernetes Event-Driven Autoscaling |
| OIDC | OpenID Connect |
| PDB | PodDisruptionBudget |
| RAM | Resource Access Manager |
| RBAC | Role-Based Access Control |
| RWX | ReadWriteMany (volume access mode) |
| SBOM | Software Bill of Materials |
| TGW | Transit Gateway |
| WAF | Web Application Firewall |

---

*End of v1.0. Iterate this file as you learn — `git init` it, version your edits, this is a living document.*

---

## 🔬 Appendix B — Deep-dive answers to selected FAANG questions

These are the design questions that take 30-45 minutes in an interview. Practice walking through each one out loud at a whiteboard.

### B.1 — Multi-tenant Kubernetes platform for 200 internal teams

**Frame.** Trade-off: cluster-per-tenant (strongest isolation, ops nightmare) vs single shared cluster with namespace-per-tenant (cheap, security risk). Pick a middle: **clusters by trust tier**, namespaces by team within a tier.

**Tiers (3 clusters, 200 teams divided among them).**
| Tier | Workload type | Tenants per cluster |
|---|---|---|
| Standard | stateless web apps, batch jobs | ~150 teams |
| Sensitive | payment, PII, regulated | ~40 teams |
| Hardware | GPU, large memory, special networking | ~10 teams |

**Inside a shared cluster — five layers of isolation:**
1. **Namespace** per team. RBAC scoped: team owns its namespace, can `get/list` cluster-scoped resources but no `create`.
2. **NetworkPolicy** default-deny ingress; explicit `allow-from-team-X` per cross-team API.
3. **ResourceQuota + LimitRange** per namespace. Caps CPU/mem/storage. Forces senior dev review when team needs >X.
4. **PodSecurityAdmission** at `restricted` level. No host networking, no privileged, no hostPath.
5. **Karpenter NodePool taints** by tier — `tier=sensitive:NoSchedule`. Sensitive workloads tolerate; standard pods can't land on sensitive nodes.

**Self-service onboarding.**
- A `team-onboarding/` Git repo. PR adds `teams/<name>.yaml` with team metadata.
- A controller (operator) reads that and creates: namespace, RBAC bindings, default NetworkPolicies, ResourceQuota, ArgoCD project, Kubecost label, monitoring scrape config, etc.
- Onboarding time: ~5 min from PR-merge to "team can deploy."

**Chargeback.**
- Kubecost (or OpenCost) labels every pod by `team` (enforced via admission webhook).
- Daily cost report emailed per team with pod-level breakdown.
- Showback first 6 months, then hard chargeback.

**Self-service deploy.**
- Each team gets an ArgoCD project + Application generator template (ApplicationSet).
- Image-tag bump = PR to gitops repo = rollout.

**Failure modes addressed:**
- Noisy neighbour CPU steal → Karpenter consolidation + per-namespace LimitRanges.
- Quota exhaustion crashes new pods → alert at 80% quota usage, auto-create capacity-extension PR.
- Cross-team accidental API call → NetworkPolicy default-deny prevents.

### B.2 — Pod IP exhaustion at peak load

**Symptoms.** New pods go `ContainerCreating` → eventually `Failed` with `failed to assign an IP address to container`. VPC CNI logs show `InsufficientFreeAddressesInSubnet`. Karpenter can't provision new nodes either.

**Five fixes, ordered by speed-to-deploy.**

| Speed | Fix | Cost / risk |
|---|---|---|
| **5 min** | Enable VPC CNI **prefix delegation** (`ENABLE_PREFIX_DELEGATION=true`, restart aws-node DaemonSet). Each ENI now carries a `/28` of pod IPs (16 each) → 16× capacity. | Zero downtime. Existing pods unaffected; new pods get prefix-IPs. **Always do this first.** |
| **30 min** | Add a **secondary VPC CIDR** (`100.64.0.0/16` from RFC6598) and a new pod-only subnet per AZ. Update `aws-node` ENIConfig to schedule pods into the new range. | Pods get non-routable-from-corp IPs (good for isolation, may break some debug paths). |
| **2 h** | Move to **larger nodes** (m6i.4xlarge → m6i.8xlarge). Fewer nodes = fewer ENI overhead = more pod IPs net. | Schedule a Karpenter NodePool change; consolidation will migrate. |
| **1 day** | **Sub-VPC for pods** — separate VPC for pods only via VPC sharing + EKS managed node group cross-VPC ENI. | Complex; usually not worth it. |
| **1 week** | **Cluster-per-tenant** to reduce density. | Major migration. |

**Long-term:** treat pod-IP capacity as a Day-1 design constraint. Always reserve a `/16` per cluster, plus headroom in secondary CIDRs.

### B.3 — CI pipeline 47-min → 12-min plan

**Diagnose first** (15-min profile session).
- Lint + test sequential? → parallelize.
- Docker build pulls all layers from registry every time? → BuildKit + registry cache.
- Tests hit a real DB? → ephemeral container DB or testcontainers.
- Trivy scan blocks on full image rescan? → daily scan in cron, PR scan only delta layers.
- ArgoCD update is `sleep 60 && argocd app wait`? → use `argocd app sync --async`.

**3-week plan:**

| Week | Track | Wins |
|---|---|---|
| 1 | **Parallelize** lint, test, security scans. Move them to a `needs:` matrix. | 47m → 25m |
| 2 | **Cache** Docker BuildKit, npm/pip/maven dependencies, Trivy vuln DB. Push base image weekly to ECR. | 25m → 14m |
| 3 | **Reduce test scope on PR** — full suite on main, smoke + affected-tests on PRs. Use `git diff --name-only` to filter test targets. | 14m → 8m |

**Bonus:** Replace ArgoCD `wait` step with a webhook-driven "sync done" notification. Pipeline ends at "image pushed + PR opened on gitops repo," doesn't wait for cluster sync.

### B.4 — Zero-downtime EC2+EBS → EKS+EFS migration

**Stateful service** writes to local EBS, single replica. Need to move to EKS where multiple pods need shared storage (EFS, RWX).

**Migration in 5 stages.**

1. **Replicate** EBS → EFS (one-time bulk copy). DataSync or `rsync` from a temporary EC2 mounting both. Verify checksums.
2. **Run the new stack** in EKS, pointed at EFS, using a copy of the data. Smoke-test extensively at the read path; keep writes off (read-only mode).
3. **Stop writes briefly** (5-min maintenance window). Final delta-sync (rsync `--delete --update`).
4. **Cutover DNS** to point at the EKS ALB. Old EC2 stack now read-only as a safety net.
5. **Soak for 24 h.** If KPIs healthy: tear down EC2. If not: revert DNS — old stack still has the data.

**Rollback path:** at any stage 1-3, no impact (new stack is parallel). At stage 4, DNS-flip back. After tear-down, restore from the EFS snapshot taken at stage 3.

**Validation gates** between stages:
- Stage 2: read latency p99 within 10% of EC2 stack.
- Stage 3: zero-data-loss check: count records before/after, hash sample of files.
- Stage 4: error rate < 0.1% over first hour.

---

## 🛡️ Appendix C — Security baseline (one-page)

Drill these — security rounds love specifics.

| Layer | Control | "How I'd verify it" |
|---|---|---|
| **Identity** | Pod Identity (not IRSA) for new clusters; SSO via Identity Center | `aws eks list-pod-identity-associations` |
| **Network — pod** | Default-deny NetworkPolicy in every namespace | `kubectl get netpol -A` shows policies; test with a deny-by-default pod |
| **Network — node** | Pods in private subnets only; ALB in public; SG ingress from ALB SG only | `aws ec2 describe-security-groups` |
| **Network — egress** | Centralised through TGW + NAT in network account; egress filtering with allowlisted CIDRs | TGW route table audit |
| **Secrets** | All secrets via ESO from Secrets Manager; KMS-encrypted; rotated quarterly | No literal secrets in any Helm values |
| **Image** | ECR scan on push, Trivy in CI, sign with cosign, verify in admission via Kyverno/OPA | Block unsigned images |
| **Runtime** | PodSecurityAdmission `restricted` enforced; no `privileged`, no host networking, runAsNonRoot, readOnlyRootFilesystem | Audit `kubectl get pods -A -o jsonpath` for `privileged: true` |
| **Audit** | Cluster control-plane logs → CloudWatch; CloudTrail org trail to security S3 bucket; alarm on `kubectl exec` in prod | Test by exec-ing — alert should fire within 1 min |
| **Compliance** | AWS Config rules: encrypted EBS, encrypted S3, no public buckets, SG no `0.0.0.0/0:22` | Config dashboard green |
| **Vulnerability mgmt** | CRITICAL CVE → block deploy. HIGH → 14-day SLA. SBOM generated per build, stored in S3 | SBOM exists for every running image |
| **Backup** | EBS snapshots daily 14d retention; EFS backup vault; etcd backup via EKS managed (built-in) | Restore drill quarterly |
| **DR** | Multi-AZ everything; cross-region for stateful (RDS Multi-AZ + read replica in DR region); IaC for cluster recreate | Quarterly DR exercise |

---

## 🚨 Appendix D — Disaster recovery & backups (talking-points)

Senior interviewers always ask: **what happens when the region goes down?**

### D.1 The honest answer

A complete region failure is rare but real (us-east-1 has had 3 multi-hour incidents in the last 5 years). Your DR posture has three knobs:

- **RTO** (Recovery Time Objective): how long before the service is back?
- **RPO** (Recovery Point Objective): how much data can you lose?
- **Cost**: standby capacity is wasted spend until you need it.

| Pattern | RTO | RPO | Cost overhead |
|---|---|---|---|
| Backup & restore | hours-days | hours | minimal |
| Pilot light | 30-60 min | 5-15 min | ~10-20% |
| Warm standby | 5-15 min | seconds | ~50% |
| Active-active | seconds | seconds (or zero with global DB) | ~100% |

**Pick based on revenue impact / SLA**, not engineer enthusiasm. Most internal services live happily at "pilot light."

### D.2 What I'd actually back up

| Asset | How | Frequency | Restore tested |
|---|---|---|---|
| Application Git repo | GitHub native + S3 mirror | Real-time | Quarterly |
| Container images | ECR cross-region replication | Real-time | Quarterly |
| Cluster state (manifests) | Already in Git (GitOps) | Real-time | Bootstrap a new cluster from scratch quarterly |
| EBS volumes | AWS Backup, daily, 14d retention | Daily | Restore-and-mount drill quarterly |
| EFS filesystems | AWS Backup, daily, 30d retention | Daily | Restore drill quarterly |
| RDS / databases | Multi-AZ + automated snapshots + cross-region read replica for prod-tier | Real-time replica + 7d snapshots | Failover drill quarterly |
| Secrets | Secrets Manager has built-in regional replication; enable for prod secrets | Real-time | Failover drill |
| DNS | Route53 records in code (Terraform) | Source-controlled | N/A |

### D.3 Cluster rebuild — practical timeline

If the entire EKS cluster is gone (region fail, accidental delete):

1. **0-5 min:** Decision to rebuild vs wait for AWS recovery (depends on outage scope).
2. **5-15 min:** Terraform apply in DR region — VPC, subnets, IAM, EKS control plane.
3. **15-25 min:** Bootstrap ArgoCD (`kubectl apply -f bootstrap/argocd.yaml`).
4. **25-50 min:** ArgoCD reconciles all platform components (Karpenter, ESO, ALB controller, CoreDNS tuning).
5. **50-90 min:** App workloads start, scale up via Karpenter.
6. **90+ min:** DNS cutover to new region's ALB.

Total RTO ~90 min from "region is gone" to "users see service" — only achievable because everything is in Git + IaC. This is **why GitOps is a DR strategy, not just a workflow.**

### D.4 What kills DR plans in practice

- **The runbook lives in the broken cluster.** Mitigation: print it / store in a different region.
- **Secrets are local-only.** Mitigation: Secrets Manager regional replication.
- **DNS TTL is 24h.** Mitigation: 60s TTL on records that need to fail over.
- **No one has run the drill.** Mitigation: scheduled quarterly DR exercise; track time-to-recovery as a metric.
- **The IAM roles to do recovery don't exist in DR account.** Mitigation: pre-provision break-glass roles.

---

## ⭐ Appendix E — Two more STAR stories (extra ammo)

### STAR-9: Reducing cluster-upgrade risk

- **S:** EKS 1.26 → 1.27 upgrade approached. Last upgrade had 4-hour outage from CoreDNS API removal. Leadership nervous.
- **T:** Make upgrades safe and routine.
- **A:** Created an upgrade runbook: pre-upgrade checks (deprecated API audit via `kubent`, AMI compatibility, add-on version matrix), staged rollout (dev → stg → prod 1 week between), automatic rollback trigger on health-check failure within 5 min, observability dashboard pre-built. Ran a tabletop exercise with the team before the real upgrade. Migrated CoreDNS Corefile changes ahead of upgrade. Used Karpenter's drift detection to roll worker AMIs gradually, not big-bang.
- **R:** 1.27 upgrade completed in 3 hours, zero customer-facing impact. The runbook + tooling cut subsequent upgrades to ~90 min. Adopted as standard.

### STAR-10: Mentoring through a hard call

- **S:** A junior engineer on my team proposed replacing our entire Helm chart library with a Pulumi rewrite. Compelling pitch, but I felt the migration cost dwarfed the benefits.
- **T:** Decide without crushing their initiative or shipping a bad architecture.
- **A:** Asked them to write a one-page comparison: pain points solved, migration plan, on-call burden. Reviewed together — found the real pain was Helm template debugging, not the templating tool itself. Proposed a smaller win: adopt `helm-debug` tooling + a stricter Helm chart linter, leave the architecture alone. They presented this revised plan to the team — got immediate approval. I framed it as their decision, not mine.
- **R:** Helm chart pain dropped (debug time -60%). They led the linter rollout, got recognition, was promoted within 6 months. Most importantly: I avoided "no, because experience" and they learned the senior reflex of asking "what's the smallest thing that solves the actual pain?"

---

## 🎤 Appendix F — Recap: 30-second elevator pitch for "what's your stack?"

Memorise this. Variant of it works in 95% of interviews.

> *"Multi-account AWS with a network account holding the Transit Gateway, IGW/NAT, and VPN. Application accounts each run an EKS cluster with **Karpenter** for node autoscaling — picks Spot for stateless, on-demand for system. **ArgoCD** handles GitOps from a `gitops/` monorepo using app-of-apps + ApplicationSets. Pods authenticate to AWS via **EKS Pod Identity** — simpler than IRSA. Secrets come from **External Secrets Operator** projecting from AWS Secrets Manager. **AWS Load Balancer Controller** terminates TLS at ALBs in IP target mode. **EFS** for ReadWriteMany; EBS via the managed CSI for ReadWriteOnce. Networking: VPC CNI with prefix delegation, NodeLocal DNSCache to offload CoreDNS. Observability is Prometheus + AMP, Fluent Bit → CloudWatch, X-Ray for traces, Kubecost for chargeback. Multi-tenant via namespace + NetworkPolicy + ResourceQuota + Karpenter NodePool taints by trust tier."*

That's the whole stack in 90 seconds. The interviewer will pick a thread to drill into — you've already mapped each thread in this document.

---

*Real end of v1.0. Good luck.*



---

## 🗓️ Added 2026-08-15 (auto-generated · 4 new Q&A)

<!-- agent:2026-08-15 12:44 -->

### Q: How do you design multi-tenant isolation in EKS when multiple teams or customers share the same cluster?

Multi-tenancy in EKS requires layered isolation controls rather than a single mechanism. At the Kubernetes level, I enforce namespace-per-tenant with RBAC roles scoped strictly to those namespaces, preventing cross-namespace API access. Network policies (via Calico or the VPC CNI's native policy support) enforce traffic segmentation so pods in one tenant namespace cannot reach another. For stronger isolation, I map each tenant namespace to a dedicated IAM role using IRSA, ensuring cloud-resource permissions never leak across tenants. On the compute side, I use node selectors, taints/tolerations, and—when the threat model demands it—separate node groups per tenant to achieve noisy-neighbor containment and blast-radius reduction. Resource quotas and LimitRanges prevent one tenant from starving others. For the hardest compliance requirements I evaluate separate clusters per tenant (cluster-per-tenant model) and weigh that against the operational overhead of running the fleet.

---

### Q: Walk me through how you would troubleshoot intermittent pod-to-pod connectivity failures in a VPC CNI-based EKS cluster.

I approach this systematically, starting with data collection before making changes. First, I check `kubectl describe pod` and node events for any IP allocation failures—VPC CNI exhausts ENI secondary IPs if the instance type's IP limit is hit, so I verify ENI capacity against running pods per node and consider enabling prefix delegation to expand available IPs. I run `aws-node` DaemonSet logs (`kubectl logs -n kube-system -l k8s-app=aws-node`) to look for IPAMD errors or throttling from EC2 API. I use `kubectl exec` with `curl` or a debug container to reproduce the failure and capture the exact source/destination IPs, then check VPC Flow Logs to see if packets are being dropped at the security group or NACL layer—often a missing inbound rule for the pod CIDR. I verify that security groups attached to nodes allow traffic on the target port from the source pod's CIDR. If the issue is asymmetric, I look at conntrack table exhaustion on the node (`/proc/sys/net/netfilter/nf_conntrack_count` vs max). Finally I check whether a recent CNI version upgrade introduced a regression and review the CNI plugin changelog accordingly.

---

### Q: Compare the trade-offs between using AWS Fargate for EKS versus managed EC2 node groups. When would you choose each?

Fargate eliminates node management entirely—no patching, no capacity planning, no SSH access to nodes—which reduces operational toil and satisfies strict compliance postures since each pod runs on an isolated compute boundary with no shared kernel. The trade-offs are real, however: Fargate doesn't support DaemonSets, stateful workloads requiring local NVMe, or privileged containers, and cold-start latency is higher because each pod provisions a micro-VM. Cost is also less predictable at scale because you pay per vCPU/memory second with no Reserved Instance discounting equivalent (Savings Plans apply but less efficiently). Managed node groups with EC2 give you full control over instance family, GPU access, storage, and DaemonSet-based tooling (log agents, security sensors), and allow Spot instances for significant cost reduction on fault-tolerant workloads. My decision framework: Fargate for bursty, stateless, compliance-sensitive workloads where teams shouldn't own infrastructure; managed node groups for performance-sensitive, GPU, stateful, or cost-optimized at-scale workloads. In practice most production clusters use both—Fargate profiles for specific namespaces and EC2 node groups for baseline capacity.

---

### Q: Describe your approach to GitOps-based continuous delivery on EKS. What tooling choices would you make and what failure modes do you guard against?

My preferred GitOps stack on EKS centers on Flux or Argo CD as the reconciliation controller, with a Git repository as the single source of truth for all Kubernetes manifests and Helm releases. I structure the repo with environment overlays (Kustomize) so promotion from staging to production is a reviewed pull request rather than an ad-hoc `kubectl apply`. The controller runs inside the cluster and pulls changes, which is architecturally preferable to push-based CI pipelines that need cluster credentials stored externally. For secrets I integrate External Secrets Operator backed by AWS Secrets Manager or Parameter Store, ensuring no secrets live in Git. Key failure modes I guard against: (1) **drift**—I enable the controller's drift detection so out-of-band manual changes are automatically reverted; (2) **reconciliation loops**—I set explicit sync intervals and health checks so a bad manifest doesn't hammer the API server; (3) **image tag mutability**—I use image digest pinning or Argo CD Image Updater with digest references to prevent "latest" tag ambiguity; (4) **split-brain during outage**—I document a break-glass procedure allowing direct `kubectl` access with audit logging enabled, while the GitOps controller resumes reconciliation once connectivity restores. Rollback is a `git revert` plus a forced sync, giving a clear, auditable history.


---

## 🗓️ Added 2026-08-29 (auto-generated · 4 new Q&A)

<!-- agent:2026-08-29 16:32 -->

### Q: How do you design a cost-optimised EKS compute strategy using Spot Instances, and how do you handle interruptions gracefully?

A well-designed Spot strategy layers multiple instance families and sizes across several Availability Zones to maximise capacity pool diversity, configured via Karpenter NodePools or Cluster Autoscaler with mixed-instances policies. Key practices include:

- **Diversification**: specify 10–15 instance types of similar vCPU/memory profiles so Spot reclamation in one pool triggers capacity from another.
- **Interruption handling**: deploy the **AWS Node Termination Handler** (or rely on Karpenter's native interruption queue) to cordon and drain nodes within the 2-minute warning window.
- **Workload suitability**: run stateless, fault-tolerant workloads (batch jobs, ML training, data processing) on Spot; keep stateful or latency-sensitive services on On-Demand or Savings Plans.
- **Pod Disruption Budgets (PDBs)**: enforce minimum available replicas so a sudden Spot reclamation event doesn't drop below SLA thresholds.
- **Fallback**: configure a small On-Demand base capacity (e.g., 20%) and let Spot cover burst, ensuring the cluster degrades gracefully rather than failing entirely.

Typical outcome is 60–80 % compute cost reduction with near-zero unplanned downtime when all layers are in place.

---

### Q: Walk me through how you secure the EKS API server and the data plane network, from IAM through to pod-level controls.

Defence-in-depth across four layers:

1. **API server access**: set the endpoint to *private-only* or private+public with CIDR allowlisting; authenticate via **aws-auth ConfigMap** (migrating to EKS Access Entries in newer clusters) and enforce least-privilege IAM roles per team.
2. **RBAC**: map IAM roles to Kubernetes RBAC roles, never to `cluster-admin`; use namespaced Roles + RoleBindings; audit with `kubectl auth can-i --list` or tools like `rbac-lookup`.
3. **Network segmentation**: deploy nodes in private subnets, restrict control-plane-to-node SG rules; apply Kubernetes **NetworkPolicies** (Calico or Cilium) defaulting to deny-all and explicitly allowing required pod-to-pod flows.
4. **Pod-level controls**: enforce **Pod Security Admission** (restricted profile) cluster-wide; use **IAM Roles for Service Accounts (IRSA)** or **EKS Pod Identity** so pods assume scoped IAM roles without shared node credentials; enable **Secrets encryption** with a CMK in KMS; scan images in ECR with Inspector and block non-compliant images via OPA/Gatekeeper admission webhooks.

Continuous posture management via **AWS Security Hub** + **GuardDuty EKS Runtime Monitoring** closes the detection loop.

---

### Q: How do you architect observability for a large EKS fleet — metrics, logs, and traces — without creating runaway cost or operational toil?

The goal is correlated, actionable telemetry with predictable spend:

- **Metrics**: run **ADOT (AWS Distro for OpenTelemetry)** or the managed Prometheus add-on; scrape at 60 s intervals, drop high-cardinality labels at the collector tier, and remote-write to **Amazon Managed Prometheus**. Use recording rules to pre-aggregate. Visualise in **Managed Grafana**.
- **Logs**: use Fluent Bit DaemonSet to ship container logs to **CloudWatch Logs** (structured JSON only); set log group retention policies and use Contributor Insights for anomaly detection. Avoid shipping DEBUG logs from every pod to production.
- **Traces**: instrument services with **OpenTelemetry SDK** and send spans to **AWS X-Ray** or an OTLP-compatible backend; enable **tail-based sampling** to keep 100 % of error/slow traces and 1–5 % of healthy ones, cutting volume by 95 %.
- **Cost guard rails**: use metric-stream filtering, CloudWatch Metric Math instead of custom metrics where possible, and S3 archival for logs older than 30 days.
- **Correlation**: emit `trace_id` in structured logs so Grafana or CloudWatch can pivot from a metric spike → log line → trace without manual searching.

This stack typically costs $0.10–0.30 per node-hour all-in and gives <5-minute MTTR for most incidents.

---

### Q: Tell me about a time an EKS upgrade caused a production incident. What happened, what was your remediation, and what did you change permanently?

*(Behavioral — model answer framework)*

**Situation**: During an in-place upgrade from EKS 1.24 → 1.25, the removal of the `PodSecurityPolicy` API caused several third-party Helm charts (cert-manager, ingress-nginx) to lose their PSP resources silently; pods began failing admission after node rollout.

**Task**: Restore service within the RTO of 30 minutes while avoiding a full rollback.

**Action**:
- Immediately identified the root cause via `kubectl get events` and API server audit logs showing `Forbidden` responses from the new Pod Security Admission controller.
- Applied namespace-level `pod-security.kubernetes.io/enforce: privileged` labels as a temporary exemption to unblock pods, restoring traffic in ~12 minutes.
- Ran an emergency Helm upgrade for cert-manager and ingress-nginx to PSA-compatible versions.
- Conducted a post-incident review the same day.

**Result & permanent changes**:
1. Added a **pre-upgrade runbook** step requiring a staging cluster upgrade 2 weeks before production, with automated API deprecation scanning via `Pluto` in CI.
2. Instituted **blue/green cluster upgrades** (new cluster, traffic shift via weighted Route 53 or ALB target groups) instead of in-place upgrades for major version jumps.
3. Set up alerting on API server audit logs for `NotImplemented` and `Forbidden` spikes immediately after any upgrade window.


---

## 🗓️ Added 2026-08-30 (auto-generated · 4 new Q&A)

<!-- agent:2026-08-30 18:24 -->

### Q: How do you design a secure, scalable EKS networking architecture — including CNI choice, network policies, and ingress — for a highly regulated environment?

**What the interviewer wants to hear:** deep VPC/CNI knowledge, security posture, and awareness of compliance constraints.

- **CNI choice:** Use the AWS VPC CNI for native VPC IP assignment, which simplifies security group enforcement and satisfies auditors who want "no overlay network" visibility. For very large clusters, enable prefix delegation (`ENABLE_PREFIX_DELEGATION`) to avoid IPv4 exhaustion.
- **Security Groups for Pods:** Assign pod-level SGs to workloads that call RDS/ElastiCache so firewall rules are auditable in the same pane as EC2, rather than relying solely on NetworkPolicy.
- **Network Policies:** Layer Calico or Cilium *on top* of VPC CNI for L3/L4 NetworkPolicy enforcement; Cilium additionally provides L7 visibility and can replace a service mesh sidecar for mTLS.
- **Ingress:** AWS Load Balancer Controller with ALB in `ip` mode (pod-direct routing, no NodePort hop); use WAFv2 on the ALB for OWASP protection required by PCI/HIPAA.
- **Egress control:** Route egress through a NAT Gateway with a fixed IP allowlist and/or deploy AWS Network Firewall in a centralised inspection VPC via Transit Gateway for FQDN-based egress filtering.
- **Subnet segmentation:** Nodes in private subnets, control-plane endpoint private-only, bastion/SSM for access — no public IPs on nodes.
- **Compliance audit trail:** Enable VPC Flow Logs to S3 + Athena; pair with Amazon GuardDuty EKS Protection for runtime threat detection.

---

### Q: Walk me through how you would implement robust secrets management for workloads running in EKS, and what the failure modes of each approach are.

**What the interviewer wants to hear:** practical AWS Secrets Manager / Parameter Store integration, IRSA, and awareness of secret sprawl risks.

- **Preferred pattern:** IRSA (IAM Roles for Service Accounts) + Secrets Store CSI Driver with the AWS provider mounts secrets as volumes; no secrets ever touch etcd or environment variables visible in `kubectl describe pod`.
- **Alternative — External Secrets Operator (ESO):** Syncs Secrets Manager/SSM into native Kubernetes Secrets on a configurable refresh interval; broader community adoption but the secret *does* land in etcd, so etcd encryption at rest (KMS envelope encryption via `--encryption-provider-config`) is mandatory.
- **Failure mode — IRSA misconfiguration:** If the OIDC provider or trust policy is wrong, pods silently fall back to no credentials; instrument with CloudTrail and deny explicit `ec2:*` instance-metadata access (`IMDSv2` required, hop limit 1) so pods cannot escalate via node role.
- **Failure mode — CSI Driver unavailability:** If the CSI daemonset pod is evicted or crashlooping, pod startup blocks; mitigate with `secretProviderClass` sync-to-Kubernetes-Secret so a cached copy exists for restarts.
- **Secret rotation:** Secrets Manager auto-rotation must be coupled with either pod restart (via Reloader/stakater) or CSI's `rotationPollInterval` to ensure in-memory secrets stay fresh.
- **Audit:** Enable Secrets Manager resource policies + CloudTrail data events and periodically run `kubectl get secrets -A` to detect secrets created outside the approved pipeline.

---

### Q: Describe how you would architect EKS cluster autoscaling in 2024 — Cluster Autoscaler versus Karpenter — and when each is appropriate.

**What the interviewer wants to hear:** architectural judgement on Karpenter's advantages, operational trade-offs, and real scaling scenarios.

- **Cluster Autoscaler (CA):** Works against predefined Auto Scaling Groups; scaling decisions are ASG-bound, so you must pre-create node groups per instance family/size. Mature, well-understood, but can be slow (1–2 min per scale-out cycle) and requires careful ASG tagging and `--balance-similar-node-groups`.
- **Karpenter:** Provisions EC2 instances directly via EC2 Fleet/Launch Templates without ASGs; NodePool + EC2NodeClass CRDs describe constraints (instance families, AZs, capacity types). Scale-out latency is typically 30–45 seconds — a meaningful improvement for bursty workloads.
- **Karpenter's killer features:** Bin-packing consolidation (`disruption: consolidateAfter`) replaces over-provisioned nodes proactively; spot-to-on-demand fallback within a single NodePool; automatic Spot interruption handling via EC2 Instance Rebalance notifications.
- **When to keep CA:** If you have strict compliance requirements around ASG lifecycle hooks (e.g., custom drain scripts triggered by ASG hooks), or if your organisation's security review hasn't approved Karpenter's direct EC2 API permissions yet.
- **Avoid running both simultaneously** on the same node group — they will fight over scale-down decisions. Separate by node taints/labels if a migration phase requires coexistence.
- **Operational concern:** Karpenter requires careful NodePool `limits` to prevent runaway provisioning; always set CPU/memory ceilings and use AWS Service Quotas alerts as a backstop.

---

### Q: A team reports that their pods are experiencing intermittent "OOMKilled" events, but the application developers insist memory usage looks fine in their profiling tools. How do you systematically diagnose and resolve this?

**What the interviewer wants to hear:** methodical troubleshooting, understanding of cgroup memory accounting, JVM/Go/Node.js edge cases, and limits/requests design.

- **First, verify cgroup accounting vs. application view:** The OOM killer fires based on the container's cgroup RSS + page cache; languages with their own allocators (JVM, Go) or apps that memory-map large files may look "fine" inside the process but consume significant page cache the app doesn't account for.
- **Gather evidence:** `kubectl describe pod <pod> --previous` for `OOMKilled` exit code; `kubectl top pod` vs. limit; Prometheus `container_memory_working_set_bytes` (excludes reclaimable cache — closest to what Kubernetes uses for eviction) vs. `container_memory_rss`.
- **JVM-specific:** If the app is Java, check that `-Xmx` + metaspace + direct buffers + JVM overhead stay within the container limit; use `-XX:MaxRAMPercentage` rather than hardcoded `-Xmx` and add `-XX:+UseContainerSupport` (default in JDK 11+).
- **Go/Rust:** Check for goroutine leaks causing heap growth; `runtime.ReadMemStats` or pprof heap endpoint for evidence.
- **Sidecar containers:** Count memory against the Pod's total cgroup; a logging or Envoy sidecar may be the actual culprit — inspect per-container `container_memory_working_set_bytes` with `container=` label filter.
- **Resolution options:** (a) Increase memory limit with a buffer (20–30% headroom over p99 observed), (b) set correct JVM flags, (c) tune `GOMEMLIMIT` for Go 1.19+ apps, (d) if caused by page cache from file I/O, switch to `emptyDir` with `medium: Memory` or restructure I/O pattern.
- **Prevention:** Add Vertical Pod Autoscaler in recommendation mode to surface right-sizing data; enforce `LimitRange` minimums and require resource requests/limits via OPA/Gatekeeper admission policy.


---

## 🗓️ Added 2026-08-31 (auto-generated · 4 new Q&A)

<!-- agent:2026-08-31 20:38 -->

### Q: How do you design a highly available, cross-region EKS strategy for a workload that requires near-zero RTO and RPO?

A true active-active multi-region EKS design requires careful attention at every layer:

- **Control plane**: Provision independent EKS clusters in each region; the managed control plane is already multi-AZ within a region, so cross-region means separate clusters, not a stretched one.
- **Traffic routing**: Use Route 53 latency or health-check-based routing (or AWS Global Accelerator) to distribute traffic; combine with weighted records for controlled failover.
- **Data plane synchronisation**: For stateful workloads, use Aurora Global Database, DynamoDB Global Tables, or S3 Cross-Region Replication so the data layer is consistent before you fail over compute.
- **GitOps federation**: A single GitOps control plane (e.g., Flux with multiple cluster contexts, or ArgoCD in a hub-spoke topology) ensures identical workload manifests are reconciled in all regions simultaneously.
- **Service mesh bridging**: Tools like Istio's east-west gateway or AWS Cloud Map allow services in one cluster to discover and call services in the other during partial failures.
- **Testing**: Game-day exercises with AWS FIS (Fault Injection Simulator) simulating full-region unavailability are mandatory to validate RTO claims.

The honest trade-off is cost — running full capacity in two regions can double the compute bill — so many teams opt for active-passive with pre-warmed capacity using Cluster Autoscaler or Karpenter node pools on standby.

---

### Q: Walk me through how you would harden an EKS cluster to meet CIS Benchmark and SOC 2 requirements without crippling developer velocity.

**Key hardening layers and the velocity-preserving approach for each:**

- **API server access**: Enable private endpoint only; restrict public access to specific CIDR ranges or remove it entirely. Use AWS VPN or Direct Connect for operator access rather than bastion hosts.
- **RBAC**: Enforce least-privilege with namespace-scoped roles; use `aws-auth` ConfigMap (or the newer Access Entries API in EKS) audited by a policy-as-code tool like `rbac-lookup` in CI.
- **Pod Security**: Enforce the `restricted` Pod Security Standard at the namespace level via admission; give development namespaces `baseline` with a documented exception process.
- **Image supply chain**: Require all images to be signed (Cosign + Notation) and scanned (ECR Enhanced Scanning with Inspector v2); block unsigned or critical-CVE images at admission with Kyverno or OPA Gatekeeper — this is automated, not manual, so it doesn't slow PR merges.
- **Secrets management**: Prohibit plaintext Secrets in manifests; use the Secrets Store CSI Driver with AWS Secrets Manager or Parameter Store. Rotate secrets automatically.
- **Audit logging**: Enable EKS control-plane audit logs to CloudWatch; ship to a SIEM with a 90-day hot retention policy for SOC 2 evidence. Use Falco for runtime anomaly detection.
- **Velocity preservation**: Shift-left — embed `kube-score`, `checkov`, and `trivy` scans into the developer's IDE and PR pipeline so issues are caught before they reach the admission webhook and cause a deployment failure at 2 a.m.

---

### Q: Explain how EKS Pod Identity (the newer mechanism) differs from IRSA, and when you would migrate to it.

**IRSA (IAM Roles for Service Accounts)** works by annotating a Kubernetes ServiceAccount with a role ARN; the EKS OIDC provider exchanges a projected service-account token for temporary AWS credentials via `sts:AssumeRoleWithWebIdentity`. This requires you to embed the OIDC issuer URL in every IAM role's trust policy, which becomes operationally expensive at scale (especially across accounts).

**EKS Pod Identity** (GA since late 2023) introduces an agent (`eks-pod-identity-agent` DaemonSet) and a new EKS API resource — *Pod Identity Associations* — that maps a namespace/ServiceAccount pair to an IAM role directly in the EKS control plane, without touching the role's trust policy per cluster. The agent intercepts the credentials request on the node and vends credentials via a local endpoint.

**Key differences:**

| Dimension | IRSA | Pod Identity |
|---|---|---|
| Trust policy coupling | Per-cluster OIDC URL in trust policy | Single generic EKS principal |
| Cross-account | Requires role chaining or per-account OIDC | Cleaner; role stays in target account |
| Credential endpoint | `sts` regional endpoint | Local agent on node (faster, no STS call per pod) |
| Session tags | Limited | Supports `eks:cluster-name`, `eks:namespace`, `eks:service-account` |

**When to migrate**: Migrate when you manage more than a handful of clusters, when you need richer session-tag-based attribute-based access control, or when OIDC trust-policy sprawl is becoming an audit burden. IRSA remains valid for existing clusters with no immediate pain; there is no forced cutover.

---

### Q: A critical microservice on EKS is experiencing high tail latency (p99) during peak load but p50 is fine. How do you systematically diagnose and resolve it?

High p99 with healthy p50 is a classic indicator of resource contention, noisy-neighbour effects, or GC pressure — not an average-throughput problem. My systematic approach:

1. **Isolate the layer first**: Use distributed tracing (X-Ray or Tempo) to identify whether latency is inside the pod, in a downstream dependency, or in the network path. Many p99 problems are actually in a dependency, not the service under investigation.
2. **Node-level contention**: Check CPU throttling with `container_cpu_cfs_throttled_seconds_total` in Prometheus. Throttling is the single most common cause of tail latency in Kubernetes — pods are getting CPU-limited by their `limits` even though `requests` headroom appears available. Fix: raise limits or switch to a Guaranteed QoS class by setting `requests == limits`.
3. **Noisy neighbour**: Use `perf`, `ebpf`-based tools (Pixie, Parca), or node-level `iostat` to check if a co-located pod is saturating disk I/O or LLC cache. Remediation: use pod topology spread constraints or node affinity to isolate the service onto dedicated nodes.
4. **GC pauses (JVM/Go)**: Correlate p99 spikes with GC pause metrics. For JVM: tune heap, switch to G1/ZGC. For Go: check `runtime.MemStats`.
5. **Connection pool exhaustion**: If the service calls a database or downstream API, check whether connection pool exhaustion causes request queuing. Instrument with pool-wait-time metrics.
6. **Kernel network stack**: For very high RPS services, check if `conntrack` table is full (dropped packets) or if `net.core.somaxconn` is too low. Tune via node sysctl or use a custom AMI.
7. **Remediation and validation**: Apply fixes in a staging environment, run load tests with k6 or Gatling targeting the same concurrency profile, and confirm p99 improvement before promoting. Set p99 SLO alerts (not just p50) in the production SLO framework going forward.


---

## 🗓️ Added 2026-09-01 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-01 18:09 -->

### Q: How do you approach EKS cluster autoscaling — and when would you choose Karpenter over Cluster Autoscaler?

**Model Answer:**

Cluster Autoscaler (CA) operates at the node-group level, scaling pre-defined ASGs based on pending pods. Karpenter is node-group-agnostic: it watches unschedulable pods directly, selects the optimal instance type from a NodePool definition, and provisions nodes via EC2 Fleet in seconds rather than the 2–4 minute CA cycle. Key trade-offs:

- **Flexibility:** Karpenter can bin-pack across hundreds of instance families simultaneously; CA requires you to pre-create node groups for each type you want.
- **Speed:** Karpenter's direct EC2 API path is typically 60–90 s faster to first node-ready than CA+ASG warm-up.
- **Consolidation:** Karpenter's `consolidationPolicy: WhenUnderutilized` actively right-sizes and de-provisions nodes; CA relies on `--scale-down-utilization-threshold`, which is coarser.
- **Maturity:** CA has a longer production track record; Karpenter (GA since late 2023) has fewer edge-case integrations with some cluster add-ons.

**Choose Karpenter** for greenfield clusters, Spot-heavy workloads, or teams that want low-ops autoscaling with mixed instance diversity. **Stick with CA** when you have strict node group compliance/tagging requirements enforced externally (e.g., by a CCoE) or when the workload relies on GPU node groups with complex launch templates already managed by ASG.

Always set `topologySpreadConstraints` and appropriate PodDisruptionBudgets regardless of which scaler you use, so node churn doesn't create availability gaps during scale-down.

---

### Q: Walk me through how you would harden EKS workloads to meet CIS Kubernetes Benchmark and SOC 2 requirements without blocking developer velocity.

**Model Answer:**

The key is shifting controls left and automating enforcement so developers get fast feedback rather than change-freeze gates.

- **Admission control:** Deploy OPA/Gatekeeper or Kyverno with a tiered policy set — `warn` mode first in dev/staging, `deny` in prod. Policies cover: no `hostPID`/`hostNetwork`, required resource limits, no `latest` tags, mandatory pod labels.
- **Pod Security Standards:** Set `pod-security.kubernetes.io/enforce: restricted` on production namespaces; use `baseline` on developer sandboxes.
- **Supply chain:** Enforce image signing with AWS Signer + Cosign verified at admission; use ECR image scanning (Inspector) with a severity gate in CI.
- **Secrets:** Never mount AWS credentials as env vars; use IRSA (or EKS Pod Identity, now GA) scoped to least-privilege IAM roles per service account. Store secrets in Secrets Manager/Parameter Store, not K8s Secrets etcd.
- **Audit & drift:** Enable EKS control plane audit logs → CloudWatch → Security Lake; run `kube-bench` as a CronJob and export results to Security Hub.
- **Developer UX:** Provide a golden-path Helm chart library that's compliant by default, so teams don't write raw manifests against the hard rules.

SOC 2 evidence is then generated automatically from Security Hub findings and CloudTrail — auditors get dashboards rather than manual evidence packs.

---

### Q: A deployment rollout on EKS is causing cascading failures because the new pods pass readiness checks but start returning 5xx errors under real traffic seconds later. How do you diagnose and prevent this?

**Model Answer:**

This is a classic **shallow readiness probe** problem combined with potentially missing traffic-shaping guardrails.

**Diagnosis steps:**
1. Correlate pod start timestamps against ALB/Ingress 5xx spikes using Container Insights or your APM tool — confirm it's the new revision.
2. Check whether the readiness probe exercises only a `/healthz` stub rather than a dependency chain (DB, downstream services, cache warm-up).
3. Look for connection pool exhaustion or cold-start JIT latency (common in JVM/Node apps) — pod is "ready" but not yet at steady-state throughput.
4. Review `minReadySeconds` — if it's 0, traffic hits pods the instant readiness flips.

**Fixes:**
- **Deepen the probe:** Make `/ready` verify critical downstream connectivity and return 503 until warm.
- **`minReadySeconds`:** Set to 30–60 s so the pod must stay ready before the Deployment considers it available and terminates old pods.
- **Progressive delivery:** Use Argo Rollouts with a canary strategy and an analysis template querying error-rate metrics — auto-rollback if p99 or error rate breaches SLO within the analysis window.
- **`maxSurge` / `maxUnavailable`:** Tune to keep old pods serving until new pods are genuinely stable.
- **PreStop hook + `terminationGracePeriodSeconds`:** Ensure old pods drain in-flight requests before termination, so the transition window doesn't double-count failures.

---

### Q: How do you design an EKS IAM strategy using IRSA and EKS Pod Identity, and what are the security pitfalls to avoid?

**Model Answer:**

**IRSA (IAM Roles for Service Accounts)** works by annotating a Kubernetes ServiceAccount with an IAM role ARN; the OIDC provider on the EKS cluster issues a projected token that AWS STS exchanges for temporary credentials. **EKS Pod Identity** (GA 2023) simplifies this: it removes the per-cluster OIDC registration requirement and uses a new EKS-managed agent (DaemonSet) to vend credentials, making role associations a cluster-level API call rather than a trust-policy JSON edit per role.

**Design principles:**
- **One IAM role per workload** (not per namespace, not per cluster) — enables fine-grained least privilege and clean blast-radius containment.
- **Condition keys:** For IRSA, always add `aws:PrincipalTag` or `sts:RoleSessionName` conditions to prevent role assumption from unintended service accounts across namespaces.
- **No node instance profiles for app permissions:** If the node's EC2 role has S3/DynamoDB access, any pod can use it via the IMDS. Use IMDSv2 and, critically, set `--metadata-options httpPutResponseHopLimit=1` on node launch templates to block pod access to IMDS (hop count of 2 would reach containers).
- **Audit:** Use CloudTrail `AssumeRoleWithWebIdentity` events to verify which pods are assuming which roles; alert on unexpected role assumptions.
- **Pod Identity preference:** For new clusters on supported regions/versions, prefer Pod Identity — simpler trust policy management and no OIDC thumbprint rotation overhead.

Pitfall: developers sometimes request wildcard resource ARNs (`"Resource": "*"`) to unblock themselves — enforce SCPs or IAM permission boundaries at the account level to cap what any IRSA role can ever grant.


---

## 🗓️ Added 2026-09-02 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-02 18:24 -->

### Q: How do you design and manage EKS control-plane and data-plane upgrades at scale with minimal disruption?

EKS upgrades require a two-phase approach: control plane first, then node groups, and the two versions must stay within one minor version of each other. Before starting, I audit all add-ons (CoreDNS, kube-proxy, VPC CNI, EBS CSI) against the target version's compatibility matrix, and I run `kubectl deprecations` (or Pluto) to catch removed API versions in existing manifests and Helm charts. For the control plane I trigger the AWS-managed upgrade and monitor it via CloudTrail and the EKS API; it's generally low-risk because AWS handles the etcd and API server rollover. For node groups I use blue/green replacement: provision a new node group at the target version, cordon and drain the old group in batches using PodDisruptionBudgets to enforce quorum, then terminate the old group only after all workloads have migrated and are healthy. With Karpenter, I update the `EC2NodeClass` AMI family reference and roll nodes by annotating them with `karpenter.sh/do-not-disrupt: "false"` removal, letting Karpenter deprovision and replace naturally. Lessons learned: always test in a staging cluster first, pin add-on versions explicitly (not "latest"), and schedule the upgrade window to allow at least one full sprint to remediate any post-upgrade regressions before the next upgrade cycle.

---

### Q: Walk me through how you would debug and resolve an EKS networking issue where pods on different nodes cannot communicate intermittently.

I start by narrowing the blast radius: is this cross-AZ, cross-node-group, or random? I run a DaemonSet with `netshoot` to run `ping` and `curl` between specific pod IPs and note which source/destination node pairs fail. For VPC CNI, I check `aws-node` DaemonSet logs for IP allocation errors and verify the node has available secondary IPs with `kubectl describe node` (the `vpc.amazonaws.com/pod-eni` and `vpc.amazonaws.com/pod-count` annotations). Common culprits include: exhausted IP pools (fix: enable prefix delegation or increase `WARM_IP_TARGET`), stale iptables/eBPF rules after a node event (fix: restart `aws-node` on affected node), or security group rules that don't allow pod-to-pod ICMP/TCP (fix: audit the node and pod security groups). I also check for MTU mismatches—VPC CNI defaults to 9001 for Jumbo frames, but if an intermediate path doesn't support it, large packets are silently dropped; I verify with `ping -M do -s 8972`. If Calico or Cilium is layered on top, I inspect policy enforcement logs and check BPF map sizes. Finally, I correlate with VPC Flow Logs filtered to `REJECT` to identify whether drops are happening at the VPC level versus inside the node, and I open a CloudWatch Contributor Insights query to find the top offending source/destination pairs at scale.

---

### Q: How do you design an EKS secret management strategy that satisfies both security and developer-experience requirements?

The baseline is to never store secrets in ConfigMaps or environment variables baked into images. My preferred architecture uses the **Secrets Store CSI Driver** with the AWS Secrets Manager or Parameter Store provider, mounted as files into pods—this keeps secrets out of etcd entirely and provides automatic rotation without pod restarts (using the `rotation reconciliation` feature). For teams that need environment-variable-style access, I use the CSI driver's `syncSecret` feature to mirror the mounted secret into a Kubernetes Secret, scoped to the namespace. IAM access to each secret is controlled per workload via IRSA or EKS Pod Identity, so a compromised pod can only read its own secrets. I enforce this with OPA/Kyverno policies that reject pods referencing `secretKeyRef` pointing to broadly-scoped Kubernetes Secrets not created by the CSI driver. For secret rotation, I configure Secrets Manager rotation Lambdas and set short `rotationPollInterval` values on the CSI driver; applications are designed to re-read secrets from the filesystem on a health-check cycle rather than caching them at startup. Audit trails come from CloudTrail (Secrets Manager API calls) and from Kubernetes audit logs filtered on `secrets` resource access. The developer experience is preserved via Helm chart templates that abstract the `SecretProviderClass` boilerplate, and a self-service Terraform module that provisions the secret, the IAM policy, and the IRSA binding together.

---

### Q: A cost audit reveals your EKS workloads are consuming 60% more compute than capacity planning predicted. How do you investigate and remediate over-provisioning?

I treat this as a data problem first. I deploy **Kubecost** (or use AWS Cost Explorer with split-cost allocation tags) to attribute spend to namespace, team, and workload. The most common root causes are: (1) `requests` set far higher than actual utilisation, (2) HPA minimum replicas never scaling down, (3) DaemonSets running on oversized nodes, and (4) orphaned node groups from old feature branches. For (1), I pull 30-day Prometheus data on `container_cpu_usage_seconds_total` and `container_memory_working_set_bytes` vs. `kube_pod_container_resource_requests` to quantify the gap per container, then use **VPA** in recommendation-only mode to generate right-sized request values—teams review and adopt them through their Helm values. For (2), I audit HPA `minReplicas` configurations; many teams set them high for "safety" without understanding the cost implication, so I establish a policy that `minReplicas` for non-critical workloads defaults to 1-2 with Karpenter consolidation enabled. For (3), I evaluate whether DaemonSets are truly needed cluster-wide or could be replaced with sidecar injection scoped to specific namespaces. For (4), I tag all node groups with the owning team and TTL, and a Lambda function alerts on groups older than 14 days with no active pods. Remediation is iterative: I target the top-10 over-provisioned workloads for a 30% request reduction sprint, measure impact, and repeat. I also enable Karpenter's **consolidation policy** (`WhenUnderutilized`) so underloaded nodes are compacted automatically, typically recovering 15-25% of compute cost without application changes.


---

## 🗓️ Added 2026-09-03 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-03 18:19 -->

### Q: How do you design an EKS storage strategy for stateful workloads, and what are the trade-offs between the available volume options?

**Model Answer:**

The primary storage options on EKS are EBS (via the EBS CSI driver), EFS (via the EFS CSI driver), and FSx for Lustre/NetApp ONTAP for specialist workloads.

- **EBS**: Low-latency, high-throughput block storage; `ReadWriteOnce` only, so pods are zone-pinned — design node groups and PersistentVolumes in the same AZ to avoid scheduling failures and cross-AZ data transfer costs. Best for databases (Postgres, MySQL) and single-writer workloads.
- **EFS**: Managed NFS with `ReadWriteMany`; simpler multi-pod access but higher latency (~1–2 ms vs <0.5 ms for io2 EBS) and per-GB-read cost. Suitable for shared config, ML training checkpoints, or CMS assets.
- **FSx for Lustre**: Purpose-built for HPC/ML; parallel throughput in the hundreds of GB/s but expensive and operationally heavier.
- Use **VolumeSnapshotClass** for crash-consistent backups and test restores regularly. Set `reclaimPolicy: Retain` in production StorageClasses to prevent accidental data loss on PVC deletion.
- For StatefulSets, use `volumeClaimTemplates` and ensure Pod Disruption Budgets and `terminationGracePeriodSeconds` are tuned so storage detaches cleanly before a node drains.
- Key pitfall: EBS volumes take ~10–30 s to detach/reattach; if a node is forcibly terminated (Spot interruption, AZ failure), the volume may stay attached, blocking new pod scheduling — set `--volume-attach-timeout` appropriately in the CSI driver.

---

### Q: Walk me through how you would design and enforce a supply-chain security posture for container images running on EKS.

**Model Answer:**

Supply-chain security spans image build, distribution, admission, and runtime layers.

- **Build**: Use minimal base images (distroless or Chainguard), pin digests not tags, and integrate Trivy/Grype into CI to fail builds above a CVSS threshold. Sign images with **Sigstore/Cosign** and push signatures to ECR alongside the image.
- **Registry**: Enable **ECR image scanning** (Enhanced Scanning via Inspector v2) for both push-time and continuous rescanning. Use ECR lifecycle policies to evict untagged/old images and reduce attack surface.
- **Admission**: Deploy **Kyverno** or **OPA/Gatekeeper** with a policy that verifies Cosign signatures before allowing image pulls (`cosign verify` via Kyverno's `verifyImages` rule). Reject `latest` tags, privileged containers, and images from non-approved registries.
- **Runtime**: Use **Falco** or AWS GuardDuty Runtime Monitoring for anomaly detection — unexpected process execution, outbound connections, `/proc` reads, etc.
- **SBOM**: Generate and attest SBOMs (CycloneDX/SPDX) at build time using `syft`; store attestations in ECR so you can audit component lineage after a CVE disclosure.
- Tie everything together with a **policy-as-code** repo where changes go through PR review, ensuring governance isn't a one-time checklist but a living control.

---

### Q: Your EKS cluster's API server starts returning 429/503 errors intermittently during business hours. How do you diagnose and resolve this?

**Model Answer:**

EKS API server throttling and unavailability typically stem from client-side request storms, control-plane resource exhaustion, or AWS-side limits.

1. **Quantify**: Pull `apiserver_request_total` and `apiserver_request_duration_seconds` from the control-plane CloudWatch Container Insights metrics. Look for spikes in `LIST`/`WATCH` verb counts.
2. **Identify top talkers**: Enable **API server audit logs** (send to CloudWatch Logs), then query with Logs Insights — `stats count(*) by user.username, verb, resource` — to find which controllers, operators, or kubectl users are flooding the API.
3. **Common culprits**: Misconfigured controllers doing full re-list on every reconcile loop, `kubectl get pods --all-namespaces` in monitoring scripts, Helm hooks that poll aggressively, or a Karpenter/CAS loop thrashing on conflicting decisions.
4. **Remediation**:
   - Add `--qps` and `--burst` flags to offending controllers; tune informer cache `resyncPeriod`.
   - Use **watch** instead of repeated `list` calls in custom controllers.
   - If using many CRDs, audit `etcd` object count — AWS EKS etcd has object limits (~25K secrets, etc.).
   - Request an EKS control-plane limit increase via AWS Support if legitimately needed.
5. **Structural fix**: Apply client-side rate limiting, back-off/retry logic in operators, and set up a CloudWatch alarm on `apiserver_request_total{code="429"}` so you catch this proactively.
6. **Behavioral note**: In a post-mortem I'd capture this as a toil-reduction item — automate the audit log query as a Runbook so on-call doesn't need to reinvent it each time.

---

### Q: How do you design an EKS service mesh strategy, and when is a service mesh the wrong answer?

**Model Answer:**

A service mesh (Istio, AWS App Mesh, Linkerd, Cilium Service Mesh) adds mTLS, traffic management, and deep observability at the cost of operational complexity and latency overhead.

**When it's justified:**
- Zero-trust, pod-to-pod mTLS is a hard compliance requirement and you can't achieve it purely with network policies.
- Fine-grained traffic shaping (weighted canary, fault injection, circuit breaking, retries) that application code shouldn't own.
- Uniform observability (L7 golden signals) across polyglot services without per-language instrumentation.

**Design considerations:**
- **Linkerd** is the lightest-weight option (Rust data-plane, ~2 ms added latency), good for teams that want mTLS + metrics with low ops burden. **Istio** (with ambient mesh in sidecar-less mode) is more feature-rich but operationally heavier.
- In EKS, integrate with **ACM Private CA** or **cert-manager** for workload certificate issuance; automate rotation.
- Use **strict** mTLS mode only after ensuring all services are enrolled — otherwise you silently allow plaintext. Canary the rollout namespace by namespace.
- Separate data-plane from control-plane upgrades; control-plane disruption should not drop existing connections.

**When it's the wrong answer:**
- Small clusters (<20 services) where network policies + IRSA + ALB auth satisfy security requirements — a mesh adds 10–30% CPU overhead per sidecar for marginal gain.
- Teams without the maturity to operate it; a misconfigured Istio `VirtualService` is a common cause of hard-to-debug outages.
- Fargate-heavy clusters where sidecar injection is constrained.
- Start with Cilium's native network policies and BPF-based observability first; add a full mesh only when you've exhausted simpler primitives.


---

## 🗓️ Added 2026-09-04 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-04 18:03 -->

### Q: How do you design an EKS pod security strategy post-PodSecurityPolicy deprecation, and what controls do you layer together?

**What the interviewer wants:** Understanding of the PSP replacement landscape, defense-in-depth, and practical enforcement.

PSP was removed in Kubernetes 1.25, so the replacement stack combines **Pod Security Admission (PSA)**, **OPA/Gatekeeper or Kyverno**, and runtime security tooling. My layered approach:

- **PSA** (built-in): Apply `baseline` or `restricted` standards at the namespace level via labels; use `warn` mode in non-prod namespaces first to surface violations before enforcing.
- **Kyverno or OPA/Gatekeeper**: Policy-as-code for controls PSA can't express — e.g., required labels, image registry allow-lists, disallowing `latest` tags, enforcing resource requests/limits.
- **Seccomp / AppArmor profiles**: Applied via `securityContext`; EKS 1.27+ defaults the `RuntimeDefault` seccomp profile, which I enforce cluster-wide via policy.
- **Runtime enforcement**: Falco or AWS GuardDuty for Containers detects anomalous syscalls at runtime — the last line of defence when a misconfigured or compromised pod is already running.
- **Image scanning**: ECR native scanning or Trivy in CI gates prevent vulnerable images reaching the cluster at all.

The key trade-off is Kyverno (Kubernetes-native, easier authoring) vs. Gatekeeper (Rego, more expressive but steeper learning curve). I choose Kyverno for most teams unless there's an existing OPA investment. I always run policies in `audit` mode first, export violations to CloudWatch, and set a remediation SLA before flipping to `enforce`.

---

### Q: Your EKS cluster nodes are joining but pods remain in "Pending" with no scheduler events. How do you systematically diagnose and resolve this?

**What the interviewer wants:** Structured troubleshooting, knowledge of scheduler internals, node readiness lifecycle, and common EKS-specific gotchas.

I work through a structured hierarchy of failure domains:

1. **Node readiness**: `kubectl get nodes` — are nodes `Ready`? Check `kubectl describe node` for condition taints (`node.kubernetes.io/not-ready`, `node.kubernetes.io/disk-pressure`). Examine kubelet and containerd logs via SSM or CloudWatch Logs.
2. **Scheduler visibility**: `kubectl describe pod <pending>` — if there are *no* scheduler events at all, the scheduler itself may be unhealthy, or the pod is hitting a **node selector / affinity / toleration** mismatch that prevents scheduling silently.
3. **Resource pressure**: Verify `Allocatable` vs. `Requested` on nodes. A common EKS gotcha is that the VPC CNI pre-allocates ENIs/IPs, and if the subnet is exhausted, nodes become `NotReady` with a CNI error — pods never schedule.
4. **Taints**: New Karpenter or managed node group nodes may have a startup taint (`node.kubernetes.io/not-ready`) that isn't cleared if the node bootstrap script failed. Check EC2 user-data logs and `aws ec2 describe-instances` for instance state.
5. **Resource quotas / LimitRange**: Namespace-level `ResourceQuota` can silently block scheduling if the pod spec lacks required requests. `kubectl describe resourcequota -n <ns>` reveals exhaustion.
6. **Cluster Autoscaler / Karpenter race**: Pending pods might be waiting for a node the autoscaler decided to provision but that node failed to join (IAM role, launch template AMI mismatch). Check CA logs for `failed to create node group` errors.

Resolution path: fix the root cause (subnet CIDR expansion, taint correction, quota increase), then force pod rescheduling. Post-incident, I add alerts on sustained pending pod counts > 5 minutes.

---

### Q: How do you design an EKS disaster recovery strategy that accounts for both the control plane and stateful workload data, and how do you validate it?

**What the interviewer wants:** End-to-end DR thinking beyond just "use another region," including control-plane state, etcd, PV data, and runbook validation.

EKS's managed control plane means AWS owns etcd availability within a region, but you're still responsible for everything *above* the API — and for data-plane and stateful recovery. My design covers five layers:

- **Cluster configuration**: All cluster resources (Deployments, Services, CRDs, RBAC, ConfigMaps) are GitOps-managed in Flux/ArgoCD. Recovery = bootstrap a new cluster and let GitOps converge. Target RTO for stateless workloads: <30 minutes.
- **Persistent data**: Use Velero with CSI snapshot support for EBS/EFS volumes. Snapshots are cross-region copied on a schedule matching RPO requirements. For databases, prefer RDS/Aurora with cross-region read replicas over self-managed PVs — the managed service DR story is stronger.
- **Secrets**: External Secrets Operator pulling from AWS Secrets Manager, which replicates secrets cross-region. No Kubernetes secrets hold source-of-truth data.
- **Networking dependencies**: Pre-provision VPCs, subnets, and Route53 hosted zones in the DR region. Use weighted routing policies so failover is a weight change, not a DNS propagation event.
- **Validation — the critical part**: Run **quarterly DR drills** where the DR cluster is actually promoted. Use `kubectl diff` against the GitOps repo to confirm drift, run smoke tests, and measure actual RTO vs. target. Without validation, DR plans are fiction.

I also instrument the mean-time-to-detect (MTTD) for control-plane unavailability via synthetic probes hitting the API server from a separate monitoring account, so the DR trigger is automated rather than dependent on human observation.

---

### Q: A security audit finds that several EKS workloads are making unexpected AWS API calls outside their intended permissions. How do you investigate the blast radius and harden the environment going forward?

**What the interviewer wants:** Incident-response methodology, IRSA misuse patterns, detective controls, and remediation strategy.

**Immediate investigation:**

- Pull **CloudTrail** logs filtered by the OIDC-derived role ARNs associated with the offending workloads. Identify which API calls were made, from which source IP (pod IP maps to node via VPC Flow Logs), and whether they succeeded.
- Check whether the calls used the *pod's* IRSA token or the *node's* EC2 instance profile — a common finding is that workloads fall back to the node role because IRSA is misconfigured, meaning the node role has over-broad permissions.
- Map service account → IAM role → policy to determine actual granted permissions vs. what was intended (`aws iam simulate-principal-policy` is useful here).

**Blast radius assessment:**
Determine whether any data was exfiltrated (S3 `GetObject`, Secrets Manager `GetSecretValue`) or infrastructure mutated (EC2 `RunInstances`, IAM `CreateRole`). Escalate to a security incident if sensitive data or privilege escalation is confirmed.

**Hardening actions:**

1. **Restrict node instance profiles** to the absolute minimum (ECR pull, CloudWatch Logs, SSM) — nothing that application workloads should ever use.
2. **Enforce IRSA on every workload** via Kyverno policy that rejects pods with `AWS_*` env vars injected manually or missing the required service account annotation.
3. **Enable IAM Access Analyzer** to continuously flag roles with unused permissions; implement least-privilege remediation quarterly.
4. **GuardDuty EKS Audit Log monitoring** detects anomalous API server behaviour and unusual IRSA usage patterns as an ongoing detective control.
5. **Scope IAM role trust policies** with `aws:RequestedRegion` and `sts:ExternalId`-equivalent OIDC conditions so a stolen token cannot be used outside the expected cluster.

Post-incident, I introduce a **permission boundary** on all IRSA roles created going forward, capping the maximum effective permissions regardless of what the attached policies allow.


---

## 🗓️ Added 2026-09-05 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-05 17:07 -->

### Q: How do you design an EKS networking strategy for IPv6, and what are the operational trade-offs compared to IPv4?

**Key points an interviewer wants to hear:**

- **Why IPv6 on EKS:** Each pod gets a unique global IPv6 address, eliminating the RFC-1918 exhaustion problem that plagues large IPv4 clusters (especially with the VPC CNI's IP-per-pod model consuming ENI secondary IPs rapidly).
- **VPC CNI behaviour:** In IPv6 mode the CNI assigns one IPv6 address per pod directly from the VPC prefix; there is no need for custom networking or prefix delegation workarounds required in large IPv4 deployments.
- **Dual-stack reality:** Most production deployments today run dual-stack (IPv4 + IPv6) at the VPC level because downstream dependencies—RDS, ElastiCache, many SaaS endpoints—remain IPv4-only; you must plan NAT64/DNS64 at the subnet level for egress to IPv4 services.
- **Trade-offs:**
  - Security groups for pods work the same way, but flow logs are more verbose and SIEM parsers often need updating.
  - Third-party tooling (service meshes, some CNI plugins, WAF rules) may have incomplete IPv6 support.
  - Fargate on EKS supports IPv6 but only in single-stack IPv6 VPCs; mixing Fargate and EC2 nodes in dual-stack clusters requires careful subnet design.
- **Load balancer layer:** AWS Load Balancer Controller supports dualstack and dualstack-without-public-ipv4 target types; choose based on whether external clients are IPv6-capable.
- **Migration path:** Migrating an existing IPv4 cluster is destructive (cluster replacement); plan this as a greenfield deployment with traffic migration via weighted DNS or a service mesh.

---

### Q: How do you design an EKS add-on and cluster configuration drift-prevention strategy at scale?

**Key points an interviewer wants to hear:**

- **The drift problem:** In a fleet of dozens of clusters, manual console changes, ad-hoc `kubectl apply` operations, and out-of-band EKS add-on upgrades cause clusters to silently diverge—leading to "works in cluster A, fails in cluster B" incidents.
- **Infrastructure layer (Terraform/CDK):** Represent every cluster, managed node group, EKS add-on version, and IRSA binding in IaC; enforce via CI plan-and-apply pipelines with required PR approvals. Use remote state locking to prevent concurrent mutations.
- **Kubernetes manifest layer (GitOps):** Use Flux or ArgoCD with the `--prune` flag and a deny-all default sync policy so any resource not in Git is removed. ApplicationSets or Flux `Kustomization` objects let you fan out a single source to multiple clusters.
- **Add-on version pinning:** Explicitly pin EKS managed add-on versions in IaC rather than using `LATEST`; subscribe to AWS SNS notifications for add-on deprecations so upgrades are deliberate.
- **Policy enforcement:** Deploy OPA/Gatekeeper or Kyverno policies that reject mutations to protected namespaces (e.g., `kube-system`) unless they originate from the GitOps service account.
- **Drift detection and alerting:** Run `kubectl diff` or ArgoCD's out-of-sync alerting on a schedule; pipe results to a Slack channel or PagerDuty so drift is visible within minutes, not discovered during an incident.
- **Behavioral angle:** Emphasise that tooling alone is insufficient—teams need a culture where "if it's not in Git, it doesn't exist," enforced by removing broad IAM permissions for direct cluster write access from human users.

---

### Q: A newly onboarded EKS cluster in a regulated industry fails a CIS Kubernetes Benchmark scan. How do you systematically remediate it without breaking running workloads?

**Key points an interviewer wants to hear:**

- **Baseline first:** Run `kube-bench` (the CIS benchmark tool) against control-plane and worker node components to produce a prioritised finding list categorised as Level 1 (must-fix) and Level 2 (environment-specific).
- **Control-plane findings on EKS:** AWS manages the API server, etcd, and scheduler—you cannot SSH into them. For findings like audit logging, enable EKS control-plane audit logs to CloudWatch; for API server flags you cannot change, document the shared-responsibility boundary and compensate with detective controls.
- **Node-level findings:** Use a custom AMI built with EC2 Image Builder or Bottlerocket (which ships CIS-hardened by default) to address kubelet configuration, file permissions, and kernel parameters. Replace nodes via a rolling node-group update to avoid workload disruption.
- **RBAC and authentication:** Remediate overly permissive ClusterRoleBindings incrementally—use `kubectl auth can-i --list` and audit logs to identify blast radius before removing permissions. Enforce MFA/SSO via IAM Identity Center; remove static `aws-auth` ConfigMap entries in favour of EKS Access Entries.
- **Workload-impacting changes (e.g., disabling anonymous auth, enabling admission controllers):** Test in a non-production cluster first; use PodDisruptionBudgets and canary rollouts when node replacement touches production.
- **Continuous compliance:** Integrate `kube-bench` into a CI job and deploy AWS Security Hub with the EKS standard to get ongoing drift alerting rather than treating this as a one-time exercise.

---

### Q: How do you design an EKS strategy for machine-learning inference workloads that require GPU nodes, and what are the key operational pitfalls?

**Key points an interviewer wants to hear:**

- **Node provisioning:** Use Karpenter with GPU-aware `NodePool` definitions (e.g., `g5`, `p4d`, `inf2` instance families) and `limits` to cap total GPU spend. Karpenter's bin-packing is particularly valuable here because GPU instances are expensive and idle allocation is wasteful.
- **Device plugin:** Deploy the NVIDIA Device Plugin DaemonSet (or the AWS Neuron device plugin for Inferentia/Trainium) so the scheduler can treat `nvidia.com/gpu` or `aws.amazon.com/neuron` as a schedulable resource. Pin the plugin version to the driver version on your AMI.
- **AMI and driver management:** Use the EKS-optimised accelerated AMI or a custom AMI with a tested driver stack; driver/CUDA/framework version mismatches are the #1 cause of silent inference errors or OOM crashes that look like application bugs.
- **Resource requests and limits:** Always set `nvidia.com/gpu` as both request and limit (they must be equal); unlike CPU/memory, GPUs are not overcommittable. Failing to set limits causes a pod to consume the full GPU while kubernetes reports zero GPU usage.
- **Spot for inference:** GPU Spot instances can cut costs 60–70% but require the model server (Triton, TorchServe) to checkpoint in-flight requests or drain gracefully on SIGTERM. Use `terminationGracePeriodSeconds` aligned to your model's warm-up time so replacement pods are ready before traffic shifts.
- **Observability pitfalls:** Standard CloudWatch and Prometheus node exporters do not expose GPU utilisation or memory bandwidth by default; deploy `dcgm-exporter` (NVIDIA DCGM) to get GPU-level metrics, and alert on GPU memory utilisation rather than CPU to catch saturation early.
- **Multi-tenancy on GPU nodes:** Avoid placing non-GPU workloads on GPU nodes (use taints/tolerations); a single CPU-bound sidecar can starve the GPU process of scheduling time and inflate p99 latency unpredictably.


---

## 🗓️ Added 2026-09-06 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-06 17:30 -->

### Q: How do you design an EKS ingress strategy at scale, and what are the trade-offs between the AWS Load Balancer Controller, NGINX, and Gateway API?

**Model Answer:**

The choice hinges on operational complexity, feature surface, and traffic profile:

- **AWS Load Balancer Controller (ALB Ingress):** Provisions an ALB per Ingress or shared via IngressGroup. Best for teams wanting deep AWS-native integration (WAF, Cognito, target-group binding for gRPC/NLB). Trade-off: ALB per service can be expensive; cross-namespace sharing requires `IngressGroup` discipline.
- **NGINX Ingress Controller:** Single NLB/CLB fronts many virtual hosts via L7 routing in-cluster. Richer annotation set, better cost profile at high Ingress-object count, but you own the NGINX pod's availability and scaling.
- **Gateway API (v1 GA):** Separates infra (GatewayClass, Gateway) from app-team concerns (HTTPRoute). Preferred for multi-team clusters because it enforces RBAC-aligned role separation without annotation sprawl. AWS supports it via the LBC's Gateway API mode.
- **Scaling pitfalls:** ALB rule limits (100 rules/listener), NGINX config reload latency at thousands of Ingresses, and certificate management (use ACM for ALB, cert-manager for NGINX).
- **Recommendation at scale:** Adopt Gateway API as the abstraction layer with LBC as the implementation for AWS-native traffic, and NGINX for complex rewrite/snippet use-cases where Gateway API support is immature.

---

### Q: Your EKS cluster's DNS resolution is intermittently timing out under load. How do you systematically diagnose and resolve this?

**Model Answer:**

DNS failures in EKS almost always trace to CoreDNS saturation or misconfiguration, with the VPC resolver as a secondary suspect.

1. **Quantify the blast radius:** `kubectl top pods -n kube-system` for CoreDNS CPU/memory; check CoreDNS `coredns_dns_request_duration_seconds` and `coredns_dns_responses_total{rcode="SERVFAIL"}` metrics.
2. **Check `ndots` amplification:** Default `ndots:5` causes up to 8 DNS queries per external hostname lookup. Audit pod `dnsConfig` and reduce to `ndots:2` or append absolute FQDNs where possible.
3. **CoreDNS horizontal scaling:** CoreDNS is often under-provisioned — scale replicas, enable `PodDisruptionBudget`, and pin replicas across AZs with `topologySpreadConstraints`.
4. **NodeLocal DNSCache:** Deploy the `node-local-dns` DaemonSet to cache responses at the node level, bypassing conntrack table pressure that causes UDP packet drops under high connection rates (a known Linux kernel issue with `DNAT` and CoreDNS).
5. **VPC resolver limits:** Each EC2 instance is limited to 1,024 DNS packets/second to the VPC resolver (.2 address). At scale, switch bulk external lookups to Route 53 Resolver or cache aggressively.
6. **Validate fix:** Use `dnsperf` or `kubectl exec` `dig` loops to reproduce the failure rate before and after changes.

---

### Q: How do you design an EKS workload identity and supply-chain security strategy to meet SLSA Level 3 requirements?

**Model Answer:**

Meeting SLSA L3 on EKS requires controls across build, publish, and runtime stages:

- **Hermetic, reproducible builds:** Use AWS CodeBuild with network-egress blocked or GitHub Actions OIDC with provenance attestation. Build systems must not allow mutable inputs at build time.
- **Provenance and signing:** Sign container images with **Sigstore/Cosign** and generate SLSA provenance documents, storing both in ECR alongside the image via OCI referrers API. Use AWS Signer for an AWS-native alternative.
- **Admission enforcement:** Deploy **Kyverno** or **OPA Gatekeeper** policies that verify Cosign signatures and provenance against a trusted Sigstore TUF root before any pod is admitted. Reject unsigned or unverified images at the policy layer.
- **SBOM generation and vulnerability gating:** Attach SBOMs (Syft/CycloneDX) as OCI artifacts; pipe them into **Amazon Inspector** or Grype in CI to block images with critical CVEs before push.
- **Immutable registry:** Enable ECR image immutability and tag-protection policies so deployed digests cannot be overwritten.
- **Runtime enforcement:** Combine **Falco** rules with seccomp/AppArmor profiles and read-only root filesystems to detect supply-chain compromise at runtime.
- **Audit trail:** All image promotions, policy decisions, and IRSA credential issuance should flow into CloudTrail + S3 for the immutable audit log SLSA L3 demands.

---

### Q: A large EKS cluster is experiencing node-level "NotReady" flapping on a subset of nodes every few hours, but the nodes recover without manual intervention. How do you diagnose the root cause?

**Model Answer:**

Intermittent `NotReady` that self-recovers is deceptive — it rarely points to the obvious causes. Systematic approach:

1. **Correlate timing:** `kubectl describe node <node>` — check `Conditions` history and the `lastTransitionTime`. Cross-reference with CloudWatch node-level metrics (CPU steal, network error counters) and EC2 status checks at the same timestamp.
2. **Kubelet health:** SSH (or use SSM) to an affected node and inspect `journalctl -u kubelet --since "X minutes ago"`. Look for PLEG (Pod Lifecycle Event Generator) errors — `PLEG is not healthy` means the container runtime is stalling, often a containerd or Docker daemon issue.
3. **Container runtime pressure:** Check `containerd` or `dockerd` logs for image pull storms, garbage collection pauses, or OOM events on the runtime process itself. Disk I/O saturation during image GC is a common culprit on `gp2` volumes — migrate to `gp3` with provisioned IOPS.
4. **Network plugin (CNI) failures:** For VPC CNI, check `ipamd` logs (`kubectl logs -n kube-system aws-node-<id>`). IP exhaustion in a subnet causes ipamd to stall, which can manifest as kubelet losing connectivity to the API server.
5. **EC2 maintenance events:** Call `aws ec2 describe-instance-status` — Spot interruption notices or scheduled maintenance can cause transient `NotReady` before the instance is replaced.
6. **Node-level resource pressure:** `NotReady` also fires when the node's own memory pressure triggers the kubelet's eviction manager — check `MemoryPressure` and `DiskPressure` conditions; tune eviction thresholds or right-size the node.
7. **Resolution:** Once root cause is confirmed, encode the fix in the node group launch template (e.g., containerd config, larger ephemeral storage, ENI warm pool settings) and validate with a canary node group before rolling fleet-wide.


---

## 🗓️ Added 2026-09-07 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-07 18:59 -->

### Q: How do you design an EKS cluster networking strategy to support PrivateLink-based communication between clusters and external AWS services, and what are the operational pitfalls?

**Model Answer:**

For inter-service communication that must never traverse the public internet, I use AWS PrivateLink (VPC Endpoints) to expose AWS-managed services and internal Platform services to the EKS VPC. Key design decisions:

- **VPC Endpoint placement:** Create Interface Endpoints (e.g., for ECR, S3, STS, Secrets Manager, ELB, EC2) in each AZ where EKS nodes run; missing an AZ endpoint causes asymmetric routing failures and subtle DNS resolution gaps.
- **DNS resolution:** Enable `enableDnsSupport` and `enableDnsHostnames` on the VPC; Route 53 Private Hosted Zones or endpoint-specific private DNS must resolve service hostnames to endpoint ENI IPs — misconfigured PHZs are the #1 PrivateLink support ticket.
- **Security Groups on endpoints:** Lock endpoint SGs to the node and pod CIDR ranges only; overly broad rules undermine the isolation goal.
- **Cross-cluster traffic:** For EKS-to-EKS communication across accounts or VPCs, expose services via NLB + PrivateLink rather than VPC peering; this avoids overlapping CIDR conflicts and provides per-service access control.
- **Gateway Endpoints vs. Interface Endpoints:** S3 and DynamoDB support free Gateway Endpoints (route-table based); prefer these over Interface Endpoints for cost on high-throughput workloads.
- **Operational pitfall — endpoint policy drift:** VPC Endpoint resource policies are separate from IAM; forgetting to scope them allows any principal in the VPC to call the service. Enforce policies via AWS Config rules and SCP guardrails.
- **Fargate consideration:** Fargate pods require the ECR, S3, STS, and Secrets Manager endpoints to be present; missing endpoints silently prevent pod startup with opaque "ImagePullBackOff" or credential errors.

---

### Q: Your EKS pods intermittently lose connectivity to an RDS Aurora cluster for 30–60 seconds, then self-recover. How do you diagnose and eliminate the root cause?

**Model Answer:**

This pattern — brief, self-healing connectivity loss — has several common causes in EKS and requires layered investigation:

1. **Establish a baseline:** Deploy a sidecar or DaemonSet-based TCP prober (e.g., `tcping` or a Prometheus blackbox exporter) hitting the Aurora writer endpoint every second, correlated with timestamps to match application error logs precisely.
2. **Check Aurora failover events:** In the RDS console and CloudWatch Events, look for Multi-AZ failovers or Aurora writer re-elections — these cause a DNS TTL flush period (typically 30–40 s) during which old connections time out.
3. **Connection pool behavior:** Many ORMs and connection pools cache the Aurora DNS endpoint IP; after a failover the pool holds stale connections. Fix: set connection TTL/validation (`testOnBorrow`, `keepalive`) and respect the RDS DNS TTL of 5 s in the pool config.
4. **Security Group rule evaluation:** Spot check that pod CIDR ranges (especially if using custom networking or Prefix Delegation) are covered by the Aurora SG inbound rule; a recent node scaling event expanding IP space can expose gaps.
5. **NAT Gateway SNAT port exhaustion:** If pods route through a NAT GW to reach RDS (not recommended), check `ErrorPortAllocation` CloudWatch metric; port exhaustion causes silent drops.
6. **VPC DNS throttling:** The `.2` resolver has a 1,024 packets/second/ENI limit; bursts of DNS lookups at scale cause query drops. Mitigation: enable Route 53 Resolver DNS Firewall logging, and use NodeLocal DNSCache.
7. **Resolution:** Use Aurora Proxy (RDS Proxy) to absorb failover events transparently, enforce connection pool limits at the proxy layer, and switch to persistent keep-alive connections with exponential backoff in the application.

---

### Q: How do you design an EKS platform team operating model — including cluster fleet topology, self-service developer experience, and guardrails — for an organisation with 50+ engineering teams?

**Model Answer:**

At this scale the platform team becomes a product team; the design spans topology, tooling, and culture:

**Cluster topology strategy:**
- Use a **hub-and-spoke** model: shared platform services (observability, service mesh control plane, CI runners) in a dedicated cluster; per-domain or per-environment clusters for tenant workloads. This balances blast radius isolation against operational overhead.
- Define a **cluster tier taxonomy** (e.g., Tier 1 = prod critical, Tier 2 = prod non-critical, Tier 3 = non-prod) with different SLOs, upgrade cadences, and cost allocations per tier.

**Self-service developer experience:**
- Expose cluster provisioning via an Internal Developer Portal (Backstage) backed by a Terraform/Crossplane GitOps pipeline; teams submit PRs, not tickets.
- Provide opinionated Helm chart libraries or Kustomize bases that embed security defaults (non-root, read-only FS, resource limits); teams extend, not override from scratch.
- Namespace-as-a-Service: automate namespace creation with RBAC, NetworkPolicy, ResourceQuota, and LimitRange templates via a controller (e.g., Hierarchical Namespace Controller).

**Guardrails:**
- Enforce policy via **Kyverno or OPA/Gatekeeper** in `Enforce` mode for must-have controls (image registry allowlist, no `latest` tags, required labels); use `Audit` mode for advisory policies with automated PR comments.
- SCPs and IAM permission boundaries prevent teams from bypassing IRSA constraints.
- Automated CIS/NSA benchmark scans (Trivy, kube-bench) as part of the cluster provisioning pipeline gate.

**Operational concerns:**
- Maintain a **golden AMI pipeline** using EC2 Image Builder; nodes launch only from validated, patched AMIs.
- Define a platform SLO (e.g., control-plane API p99 < 1 s, node provisioning < 5 min) and publish it on an internal status page to create accountability.
- Hold a monthly **platform review** with team leads covering cost attribution, policy violations, and roadmap — treating internal teams as customers.

---

### Q: Walk me through how you would implement and operationalise fine-grained network segmentation for EKS workloads using both Kubernetes NetworkPolicy and AWS-native controls, and explain where each layer is insufficient alone.

**Model Answer:**

Defense-in-depth for EKS network segmentation requires three complementary layers:

**Layer 1 — Kubernetes NetworkPolicy (pod-to-pod):**
- Requires a CNI that enforces NetworkPolicy; with VPC CNI, you must enable the **Network Policy Controller** (GA in EKS 1.29+) or use a policy-aware overlay like Calico or Cilium.
- Default-deny posture per namespace (`ingress: []`, `egress: []`) then explicit allow rules. Policies are namespace-scoped and cannot control traffic leaving the node to AWS services.
- **Limitation:** NetworkPolicy has no concept of FQDN-based egress (you can't write "allow egress to `api.stripe.com`"); for that you need Cilium's `CiliumNetworkPolicy` or an egress proxy.

**Layer 2 — Security Groups for Pods (SGP):**
- With VPC CNI's `ENABLE_POD_ENI=true`, individual pods get a branch ENI and can be assigned a dedicated Security Group.
- This allows SG-based rules between pods and AWS resources (RDS, ElastiCache, MSK) — the cleanest way to scope DB access without CIDR-based rules that drift as node IPs change.
- **Limitation:** SGP requires Nitro instances; not supported on Fargate with the same model; adds ENI branch limit pressure per node.

**Layer 3 — VPC-level controls (NACLs, route tables):**
- NACLs provide stateless subnet-level segmentation; useful as a coarse backstop (e.g., blocking all inter-VPC traffic not explicitly routed), but too blunt for pod-level policy.
- AWS


---

## 🗓️ Added 2026-09-08 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-08 18:17 -->

### Q: How do you design an EKS cluster bootstrap and node initialisation strategy to ensure nodes are security-hardened and configuration-compliant before they accept workloads?

**Key points an interviewer wants to hear:**

- Use **custom AMIs built with EC2 Image Builder or Packer**, baking in CIS-hardened OS configurations, approved kernel versions, and pre-pulled pause/critical images — rather than relying on userdata alone against the EKS-optimised Amazon Linux 2/AL2023 base.
- Apply **Karpenter `NodeClass` or managed node group launch templates** to inject userdata that runs a hardening script (e.g., disabling unused kernel modules, setting `auditd` rules, configuring `/etc/sysctl.d`) *before* `bootstrap.sh` registers the node with the control plane.
- Gate workload scheduling with a **startup taint** (e.g., `node.kubernetes.io/not-ready` plus a custom `bootstrapping:NoSchedule` taint) removed only after a DaemonSet-based compliance agent (e.g., a Falco/Inspector agent or custom init container) validates the node and calls the Kubernetes API to remove the taint.
- Enforce **SSM Agent presence** and enrol nodes into AWS Systems Manager for patch compliance tracking; block nodes that miss SSM heartbeats via a Lambda-driven Node auto-remediation loop.
- Integrate **Amazon Inspector container scanning** and **EC2 scanning** so newly launched nodes are assessed within seconds; couple this with EventBridge rules that cordon or drain nodes flagged with critical CVEs above a configurable CVSS threshold.
- Store the golden AMI ID in **SSM Parameter Store** and reference it in Terraform/CDK so all node groups always pull the latest approved image; failed AMI validation in CI blocks the parameter update.
- **Behavioral angle:** Be ready to discuss a specific case where a misconfigured userdata script caused nodes to register but fail kubelet TLS bootstrap, and how you used `cloud-init` logs via SSM Session Manager to diagnose it without SSH access.

---

### Q: How do you design an EKS strategy for batch and queue-driven workloads — such as data-processing pipelines — and what are the trade-offs between Kubernetes Jobs, Kueue, and purpose-built AWS services like AWS Batch?

**Key points an interviewer wants to hear:**

- **Kubernetes Jobs + Karpenter** suit teams that need tight Kubernetes-native integration (shared RBAC, namespaces, IRSA, pod-level observability) and tolerate some framework overhead; Karpenter's `consolidationPolicy` and `expireAfter` handle ephemeral node lifecycle cleanly.
- **Kueue** adds gang-scheduling, quota management, and workload priority across namespaces — essential when multiple teams compete for GPU/CPU burst capacity; it integrates with JobSet for distributed training without a separate scheduler.
- **AWS Batch with EKS compute environments** offloads job queue management, fair-share scheduling, and array job orchestration to the managed service while still running containers on EKS nodes; best when the organisation already owns Batch expertise or needs cost-allocation reporting per job queue.
- Key trade-off: AWS Batch abstracts retry logic and dependency graphs (via Step Functions integration) but couples you to AWS APIs and limits pod-level Kubernetes scheduling flexibility (affinity, topology spread).
- For **high-throughput, short-duration jobs** (seconds to minutes), Kubernetes Job overhead (API server write amplification, etcd pressure) becomes significant; consider chunking via indexed Jobs and setting conservative `ttlSecondsAfterFinished` to reduce object churn.
- Pair any batch strategy with **Spot Instances for cost** but design jobs to be **checkpointable** (S3 or EFS intermediate state) and use `terminationGracePeriodSeconds` with SIGTERM handlers to flush in-flight work before Spot reclamation.
- **Observability:** emit custom CloudWatch or Prometheus metrics on queue depth, job age, and failure rate; set HPA on the job-dispatch component if using a work-queue pattern (e.g., SQS-triggered consumers).

---

### Q: A security team reports that a compromised pod in your EKS cluster has attempted a lateral movement attack by querying the EC2 Instance Metadata Service (IMDS) to harvest node IAM credentials. How do you contain the incident and harden the cluster long-term?

**Immediate containment:**

1. **Isolate the pod** — apply a `NetworkPolicy` denying all egress/ingress and, if needed, cordon and drain the node to prevent scheduling new workloads there; preserve the node for forensics before terminating.
2. **Revoke / rotate** the node's IAM instance profile credentials via IAM's `deny` condition on `aws:TokenIssueTime`; invalidate any IMDS-derived STS tokens by attaching an explicit Deny policy scoped to the node role.
3. Capture pod filesystem snapshot, memory dump (via `kubectl exec` or Falco-triggered Lambda), and CloudTrail events in the blast-radius window.

**Root-cause & hardening:**

- The fundamental exposure is that **IMDSv1 was enabled** or **hop-limit was ≥ 2**, allowing containers to reach `169.254.169.254`. Enforce **IMDSv2-only with hop-limit = 1** in all launch templates so container-originated IMDS calls are dropped at the hypervisor.
- Implement **IRSA / EKS Pod Identity** for all workloads so pods never need node-level credentials; audit via AWS Config rule `ec2-instance-profile-attached` and a custom rule checking that no pod mounts the default service account with `automountServiceAccountToken: true` unnecessarily.
- Deploy **Falco** with the `aws_metadata_service_access` rule to alert in real time when any process inside a container queries the IMDS endpoint.
- Enforce **restricted Pod Security Standards** (no `hostNetwork`, no privileged containers) and **OPA/Kyverno policies** blocking `hostPID` and `hostIPC`, which are common pivot points post-IMDS compromise.
- Review **VPC security groups** on nodes — outbound to `169.254.169.254` should be restricted, and consider a VPC endpoint for SSM/S3 to eliminate internet egress paths the attacker might exploit.

---

### Q: How do you design an EKS platform for regulated financial services workloads that must comply with PCI-DSS and achieve sub-100 ms p99 latency SLAs simultaneously — and where do compliance and performance requirements conflict?

**Architecture pillars:**

- **Network segmentation:** Run the cardholder data environment (CDE) workloads in **dedicated node groups within private subnets**, separated from non-CDE workloads by distinct VPCs and AWS Network Firewall; use VPC endpoints for all AWS service communication to eliminate internet traversal.
- **Encryption in transit:** Enforce mTLS via a service mesh (Istio/App Mesh) for all east-west traffic — PCI DSS Req 4 demands encryption of CHD in transit, but mTLS sidecar overhead adds **1–5 ms per hop**; mitigate by tuning Envoy connection pools, enabling HTTP/2 multiplexing, and co-locating tightly coupled services via pod topology spread within the same AZ.
- **Encryption at rest:** Use **EBS volumes with CMK-backed KMS encryption** for any persistent CHD; the per-I/O KMS call adds latency — offset by enabling **KMS request caching** in the CSI driver and choosing `io2 Block Express` volumes for consistent sub-1 ms storage latency.
- **Logging and audit:** PCI requires tamper-evident audit logs (Req 10); stream all pod logs and Kubernetes audit logs to **CloudWatch Logs with S3 Object Lock (WORM)** — but high-volume log shipping can saturate the node's network interface; use **Fluent Bit with async buffering and back-pressure** to isolate logging I/O from application traffic.
- **Conflict: least-privilege vs. automation speed.** PCI change control (Req 6) demands peer review and approval workflows that can slow deployment pipelines; resolve by implementing **GitOps with required PR approvals** and automated compliance gates (OPA Conftest in CI) so policy checks are fast and human review is scoped to risk-tiered changes only.


---

## 🗓️ Added 2026-09-09 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-09 18:17 -->

### Q: How do you design an EKS cluster observability strategy for cost attribution and chargeback across multiple teams sharing a cluster?

**Key points an interviewer wants to hear:**

- **Label discipline is foundational**: enforce namespace-level and pod-level labels (`team`, `cost-center`, `environment`) via admission webhooks (OPA/Gatekeeper or Kyverno) so every resource is attributable before it lands in the cluster.
- **Metrics pipeline**: deploy Kubecost or OpenCost alongside Prometheus; both ingest node pricing from AWS Cost and Usage Reports (CUR) and apply proportional allocation based on CPU/memory requests vs. actual usage, with idle cost distribution configured per policy (shared equally, proportional, or charged to a "platform" cost center).
- **Spot and Savings Plan amortisation**: normalise EC2 pricing in the tool so Spot savings are not silently absorbed by the platform team—map instance lifecycle to pod scheduling events.
- **Network egress attribution**: tag VPC flow logs with pod metadata using the AWS VPC CNI's ENI-tagging feature and correlate with CUR line items; egress is often the largest surprise cost.
- **Showback vs. chargeback**: start with showback dashboards (Grafana + Kubecost API) shared with teams weekly; move to chargeback only after label hygiene is consistently above ~95% coverage, otherwise teams dispute numbers and trust collapses.
- **Storage and data-transfer costs**: surface EBS/EFS PVC costs by cross-referencing PersistentVolume names with AWS volume IDs in CUR; often missed in Kubernetes-only tooling.
- **Governance**: publish allocation policies in your platform runbook, review monthly with team leads, and feed anomalies back into capacity planning.

---

### Q: A critical EKS workload shows correct pod logs but customers report partial request failures that never appear in application traces. How do you diagnose and resolve gaps in your distributed tracing pipeline?

**Key diagnostic steps:**

1. **Sampling rate audit**: check whether the tracing SDK (X-Ray, OTEL Collector) is configured with a sampling rate that drops spans before they reach the backend—partial failures at low RPS are often silently discarded by head-based sampling.
2. **Collector pipeline health**: inspect OTEL Collector `receivers`, `processors`, and `exporters` metrics (`otelcol_exporter_send_failed_spans`); a misconfigured batch processor or queue overflow will silently drop spans without pod-level errors.
3. **Context propagation gaps**: verify W3C TraceContext or B3 headers are propagated across *every* hop—ALB, service mesh sidecars, async SQS consumers, and Lambda invocations all commonly break trace context; use `X-Amzn-Trace-Id` passthrough on ALB and confirm the SDK reads it.
4. **Sidecar resource starvation**: if using a sidecar collector pattern, check that the sidecar container has sufficient CPU/memory limits; under load it can queue-drop spans while the main container appears healthy.
5. **Clock skew**: nodes with significant NTP drift cause spans to appear out-of-order or be rejected by the backend's time-window validation; confirm `chrony` is running on nodes and check CloudWatch `NTPSkew` metric.
6. **Resolution**: implement tail-based sampling for error traces to guarantee 100% capture of failed requests regardless of overall sample rate; add collector self-observability dashboards and alert on `drop_rate > 0`.

---

### Q: How do you design an EKS platform to support safe, progressive multi-cluster canary releases where traffic is shifted across clusters rather than within a single cluster?

**Architecture and trade-offs:**

- **Global load balancing layer**: use Route 53 weighted routing or AWS Global Accelerator endpoint weights to split traffic between two EKS clusters (stable and canary) at the DNS/anycast layer; this avoids in-cluster traffic-splitting complexity and works for any protocol.
- **Cluster parity guarantee**: both clusters must run identical Kubernetes versions, add-on versions, and node AMIs; a GitOps source of truth (Flux/ArgoCD with cluster-scoped ApplicationSets) ensures configuration drift doesn't confound canary signal.
- **Observability alignment**: each cluster emits metrics with a `cluster_role=canary|stable` label; a unified Grafana dashboard overlays error rate, latency, and saturation for direct comparison—this is your promotion gate.
- **Automated promotion/rollback**: a promotion controller (Argo Rollouts cross-cluster plugin or a custom Lambda) reads the Grafana/CloudWatch metric API, adjusts Route 53 weights incrementally (5% → 20% → 50% → 100%), and rolls back by flipping weight to 0 if the error budget burns too fast.
- **Stateful workload challenge**: databases must be readable from both clusters simultaneously during the shift; use Aurora Global Database with read endpoints or ensure the canary cluster writes to the same primary with latency accounted for in SLO definition.
- **Trade-off**: cross-cluster canary doubles running compute cost during the window and adds DNS TTL latency to rollback (mitigate with low TTLs and Global Accelerator's near-instant weight propagation); it is most justified for high-blast-radius changes like runtime or CNI upgrades.
- **Cleanup**: automate decommission of the canary cluster post-promotion via Terraform pipelines to avoid zombie clusters accumulating cost.

---

### Q: Describe a time you had to make a significant architectural decision on EKS under uncertainty, where the right answer wasn't clear. How did you frame the decision and what was the outcome?

**What a strong answer demonstrates:**

- **Structured ambiguity handling**: name a concrete decision (e.g., choosing between Karpenter in early GA vs. Cluster Autoscaler for a 500-node production fleet, or adopting EKS Pod Identity before broad tooling support existed).
- **Decision framework**: explain how you decomposed uncertainty into *knowable now* vs. *unknowable without experimentation*—used a time-boxed spike (1–2 weeks) to validate the riskiest assumption rather than making a fully speculative choice.
- **Stakeholder alignment**: describe how you communicated the trade-off to non-technical stakeholders using a lightweight ADR (Architecture Decision Record) with explicit reversibility cost—not just a Slack message.
- **Outcome and learning**: be honest about partial success or unexpected complications (e.g., "Karpenter's consolidation caused a brief surge in pod evictions during a high-traffic window that we hadn't load-tested for"), and explain what observability gaps you closed as a result.
- **Reversibility as a first-class criterion**: strong candidates mention they weighted reversibility heavily under uncertainty—choosing the option that was cheaper to undo if wrong, even if slightly less optimal if right.
- **Red flags to avoid**: claiming certainty you didn't have, not mentioning how you validated the decision, or describing a purely solo decision without cross-functional input.


---

## 🗓️ Added 2026-09-10 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-10 18:04 -->

### Q: How do you design an EKS strategy for Windows node workloads running alongside Linux nodes, and what are the key operational constraints?

**Model Answer:**

EKS supports Windows nodes via managed node groups running Windows Server Core AMIs, but they introduce meaningful constraints that must be planned for deliberately.

Key design points:
- **Node isolation**: Windows nodes cannot run Linux system pods (CoreDNS, aws-node, kube-proxy variants differ), so you must taint Windows nodes (e.g., `os=windows:NoSchedule`) and use `nodeSelector`/tolerations to prevent Linux workloads landing on them. A Linux node group must always co-exist to host cluster-critical DaemonSets.
- **CNI limitations**: The Amazon VPC CNI on Windows does not support all features available on Linux — notably, Network Policy enforcement requires a separate solution (e.g., Calico for Windows or NPN). IPv6 is unsupported on Windows nodes as of recent releases.
- **AMI patching cadence**: Windows AMIs are significantly larger and patch cycles are longer. Use SSM Patch Manager or bake custom AMIs with EC2 Image Builder; node recycling windows must account for longer drain times due to Windows graceful shutdown behaviour.
- **Licensing and cost**: Windows nodes carry an additional OS licensing surcharge on EC2. Right-size carefully and favour Savings Plans over Spot (Spot interruption handling on Windows is less mature).
- **Image pull latency**: Windows container base images are large (2–6 GB). Pre-pull images on node startup using a DaemonSet or bake them into the AMI to avoid cold-start latency impacting pod scheduling SLAs.
- **Monitoring**: CloudWatch Container Insights has partial Windows support; supplement with Prometheus windows-exporter for node-level metrics.

The honest architectural recommendation is to minimise Windows node usage, containerising only workloads that genuinely cannot be ported, and to treat the Windows node pool as a secondary fleet with its own lifecycle policy.

---

### Q: A team's EKS workload passes all load tests in staging but suffers from severe thundering-herd startup failures in production during a cold deployment. How do you diagnose and remediate this?

**Model Answer:**

Thundering-herd on cold deployment typically manifests as a burst of pods starting simultaneously, overwhelming a downstream dependency (database, cache, external API, or the Kubernetes API itself), causing cascading failures that look like an application bug.

**Diagnosis steps:**
1. Correlate pod `startedAt` timestamps with downstream error spikes — if all pods become ready within a 5-second window and errors begin immediately, the pattern is clear.
2. Check if connection pool exhaustion is occurring at the database layer (RDS `DatabaseConnections` CloudWatch metric, `max_connections` on Aurora).
3. Review application startup code for synchronous cache warm-up or schema migration calls executed by every replica simultaneously.
4. Check HPA/Karpenter scaling events — a sudden scale-out after a deployment can compound the effect.

**Remediation:**
- **Stagger pod startup**: Use `minReadySeconds` on the Deployment to slow rolling updates, or reduce `maxSurge` to limit simultaneous new pods.
- **Add jitter in application startup**: Introduce a randomised sleep (50–500 ms) before the application opens connections or warms caches.
- **Decouple schema migrations**: Run migrations as a pre-upgrade Helm hook Job, not at application startup.
- **Connection pooling proxy**: Front RDS with RDS Proxy to absorb connection burst without hitting `max_connections`.
- **Rate-limit readiness**: Use a custom readiness probe with back-off so pods don't all become Ready (and start receiving traffic) at the identical instant.
- **Staging parity**: Replicate production replica counts and downstream connection limits in staging to expose the pattern before promotion.

---

### Q: How do you design an EKS cluster topology and scheduling strategy to support strict data-residency requirements where certain workloads must never leave a specific AWS Availability Zone?

**Model Answer:**

Data-residency at the AZ level (rather than region level) is an unusual but real requirement, typically driven by latency guarantees for local data stores or regulatory interpretations of "zone" as a physical boundary.

**Topology design:**
- Create **per-AZ node groups** with explicit AZ labels (e.g., `topology.kubernetes.io/zone=eu-west-1a`) and taint them so only intentional workloads schedule there (e.g., `az-pinned=eu-west-1a:NoSchedule`).
- Use `nodeAffinity` with `requiredDuringSchedulingIgnoredDuringExecution` — not `preferred` — to make AZ pinning a hard constraint, not a hint.
- Set `topologySpreadConstraints` with `whenUnsatisfiable: DoNotSchedule` scoped to the target zone to prevent the scheduler from spreading replicas across zones.

**Storage**: Ensure PVCs use `WaitForFirstConsumer` binding mode so the EBS volume is provisioned in the same AZ as the pod; use a StorageClass with `allowedTopologies` restricted to that AZ.

**Networking**: If the workload communicates with a zonal Aurora replica or ElastiCache node, configure the Service's `topologyKeys` or use AWS Local Zones / Outposts if the requirement extends beyond AZ to physical location.

**Operational risks to communicate**:
- Single-AZ designs sacrifice Kubernetes' default HA model; an AZ outage takes down the pinned workload entirely.
- Cluster Autoscaler and Karpenter must be configured with matching AZ constraints to avoid provisioning replacement capacity in the wrong zone.
- Document the business justification and accept the availability trade-off explicitly in an Architecture Decision Record.

---

### Q: Describe how you would design an EKS-based platform to support secure, isolated development environments (per-developer or per-feature-branch) without runaway cost or cluster sprawl.

**Model Answer:**

Per-developer or per-branch environments ("preview environments") on EKS require balancing isolation, speed, and cost — getting any one wrong makes the platform unusable or unaffordable.

**Namespace-per-environment model (preferred for most cases):**
- Provision a dedicated namespace per branch/developer using a GitOps controller (Argo CD `ApplicationSet` with a `git` generator keyed on branch name or PR number).
- Apply `ResourceQuota` and `LimitRange` per namespace to cap CPU/memory; use Karpenter with node consolidation enabled so idle environments don't hold warm nodes.
- Use `NetworkPolicy` to enforce namespace isolation — environments should not communicate laterally.
- Inject environment-specific config via Helm values or Kustomize overlays parameterised on branch name.

**Cost controls:**
- Schedule a CronJob or use a Kubernetes operator (e.g., `kube-janitor`) to delete namespaces after a TTL (e.g., 48 hours of inactivity) or on PR close via a CI webhook.
- Use Spot instances for the dev-environment node pool; dev workloads tolerate interruption.
- Share cluster-level services (ingress controller, observability stack, image pull cache) across all environments rather than replicating per namespace.

**Isolation trade-offs**: Namespace isolation is logical, not hard; for stricter isolation (e.g., if environments run customer data in testing), consider vcluster (virtual clusters) to provide API server-level isolation within a single physical cluster, at the cost of slightly higher resource overhead and operational complexity.

**Ingress**: Use wildcard DNS (`*.dev.internal.example.com`) with a single ALB and host-based routing rules auto-generated per environment, so each branch gets a unique URL without provisioning new load balancers.


---

## 🗓️ Added 2026-09-11 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-11 18:09 -->

### Q: How do you design an EKS cluster strategy for extremely latency-sensitive workloads — such as high-frequency trading or real-time bidding — where microsecond-level jitter is unacceptable?

**Model Answer:**

- **Node placement**: Use dedicated tenancy EC2 instances (`--instance-tenancy dedicated`) or bare-metal instance types (e.g., `c6i.metal`) to eliminate noisy-neighbour effects; pin workloads to specific AZs to avoid cross-AZ latency.
- **CPU isolation**: Use `static` CPU Manager policy and Guaranteed QoS pods (matching `requests == limits`) so the kubelet pins threads to dedicated physical cores; disable CPU throttling via cgroup v2 tuning.
- **NUMA awareness**: Enable Topology Manager (`best-effort` or `restricted` policy) alongside Memory Manager so the kernel scheduler respects NUMA locality for both CPU and memory.
- **Kernel and OS tuning**: Use a custom AMI (via Bottlerocket or Ubuntu with PREEMPT_RT patch) with tuned IRQ affinity, disabled transparent huge pages, and SR-IOV / ENA Express enabled for sub-100 µs NIC latency.
- **Networking**: Place producer and consumer pods in the same placement group (cluster placement group) to minimise intra-rack hops; use host networking (`hostNetwork: true`) to bypass the CNI overlay stack where latency budgets demand it.
- **Scheduler hints**: Use `podAffinity` with `topologyKey: kubernetes.io/hostname` to co-locate communicating pods; set `priorityClass` to guarantee eviction order under pressure.
- **Observability**: Instrument with eBPF-based tools (e.g., Cilium Hubble, `bpftrace`) for nanosecond-resolution latency histograms rather than application-level metrics that add overhead.
- **Trade-off**: These optimisations reduce scheduling flexibility and increase cost significantly; validate with production-representative load before committing to the architecture.

---

### Q: A cluster operator reports that Karpenter is repeatedly launching and terminating nodes in a tight loop — "thrashing" — causing instability and elevated AWS costs. How do you diagnose and resolve this?

**Model Answer:**

Karpenter thrashing typically results from a mismatch between provisioned node capacity and workload consolidation or disruption settings. Systematic approach:

1. **Check disruption budget and consolidation config**: Review `NodePool` `disruption.consolidationPolicy` and `consolidateAfter` — overly aggressive consolidation (e.g., `consolidateAfter: 0s`) causes Karpenter to remove nodes before pods fully migrate, triggering re-provisioning.
2. **Inspect node TTL vs. pod startup time**: If `expireAfter` is shorter than application startup + readiness probe time, nodes expire before workloads stabilise, causing a perpetual cycle.
3. **Look for anti-affinity/topology conflicts**: Pods with `podAntiAffinity` requiring unique nodes may prevent bin-packing; Karpenter terminates under-utilised nodes but the displaced pods immediately force new single-pod nodes.
4. **Review NodePool label/taint drift**: If a `NodePool` selector changed mid-flight, existing nodes no longer match and Karpenter decommissions them while simultaneously provisioning replacements — ensure label changes are batched.
5. **Check Spot interruption handling**: Rapid Spot interruptions (via EC2 Instance Rebalance or ITN) paired with narrow instance-type diversification triggers constant replacement; widen `instanceFamily` or add On-Demand fallback.
6. **Remediation**: Set `disruption.budgets` with a `maxUnavailable` cap, tune `consolidateAfter` to `≥ 1m`, and enable `do-not-disrupt` annotations on stateful or slow-starting pods during diagnosis.
7. **Metrics to watch**: `karpenter_nodes_terminated_total`, `karpenter_nodes_created_total`, and CloudWatch EC2 `RunInstances`/`TerminateInstances` API call rates are the fastest indicators.

---

### Q: How do you design an EKS platform to support safe, zero-downtime schema migrations for stateful services that use relational databases, where both old and new pod versions coexist during a rolling deployment?

**Model Answer:**

This is a classic **expand/contract** (a.k.a. parallel-change) pattern problem applied to Kubernetes rolling deployments:

- **Expand phase**: Write migrations that are *backward-compatible* — add nullable columns, new tables, or indexes without dropping or renaming existing ones. The old pod version continues to function against the migrated schema.
- **Migration job gating**: Use a Kubernetes `Job` or an init container in the new `Deployment` that runs `alembic upgrade head` / `flyway migrate` *before* new pods become ready. Gate with a `preStop` hook on old pods only after the job succeeds, preventing simultaneous migration runs. Use a distributed lock (e.g., via Postgres advisory lock) to serialise multi-pod job execution.
- **Deployment strategy**: Configure `maxSurge: 1, maxUnavailable: 0` to ensure old pods only terminate after new pods pass readiness probes, guaranteeing overlap exists only during the transition window.
- **Contract phase**: In a *subsequent* deployment (decoupled release), remove deprecated columns or rename once all old pod instances are gone — never in the same release.
- **Feature flags**: Wrap application code that references new schema objects in feature flags so both versions can be deployed from a single artefact; avoids branching deployment pipelines.
- **Rollback design**: Migrations must be *reversible* (down migrations) or the rollback strategy must be data-loss-free (e.g., re-adding a dropped column as nullable). Document rollback SLOs explicitly.
- **EKS-specific tooling**: Use Argo Rollouts `prePromotionAnalysis` to run schema validation smoke tests before promoting the stable ReplicaSet, automatically aborting if validation fails.

---

### Q: Describe how you would design an EKS platform governance model — including policy guardrails, admission controls, and audit mechanisms — for a large enterprise with hundreds of development teams operating under a hub-and-spoke cluster topology.

**Model Answer:**

Governance at enterprise scale requires layered, automated controls rather than manual review:

- **Policy-as-code via OPA/Gatekeeper or Kyverno**: Define a central `ConstraintTemplate` library (stored in a governed Git repo) covering mandatory labels, image registry allowlists, resource request/limit requirements, and prohibited capabilities. Sync to all spoke clusters via GitOps (Flux or ArgoCD App-of-Apps). Kyverno is preferred for teams that find Rego opaque — it uses Kubernetes-native YAML policies.
- **Admission webhook tiering**: Separate policies into `deny` (hard guardrails — e.g., no `privileged: true`, no `latest` tags), `warn` (advisory — e.g., missing liveness probes), and `audit` (logging-only for new policy rollout). This prevents policy changes from causing sudden breakages.
- **Namespace-scoped delegation**: Hub cluster hosts a `PlatformTeam` namespace with cluster-scoped resources; spoke namespaces are owned by dev teams. Use `HierarchicalNamespaceController` (HNC) or Capsule/vCluster for safe namespace-level tenancy boundaries so platform team policies propagate automatically to child namespaces.
- **Audit and compliance reporting**: Enable EKS API server audit logs to CloudWatch Logs with a structured query layer (Athena or OpenSearch); build weekly compliance dashboards from `kubectl get constraint -o json` policy violation counts. Export to a centralised SIEM for SOC visibility.
- **Change management for guardrails**: Policy changes go through a PR process with mandatory review by a Platform Architecture Board; new `deny` policies are deployed in `warn` mode for a 30-day soak period, with violation counts tracked and communicated to teams before enforcement.
- **Developer self-service**: Publish a developer portal (Backstage) with policy documentation, a policy simulator (OPA Playground integrated with the live `ConstraintTemplate` library), and a `ValidatingAdmissionPolicy` dry-run CLI tool so teams can validate manifests locally before CI.
- **Escape-hatch process**: Define a formal exception workflow (ticketed, time-bounded, CISO-approved


---

## 🗓️ Added 2026-09-12 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-12 17:41 -->

### Q: How do you design an EKS strategy for graceful pod disruption during node maintenance, and what are the common failure modes that cause SLA breaches?

**Model Answer:**

Graceful disruption depends on the correct interplay of several Kubernetes primitives working together:

- **PodDisruptionBudgets (PDBs):** Define `minAvailable` or `maxUnavailable` so the eviction API blocks unsafe drains; a common mistake is setting `maxUnavailable: 0` on every deployment, which deadlocks rolling node replacements entirely.
- **Termination grace period:** Set `terminationGracePeriodSeconds` to reflect actual shutdown time — not the default 30 s. Applications must trap SIGTERM and drain in-flight requests; missing this causes 502s during Kubernetes-initiated evictions.
- **`preStop` hooks:** Add a short sleep (`preStop: exec sleep 5`) to absorb the lag between pod removal from endpoints and load-balancer deregistration propagating through kube-proxy or AWS Target Groups — this is the single most common source of brief 502 spikes during drains.
- **Node drain ordering with Karpenter/CA:** Karpenter respects PDBs during voluntary disruption via the `Disruption` budget API; CA uses the eviction API. Validate both paths in staging with chaos tooling (e.g., `karpenter.sh/do-not-disrupt` annotation tests).
- **Common failure modes:** PDB misconfiguration blocking drains indefinitely; `minReadySeconds` not set, causing premature traffic routing to cold pods; ALB target deregistration delay not matching `terminationGracePeriodSeconds`; and missing `topology.kubernetes.io/zone` spread constraints causing all replicas to be co-located and simultaneously evicted.
- **Operational hygiene:** Automate drain validation in CI by running `kubectl drain --dry-run` against staging clusters; alert on stuck PDB-blocked drains exceeding a threshold.

---

### Q: A multi-tenant EKS cluster starts hitting the 110-pod-per-node limit on several nodes, causing scheduling failures. How do you systematically address this without emergency cluster expansion?

**Model Answer:**

The 110-pod limit is a hard kernel/kubelet constraint (also constrained by ENI secondary IP capacity on VPC CNI), so the fix has both immediate and architectural layers:

**Immediate triage:**
- Run `kubectl describe nodes | grep -A5 "Allocatable"` and cross-reference pod counts per node with `kubectl get pods -A -o wide | awk '{print $8}' | sort | uniq -c | sort -rn`.
- Identify daemon-set overhead — every DaemonSet pod counts against the limit; audit and remove unnecessary DaemonSets (logging agents, monitoring collectors that can be consolidated).

**Short-term mitigations:**
- Increase `max-pods` per node by switching to **prefix delegation** on VPC CNI (`ENABLE_PREFIX_DELEGATION=true`), which dramatically increases available IP slots per ENI and allows raising `max-pods` to 250+ on nitro instances — no cluster expansion needed.
- Move batch or burst workloads to Fargate or dedicated Karpenter node pools with smaller instance types (more nodes, same total capacity, higher aggregate pod ceiling).

**Architectural remediation:**
- Right-size requests so the scheduler prefers fewer, larger nodes for compute-heavy pods and reserves pod-dense nodes for lightweight services.
- Introduce **Karpenter NodePool constraints** that select instance families with higher ENI/IP density (e.g., `m5.4xlarge` vs `m5.large`) for namespaces expected to run many small pods.
- Establish a platform policy: pod-per-node utilisation is a tracked capacity metric surfaced via observability dashboards, with alerts at 80% of the limit.

---

### Q: How do you design an EKS strategy for handling API deprecations across Kubernetes minor-version upgrades, and what governance mechanisms prevent deprecated APIs from blocking future upgrades?

**Model Answer:**

API deprecations are one of the leading causes of upgrade freezes in mature EKS fleets. A structured strategy has three layers:

**Detection:**
- Deploy **Pluto** (Fairwinds) or **kubent** as a CI gate that scans all Helm charts, raw manifests, and in-cluster live objects against the target Kubernetes version's removed-API list. Fail PRs that introduce deprecated API versions.
- Enable **API server audit logs** with a filter for `k8s.io/deprecated=true` to surface in-cluster usage of deprecated APIs by controllers, operators, and CRDs — things CI scanning misses.

**Remediation workflow:**
- Maintain a deprecation backlog tracked per-team in the platform team's JIRA/Linear board, auto-populated from Pluto scan results in each namespace.
- Use `kubectl convert` (or Helm `--api-versions` override) to migrate manifests; for third-party operators, track upstream release timelines and pin to versions that support the target API group.

**Governance:**
- Enforce via OPA/Gatekeeper: a policy that rejects `CREATE`/`UPDATE` of resources using removed API versions in the target minor version — applied to staging clusters first as a dry-run gate.
- Adopt a **version-skew window policy**: no workload team may be more than one minor version behind the cluster's Kubernetes version. This prevents the anti-pattern of skipping upgrades until APIs are hard-removed.
- Run a "shadow upgrade" canary cluster (same workloads, next K8s version) continuously; diff its API audit logs against production to surface surprises before the upgrade window.

**Operational tip:** EKS will block control-plane upgrades if deprecated APIs in the removed list are still in active use — treat the AWS pre-upgrade check as a lagging indicator, not the primary gate.

---

### Q: Describe how you would design an EKS-based platform to support a SaaS product where each customer requires a dedicated, isolated Kubernetes namespace with guaranteed resource quotas — and the customer count is expected to grow from 50 to 5,000 over 18 months.

**Model Answer:**

This is a namespace-per-tenant soft-multitenancy problem that hits scaling limits in both the Kubernetes control plane and the operational model well before 5,000 tenants:

**Namespace provisioning automation:**
- Build a **Tenant Controller** (CRD + controller pattern, implemented with controller-runtime) that reconciles a `Tenant` custom resource into: a namespace, `ResourceQuota`, `LimitRange`, `NetworkPolicy` (default-deny + allow-ingress-from-gateway), RBAC RoleBindings, and an IRSA-linked service account — all idempotent and GitOps-managed via Flux/ArgoCD App-of-Apps.
- Use **Helm library charts** or **Crossplane Compositions** for the tenant template to ensure consistency and allow policy updates to propagate across all tenants via a single chart version bump.

**Control-plane scaling considerations:**
- etcd key count and API server watch fan-out grow linearly with namespace count. At 5,000 namespaces, benchmark etcd performance; AWS-managed EKS etcd is opaque, so track API server latency (`apiserver_request_duration_seconds`) as a proxy.
- Consider a **cluster-per-tier model**: a fleet of clusters segmented by customer tier (free, professional, enterprise), with Karpenter handling compute elasticity within each. This bounds blast radius and etcd load per cluster.
- Use **ACM + Route53 + wildcard ALB** for tenant URL routing; avoid per-tenant load balancers (AWS account limits).

**Resource isolation:**
- `ResourceQuota` + `LimitRange` provide soft compute isolation. For noisy-neighbour CPU, evaluate **CPU Manager** policy (`static`) on dedicated node pools for premium tiers.
- `NetworkPolicy` enforces namespace egress/ingress isolation; pair with Cilium for identity-aware enforcement and observability.

**Operational at scale:**
- Automate tenant lifecycle (create, suspend, delete) with a reconciliation loop that handles partial failure gracefully (idempotent steps, status conditions on the CRD).
- Alert on `ResourceQuota` utilisation >85% per tenant namespace to trigger proactive upsell or quota expansion workflows — surface this via a per-tenant observability dashboard backed by label-scoped Prometheus recording rules.
- At 5,000 tenants, label cardinality


---

## 🗓️ Added 2026-09-13 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-13 17:54 -->

### Q: How do you design an EKS strategy for handling control-plane audit log volume at scale without incurring runaway CloudWatch costs?

EKS control-plane audit logs can easily generate hundreds of GB per day in large clusters, and the default CloudWatch Logs ingestion and retention pricing makes naive enablement extremely expensive. My approach layers **selective log-level configuration**, **log routing**, and **retention discipline**. First, I enable only the audit log types genuinely needed for compliance (`audit`, `authenticator`), suppressing `scheduler` and `controllerManager` verbosity unless actively debugging. Second, I use a **Fluent Bit DaemonSet or Kinesis Data Firehose subscription filter** on the CloudWatch log group to route high-volume audit events to S3 with Parquet conversion via Firehose, reserving CloudWatch retention (7–14 days) only for operational triage. For compliance queries I use **Athena** over the S3 sink. I apply CloudWatch metric filters to alarm on anomalous API call rates (e.g., `list secrets` spikes) so I don't need to retain everything hot. Finally, I set explicit `RetentionInDays` on all EKS log groups via IaC — an omission that is the single most common source of runaway bills — and enforce it with AWS Config.

---

### Q: How do you design an EKS platform to enforce and validate resource quotas and admission policies as a hard multi-team governance boundary, and what breaks when you get it wrong?

Resource quotas alone (`LimitRange`, `ResourceQuota`) are necessary but insufficient because they don't prevent misconfigured manifests from reaching the scheduler or enforce organisational conventions. My governance stack layers three controls. **Admission webhooks** (Kyverno or OPA/Gatekeeper) enforce policies such as mandatory resource requests/limits, disallowed host-path mounts, and required label taxonomies before objects persist — any cluster without this will see quota bypass through partially-specified pods. **Namespace-scoped ResourceQuotas** set hard CPU/memory/PVC ceilings per team namespace, sized from historical VPA recommendations rather than guesswork. **LimitRanges** set default requests/limits so pods without explicit values don't schedule as burstable or BestEffort accidentally. Common failure modes: policy webhook availability — if the webhook is not configured with `failurePolicy: Fail` and has no HA replicas, a crashing webhook takes down all admission for that scope; quota sum mismatches with actual node capacity causing systemic pending; and drift when teams create resources through `kubectl` bypassing CI pipelines. I close the last gap by restricting direct `kubectl apply` to break-glass roles and enforcing GitOps as the only write path.

---

### Q: A blue/green cluster migration on EKS (moving workloads from an old cluster to a new one) is running weeks behind schedule and causing escalating risk. How do you diagnose the bottleneck and recover the programme?

This is a classic programme failure disguised as a technical one, so I triage both dimensions simultaneously. Technically, cluster migrations stall on: **stateful workload data re-platforming** (PVC migration, replication lag, schema compatibility), **IRSA/Pod Identity role re-binding** (teams forget to update trust policies for the new OIDC issuer), **hardcoded cluster-internal DNS or endpoint references** in application config, and **admission/policy delta** between clusters causing manifest rejections on the new side. I run a **migration readiness checklist** per service: DNS portability, IAM role rebinding, external dependency allow-listing, and smoke-test coverage. To recover schedule I introduce **traffic-splitting at the load balancer layer** (weighted target groups or Route 53 weighted records) so we can migrate 5–10% of traffic per service to the new cluster incrementally rather than big-bang cutovers, decoupling migration risk from migration speed. Behaviourally, I hold a **programme retrospective mid-flight** to identify which teams are blocked on platform tooling versus their own readiness, then dedicate platform engineers as embedded migration buddies for the longest-tail teams. I also establish a hard cutover date with executive sponsorship to eliminate indefinite parallel-run cost drag.

---

### Q: How do you design an EKS strategy for running and securing AI/LLM inference workloads that have large model artefacts, long startup times, and unpredictable per-request latency profiles?

LLM inference on EKS introduces four atypical operational challenges that standard Kubernetes patterns don't address well. **Model loading latency**: containers that take 3–10 minutes to load a multi-GB model from S3 or EFS make default readiness probe timeouts and HPA reaction times dangerous. I pre-warm nodes using Karpenter node templates that mount models at launch via an init container pulling from S3 with `s3-mountpoint` or a shared EFS access point, and I set `initialDelaySeconds` and `failureThreshold` on readiness probes conservatively. **Scaling dynamics**: token-per-second throughput saturates non-linearly, so I use **KEDA with a custom SQS queue depth or GPU utilisation scaler** rather than CPU-based HPA, which is meaningless for GPU-bound inference. **Node topology**: I pin inference pods to GPU node groups (p4d, g5, inf2) using `nodeSelector` and `tolerations`, and I use `topologySpreadConstraints` to prevent model replica concentration on a single AZ. **Security**: model artefacts are IP-sensitive assets; I enforce S3 VPC endpoints with bucket policies restricting access to the pod's IRSA role, and I use network policies to isolate inference namespaces from tenant workloads. For cost, I combine On-Demand for a guaranteed baseline (to avoid cold-start on Spot interruption during active inference) with Spot for batch/offline inference jobs, separated by priority class.


---

## 🗓️ Added 2026-09-14 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-14 19:43 -->

### Q: How do you design an EKS strategy for handling IPv4 exhaustion in large VPCs, and what are the trade-offs between the available CIDR-extension approaches?

**Model Answer:**

IPv4 exhaustion is a common pain point at scale. The primary mitigations on EKS are:

- **VPC secondary CIDRs (RFC 1918 or 100.64.0.0/10 CG-NAT space):** Attach additional CIDRs to the VPC and create new subnets; the VPC CNI can assign pod IPs from these. CG-NAT space is popular because it doesn't conflict with corporate routing, but some enterprises block it at the transit gateway.
- **Prefix delegation (VPC CNI ≥ 1.9):** Instead of assigning one IP per pod, assign a /28 prefix to each ENI slot, multiplying pod density per node 16×. This is the lowest-friction win — no topology changes required — but requires Nitro instance types and inflates the size of IP reservations even if pods don't use them all.
- **Custom networking:** Separate pod and node IP spaces by routing pod traffic through secondary ENIs in different subnets. Enables using large pod subnets without touching node subnets, but adds operational complexity and disables `externalTrafficPolicy: Local` without extra care.
- **IPv6 dual-stack:** The cleanest long-term solution; pods get globally unique IPv6 addresses so exhaustion is effectively eliminated. The trade-off is that not all third-party tooling, legacy databases, or on-premises systems are IPv6-ready.

Governance: enforce subnet-size standards and prefix-delegation as defaults via a platform Helm chart and admission webhook; audit IP utilisation weekly with a Lambda querying the EC2 `DescribeSubnets` API and alert before subnets drop below a 20 % free-IP threshold.

---

### Q: A senior engineer proposes replacing all EKS managed node groups with fully self-managed node groups to gain more control. How do you evaluate and respond to this proposal?

**Model Answer:**

This is a classic control-vs-operational-burden trade-off. The key points to cover:

- **What managed node groups give you:** AWS handles node group rolling upgrades, drain sequencing, ASG lifecycle hooks, and health-check integration. Critically, `eksctl upgrade nodegroup` or console-driven upgrades drain and cordon nodes safely — removing this means you own that automation entirely.
- **Legitimate reasons to go self-managed:** Custom AMIs with kernel patches not yet in EKS-optimised AMIs, custom `kubelet` flags not exposed by managed groups, specialised instance types (e.g., Mac instances), or integration with custom launch template pipelines that conflict with managed-group constraints.
- **Hidden costs of self-managed:** You must write and maintain your own upgrade automation (typically via rolling ASG instance refresh + lifecycle hooks), your own node registration validation, and your own health-gate logic. Incident risk increases because AWS's tested drain path is no longer your safety net.
- **Middle path:** Karpenter replaces both approaches for most clusters — it provides fine-grained instance selection, fast scale-out, and automatic node consolidation without the node-group model at all. For stable, predictable baseline capacity Karpenter NodePools with custom `NodeClass` AMI selectors satisfy most "control" requirements.

**Recommendation:** Reject broad replacement. Accept self-managed only for specific node pools where a concrete, documented capability gap exists, and require the team to own an automated upgrade runbook reviewed by the platform team before it ships to production.

---

### Q: How do you design an EKS strategy for compliance-driven image scanning and runtime threat detection, and what are the gaps that each tool layer leaves?

**Model Answer:**

A defence-in-depth model across four layers:

1. **Build-time scanning (Trivy / Snyk / ECR Enhanced Scanning with Inspector):** Catches known CVEs before the image is pushed. Gap: zero-days, mis-configurations not expressed as CVEs, and packages added at runtime (e.g., `curl` downloaded inside a container entrypoint) are invisible.
2. **Admission-time policy (Kyverno or OPA/Gatekeeper):** Blocks images not sourced from approved ECR repos, lacking a recent scan pass, or missing required labels/SBOMs. Gap: policy bypass if the admission webhook itself is unavailable (always run in `FailClosed` mode with multiple replicas) or if someone has direct `kubectl exec` access.
3. **Runtime threat detection (Amazon GuardDuty EKS Runtime Monitoring or Falco):** Detects anomalous syscalls (e.g., unexpected shell exec, `/proc` scraping, crypto-mining patterns). GuardDuty is low-ops but has a fixed ruleset; Falco is flexible but requires rule maintenance and a daemonset that itself needs hardening.
4. **Network-level detection (VPC Flow Logs + GuardDuty network findings + network policies):** Identifies unexpected egress or east-west communication post-compromise.

**Key gaps to articulate:** No single tool closes the window between image push and admission; SBOM generation (Syft + Cosign attestation) is the bridge that lets admission policy verify supply-chain provenance rather than just a scan result. Integrate findings into a SIEM (Security Hub → EventBridge → Slack/PagerDuty) so runtime alerts have an SLA-driven response path, not just a dashboard.

---

### Q: Describe how you would design the EKS cluster RBAC model for a platform team that must grant developers self-service access without allowing privilege escalation.

**Model Answer:**

The core risk is that any subject with `create`/`update` on `ClusterRoleBinding` or `RoleBinding` in a privileged namespace can grant themselves or others higher permissions — so those verbs must be reserved for the platform team only.

**Design principles:**

- **Namespace-scoped RBAC only for developers:** Grant `edit` or custom `Role` objects (never `ClusterRole edit` bound at cluster scope). Developers can do everything within their namespace; nothing crosses namespace boundaries.
- **No `bind` or `escalate` verbs for developers:** Kubernetes 1.17+ `escalate` verb prevents a user from creating a RoleBinding that grants permissions they don't already hold. Audit this via `kubectl auth can-i` checks baked into CI.
- **RBAC via GitOps only:** All `Role`, `ClusterRole`, `RoleBinding`, and `ClusterRoleBinding` objects are managed in a platform GitOps repo. Kyverno policy blocks `kubectl apply` of RBAC resources by non-platform service accounts at admission time.
- **Break-glass access:** A time-limited `ClusterRoleBinding` to `cluster-admin` is issued via an internal CLI that writes to an audit log, sends a Slack alert, and auto-expires the binding after 4 hours using a CronJob or Kyverno `cleanupPolicy`.
- **Audit continuously:** Export RBAC objects nightly to S3 via a Kubernetes Job; diff against the GitOps state to detect out-of-band mutations. Surface any new `ClusterRoleBinding` to `cluster-admin` as a P1 security alert.


---

## 🗓️ Added 2026-09-15 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-15 18:42 -->

### Q: How do you design an EKS strategy for control-plane scalability when running thousands of Custom Resource Definitions and high-volume operators, and what are the failure modes to watch for?

**Model Answer:**

At scale, etcd becomes the primary bottleneck: each CRD instance is stored as a key-value entry, and operators that reconcile frequently can saturate etcd with watch events and list operations. Key design principles:

- **Limit CRD cardinality** — avoid patterns where one CRD instance is created per ephemeral object (e.g., per-request resources); prefer aggregation.
- **Operator tuning** — set `--sync-period`, `--max-concurrent-reconciles`, and use informer caches with label-selector filtering to reduce API server fan-out.
- **Separate operator namespaces and RBAC** — scope watches to specific namespaces so operators don't trigger cluster-wide list/watch storms.
- **etcd health metrics** — alert on `etcd_db_total_size_in_bytes` (warn at 6 GB, hard limit 8 GB), `etcd_request_duration_seconds` p99, and `apiserver_request_duration_seconds` by verb/resource.
- **Pagination and rate limiting** — ensure operators use paginated list calls (`Limit`/`Continue`) and respect client-side rate limits (`QPS`/`Burst` in the controller-runtime rest config).
- **Fleet segmentation** — for very high CRD volumes, consider dedicated clusters per domain (e.g., separate clusters for CI workloads vs. production) to isolate etcd pressure.

Common failure modes: etcd compaction lag causing watch re-sync storms; a single runaway operator issuing un-paginated list calls on a large resource type; CRD conversion webhooks adding latency to every API call of that resource.

---

### Q: A team has enabled the EKS VPC CNI's network policy controller, but pods that should be isolated are still communicating freely. How do you systematically diagnose and fix this?

**Model Answer:**

Start by confirming the foundational prerequisites before assuming policy logic is wrong:

1. **Verify the network policy controller is actually active** — check that `ENABLE_NETWORK_POLICY` env var is set to `true` on the `aws-node` DaemonSet, and that `aws-network-policy-agent` pods are running on every node and healthy.
2. **Check node kernel and eBPF support** — the VPC CNI network policy controller uses eBPF; nodes must run kernel ≥ 5.10 (Amazon Linux 2023 or AL2 with updated kernel). Older AMIs silently fall back to no enforcement.
3. **Validate policy selector labels** — use `kubectl get networkpolicy -o yaml` and cross-check `podSelector` labels against actual pod labels with `kubectl get pod --show-labels`. Label mismatches are the most common cause.
4. **Check policy direction** — confirm both ingress and egress rules are defined as needed. A missing egress policy on the source pod allows outbound traffic regardless of the destination's ingress rules.
5. **Inspect eBPF maps** — on the node, use `bpftool prog list` and check agent logs for policy programming errors; failed eBPF map updates mean policies are not enforced even if they appear applied in the API.
6. **Namespace isolation** — ensure a default-deny policy exists in the namespace; NetworkPolicy is additive, so without a baseline deny, all traffic remains allowed.
7. **Test with `kubectl exec` + `curl`** — instrument connectivity tests between specific pod pairs to confirm before/after, and use `aws-network-policy-agent` debug logging to trace policy decisions.

---

### Q: How do you design an EKS platform to support tenant-level egress control — ensuring different teams' pods exit to the internet through different NAT Gateways or egress IPs — and what are the trade-offs?

**Model Answer:**

This is a common requirement in regulated multi-tenant environments where per-team IP allowlisting on downstream systems is mandatory. Available approaches:

- **Per-team subnet + NAT Gateway** — place each tenant's node group or Fargate profile in dedicated subnets with their own route table pointing to a dedicated NAT Gateway. Traffic egresses from a predictable, team-specific elastic IP. Trade-off: NAT Gateway per team is expensive ($0.045/hr + data processing), and subnet proliferation increases VPC complexity.
- **VPC CNI secondary IP with custom routing** — use the VPC CNI's `AWS_VPC_K8S_CNI_CUSTOM_NETWORK_CFG` feature to assign pod ENIs to specific subnets distinct from the node subnet, enabling per-pod-subnet egress routing. This gives finer-grained control but requires careful ENI capacity planning.
- **Egress gateway via service mesh or proxy** — route all outbound traffic through a per-tenant Envoy egress gateway or a Squid proxy tier, applying source-NAT at the proxy layer. Adds latency and an operational proxy fleet but allows egress IP assignment without VPC subnet proliferation.
- **AWS Network Firewall + GWLB** — centralize egress through a firewall VPC with per-tenant route tables. Supports domain-based filtering and centralised logging but adds routing complexity and cost.

Key trade-offs: subnet-per-team is operationally simple but costly and hits VPC subnet limits at scale; proxy-based egress is flexible but introduces a critical-path dependency. Always combine with egress NetworkPolicy to enforce which pods can reach the egress path at all.

---

### Q: Describe how you would architect and operate an EKS cluster fleet upgrade program across 50+ clusters with varying team ownership, and what governance mechanisms prevent clusters from falling critically behind on Kubernetes versions.

**Model Answer:**

At fleet scale, ad-hoc upgrades become untenable; the program needs to be systematic and policy-enforced:

- **Version skew policy** — define an organisational SLA: clusters must not be more than N-2 minor versions behind the current EKS-supported release. Codify this as an AWS Config rule or custom policy that alerts and escalates automatically.
- **Cluster metadata registry** — maintain a central inventory (e.g., a DynamoDB table or Backstage catalog) recording each cluster's current version, owner, last-upgrade date, and upgrade-window schedule. Feed this into dashboards and on-call runbooks.
- **Staged upgrade rings** — group clusters into rings (sandbox → dev → staging → prod), promoting upgrades through rings with a mandatory soak period and automated smoke tests (kube-bench, workload health checks) before proceeding.
- **Automation with Terraform/CDK + CI pipelines** — define the target cluster version in code; a GitOps PR pipeline applies version bumps, runs pre-flight checks (deprecated API scan via `pluto` or `kubent`, add-on compatibility matrix), and requires team sign-off before merging.
- **Managed node group rolling updates** — use EKS managed node group update configs with `maxUnavailable` tuning per criticality tier; Karpenter clusters require draining and re-provisioning nodes to the new AMI.
- **Escalation path** — clusters approaching end-of-support trigger automated Jira tickets to team leads and skip-level managers; unresponsive clusters after a defined date are force-upgraded during a maintenance window by the platform team with documented authority.
- **Add-on compatibility gates** — before each upgrade, run an automated check against the EKS add-on version compatibility matrix (VPC CNI, CoreDNS, kube-proxy) and block the upgrade pipeline if incompatible add-on versions are detected.


---

## 🗓️ Added 2026-09-16 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-16 18:38 -->

### Q: How do you design an EKS strategy for handling cluster-level secrets rotation without causing application downtime, and what are the common failure modes?

**Model Answer:**

The core challenge is decoupling secret rotation from application restarts. Key design decisions:

- **External Secrets Operator (ESO) or Secrets Store CSI Driver** syncs secrets from AWS Secrets Manager/Parameter Store into Kubernetes Secrets or mounted volumes; rotation is propagated on a configurable refresh interval without pod restarts when using volume mounts with `syncSecret.enabled` and application-level file watching.
- **Versioned secret ARNs** in Secrets Manager allow you to stage a new secret version to `AWSPENDING`, validate it, then promote to `AWSCURRENT` — giving applications a window to drain old credentials.
- **Application-side rotation awareness** is critical: apps must re-read credentials from the filesystem or re-fetch from the SDK rather than caching them indefinitely in memory. This is the most common failure mode.
- **Dual-credential windows**: For database passwords, RDS Proxy or application-level dual-credential support (accepting both old and new password simultaneously) eliminates the gap between rotation and propagation.
- **Common failure modes**: (1) CSI driver volume not refreshing because `rotationPollInterval` is too long; (2) Kubernetes Secrets cached by kubelet not propagated when pods use `envFrom` (environment variables require a pod restart, unlike volume mounts); (3) race conditions where some pods pick up the new secret before the backend accepts it.
- **Governance**: Use CloudTrail + EventBridge to alert on rotation events and trigger automated canary validation before full rollout.

---

### Q: How do you design an EKS strategy for high-churn, short-lived job workloads — such as CI runners or ephemeral build environments — and what are the scaling and cost trade-offs?

**Model Answer:**

High-churn job workloads have distinct characteristics: bursty demand, short lifespans (seconds to minutes), and high scheduling overhead. The recommended architecture:

- **Karpenter** is strongly preferred over Cluster Autoscaler here because it can provision a node in ~30–60 seconds and consolidate aggressively between bursts; set `consolidationPolicy: WhenEmpty` or `WhenUnderutilized` with short `consolidateAfter` windows (e.g., 30s) to reclaim idle nodes quickly.
- **Dedicated NodePools** for CI workloads with taints/tolerations prevent job pods from landing on long-lived service nodes, avoiding noisy-neighbour disruption and enabling aggressive instance-type diversification across spot capacity pools.
- **Spot Instances with interruption handling** are cost-effective for CI since most jobs can be retried; use `karpenter.sh/interruption-queue` with SQS-based interruption handling to cordon and drain nodes before reclamation.
- **Avoid StatefulSet/PVC patterns** for ephemeral builds; use emptyDir with `medium: Memory` for small temp files or leverage S3-backed build caches (e.g., Buildkite, GitHub Actions cache action) to externalise state.
- **Pod scheduling overhead**: For very short jobs (< 60s), node startup latency dominates. Mitigate with warm pool pre-provisioning or by running a small baseline node count for immediate scheduling.
- **Cost trade-off**: Aggressive consolidation reduces idle compute waste but increases API server churn (frequent node create/delete events); monitor etcd object count and API server request rate to detect saturation.

---

### Q: A multi-team EKS cluster is experiencing intermittent scheduling failures where pods sit in "Pending" despite nodes appearing to have sufficient CPU and memory. How do you systematically diagnose and resolve this?

**Model Answer:**

When capacity appears available but scheduling fails, the issue is almost always a non-resource constraint. Systematic approach:

1. **`kubectl describe pod <pod>`**: Read the `Events` section for the scheduler's explicit rejection reason — this is the single most important diagnostic step. Common messages: `0/N nodes are available: N node(s) had taint that the pod didn't tolerate`, `Insufficient ephemeral-storage`, `node(s) didn't match Pod's node affinity/selector`.
2. **Ephemeral storage and extended resources**: CPU/memory shown in `kubectl top nodes` does not include ephemeral-storage pressure or custom extended resources (e.g., GPU, hugepages). Check `kubectl describe node` for `Allocatable` vs `Requests` across all extended dimensions.
3. **Topology spread constraints**: A misconfigured `topologySpreadConstraint` with `maxSkew: 1` across zones can block scheduling if one zone already has more pods than others, even when aggregate capacity is free.
4. **Taint/toleration drift**: Node groups created by Karpenter or via lifecycle hooks may have acquired unexpected taints (e.g., from a DaemonSet or node problem detector). Verify with `kubectl get nodes -o json | jq '.items[].spec.taints'`.
5. **Scheduler throughput**: In very large clusters (1000+ nodes), the scheduler queue depth may be backlogged. Check `scheduler_pending_pods` and `scheduler_scheduling_duration_seconds` metrics; increase `--kube-api-qps` or deploy a second scheduler for batch workloads.
6. **Resolution pattern**: Fix the immediate constraint, then add alerting on `kube_pod_status_phase{phase="Pending"} > 0 for 5m` with a runbook reference to this diagnostic flow.

---

### Q: Describe a situation where you had to advocate against a business stakeholder's preferred EKS architectural decision. How did you handle the disagreement and what was the outcome?

**Model Answer:**

This question probes influence without authority and technical leadership under pressure. A strong answer structure:

- **Situation framing**: "A VP of Engineering wanted to consolidate all teams — including high-compliance PCI workloads — onto a single shared EKS cluster to reduce operational overhead. I believed this introduced unacceptable blast radius and compliance scope creep."
- **Approach taken**: I prepared a structured trade-off document rather than a flat objection. It quantified the compliance cost (PCI scope expansion would pull 12 additional services into quarterly audits, estimated at ~$200K/year in audit effort) against the operational saving (~2 FTE cluster management overhead for separate clusters).
- **Building alignment**: I brought in the CISO and lead auditor to validate the compliance risk assessment, so the technical concern was backed by regulatory authority, not just architectural preference. I also proposed a middle path: a dedicated PCI cluster managed by the same platform tooling (Terraform modules, shared GitOps patterns) to reduce the operational delta.
- **Outcome**: The middle path was adopted. The PCI cluster was spun up within the existing platform framework in three weeks; the operational overhead delta was less than 0.5 FTE, well within the compliance savings.
- **Key principle demonstrated**: Technical advocacy is most effective when it translates architectural risk into business-relevant terms (cost, compliance exposure, time) and offers a concrete alternative rather than a binary objection.


---

## 🗓️ Added 2026-09-17 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-17 18:48 -->

### Q: How do you design an EKS strategy for handling node-level kernel and OS vulnerabilities on Bottlerocket and Amazon Linux 2023 managed nodes, and what are the operational trade-offs?

**Model Answer:**

- **Bottlerocket** is the preferred choice for security-sensitive workloads: it has a minimal, read-only root filesystem, automatic transactional OS updates via `apiclient`, and a gVisor/Bottlerocket-aware attack surface, making CVE patching faster and more deterministic.
- For managed node groups, the primary patching mechanism is **node group version updates** — AWS releases new AMIs, you update the launch template version, and managed node groups perform a rolling replacement with respect to PodDisruptionBudgets.
- **Operational trade-off**: Bottlerocket limits deep OS customisation (no `apt`/`yum`, restricted SSH by default via SSM admin container), which can conflict with teams that run node-level daemons or require custom kernel modules. Amazon Linux 2023 offers more flexibility but a larger attack surface.
- Implement **automated AMI drift detection**: compare the AMI ID in running node groups against the latest EKS-optimised AMI via the SSM Parameter Store path (`/aws/service/bottlerocket/...`), and alert or auto-trigger updates when drift exceeds a policy threshold (e.g., 14 days).
- Pair OS patching with **runtime threat detection** (Falco or GuardDuty EKS Runtime Monitoring) so that zero-days exploited before the patch cycle fires an alert rather than going silent.
- For Karpenter-managed nodes, bake AMI selection into `EC2NodeClass` with `amiSelectorTerms` pinned to a specific AMI family, and use a CI pipeline to publish a new `EC2NodeClass` version when a new AMI passes your validation suite — avoiding uncontrolled AMI drift.
- **Key interview signal**: distinguish between *data-plane AMI patching* (managed node group rollout, Karpenter node drift) and *control-plane CVEs* (AWS-managed, no operator action needed beyond staying on a supported minor version).

---

### Q: A team reports that their EKS workload's HorizontalPodAutoscaler is not scaling despite CPU metrics being well above the target threshold. How do you systematically diagnose and resolve this?

**Model Answer:**

Start with `kubectl describe hpa <name>` — the `Conditions` section will surface the most common root causes immediately: `AbleToScale`, `ScalingActive`, and `ScalingLimited` each have machine-readable reasons.

**Common root causes and checks:**

1. **Metrics pipeline broken** — HPA relies on `metrics-server` (for CPU/memory) or a custom metrics adapter (Prometheus Adapter, KEDA). Verify `kubectl top pods` returns data; if it errors, the metrics-server is the failure point. Check metrics-server logs for scrape failures, especially if node-level mTLS or network policies block kubelet port 10250.
2. **Missing resource requests** — HPA computes utilisation as `current / requested`. If the pod has no `resources.requests.cpu`, the HPA reports `<unknown>` utilisation and will not scale. Enforce requests via admission policy.
3. **`scaleTargetRef` mismatch** — the HPA must reference the correct `apiVersion` and `kind`; a wrong reference causes silent no-ops.
4. **`minReplicas`/`maxReplicas` ceiling** — confirm the current replica count is not already at `maxReplicas`; the HPA will show `ScalingLimited: TooManyReplicas`.
5. **Cooldown/stabilisation window** — default scale-down stabilisation is 5 minutes; scale-up has a 3-minute default. If the spike is short-lived, the HPA may have already stabilised before action.
6. **KEDA vs. HPA conflict** — if KEDA is also managing the same deployment, it creates its own HPA, and the two can conflict; remove the manual HPA.

**Resolution path**: fix the metrics pipeline first, enforce resource requests via OPA/Kyverno, validate with `kubectl get --raw "/apis/metrics.k8s.io/v1beta1/namespaces/<ns>/pods"`, then retest with a sustained load generator.

---

### Q: How do you design an EKS strategy for cost-optimised, resilient use of Spot Instances for production workloads, and what failure modes must you explicitly engineer against?

**Model Answer:**

- **Diversification is the foundational principle**: specify a broad set of instance families and sizes in Karpenter `NodePool` (or Cluster Autoscaler's node group pool) — ideally 10+ compatible types — so the scheduler can always find capacity even during Spot shortages in a single pool.
- Use **Spot interruption handling** proactively: AWS sends a 2-minute interruption notice via EC2 instance metadata and EventBridge. Deploy the **AWS Node Termination Handler** (or rely on Karpenter's built-in interruption queue) to cordon and drain the node gracefully before the 2-minute window closes, respecting PodDisruptionBudgets.
- **Workload suitability**: stateless, horizontally scalable services with fast startup times (<30 seconds) are ideal. Stateful workloads, leader-elected singletons, and anything with a long startup time are poor candidates unless you run at least one on-demand replica per critical component.
- **Spread and topology constraints**: use `topologySpreadConstraints` across multiple AZs and combine with `podAntiAffinity` to avoid all replicas landing on Spot nodes in a single AZ that experiences a simultaneous Spot reclamation wave.
- **Capacity rebalancing signals**: subscribe to EC2 Capacity Rebalancing recommendations (separate from interruption notices, arriving earlier) via Karpenter's interruption SQS queue to proactively replace at-risk nodes before the hard 2-minute window.
- **On-demand baseline**: for critical services, run a minimum replica count on on-demand nodes using node selectors or `nodeAffinity` with a `preferredDuringSchedulingIgnoredDuringExecution` fallback, and use Spot only for burst capacity.
- **Key trade-off to articulate**: Spot saves 60–80% compute cost but introduces non-deterministic interruptions; the architecture must treat Spot nodes as ephemeral infrastructure, not stable hosts — any assumption of node longevity is an anti-pattern.

---

### Q: Describe how you would lead a post-incident review after a major EKS outage, and what systemic changes you would drive to prevent recurrence. Walk through a realistic example.

**Model Answer:**

**Realistic scenario**: A misconfigured Karpenter `NodePool` change (wrong instance family filter) caused all new nodes to launch without the EBS CSI driver DaemonSet being scheduled (node selector mismatch), resulting in all StatefulSet pods failing to attach PVCs cluster-wide for 40 minutes during a peak traffic window.

**Post-incident review process:**

- **Blameless framing from the start**: the review focuses on system and process failures, not individual error. The misconfiguration was possible because the change lacked a pre-production validation gate.
- **Timeline reconstruction**: use CloudTrail (API calls), Kubernetes audit logs, and a correlated observability timeline (Grafana/CloudWatch) to establish a precise sequence — change applied → nodes launched → DaemonSet selector mismatch detected → PVC attachment failures → on-call page → mitigated.
- **Five whys**: Why did pods fail? PVC attach failed. Why? EBS CSI driver not present on new nodes. Why? Node selector in DaemonSet didn't match new node labels introduced by the NodePool change. Why did the change go undetected? No staging environment mirrors Karpenter `NodePool` config; change was applied directly to production via a manual `kubectl apply`. Why was manual apply possible? GitOps enforcement (ArgoCD) had an exception for Karpenter config due to a legacy bypass.

**Systemic changes driven:**
1. Remove the ArgoCD bypass — all Karpenter manifests flow through GitOps with mandatory PR review.
2. Add a pre-merge CI check that validates `NodePool` changes against DaemonSet node selectors using a policy-as-code rule (OPA Conftest).
3. Implement


---

## 🗓️ Added 2026-09-18 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-18 18:03 -->

### Q: How do you design an EKS strategy for etcd health and API server request throttling as the cluster scales to thousands of nodes and tens of thousands of objects?

**Model Answer:**

etcd is the single most critical bottleneck in a large EKS control plane, even though AWS manages it. Key design principles:

- **Object count discipline**: Aggressively prune stale objects — completed Jobs, old ReplicaSets, expired Events — using `ttlSecondsAfterFinished`, `revisionHistoryLimit`, and event TTL tuning. Unbounded growth in object count directly degrades etcd and API server list performance.
- **List/watch optimisation**: Ensure all controllers and monitoring agents use **watch** rather than repeated **list** calls. Audit `--watch-cache-sizes` and ensure informers share caches rather than each opening independent watches (e.g., avoid multiple in-cluster clients per process).
- **API priority and fairness (APF)**: EKS 1.20+ enables APF by default. Define `FlowSchema` and `PriorityLevelConfiguration` objects to ring-fence critical system traffic (node heartbeats, kube-scheduler) from lower-priority automation or CI tooling that floods the API server with requests.
- **Avoid chatty CRD controllers**: Controllers with tight reconciliation loops and no exponential back-off generate disproportionate API server load. Enforce requeue rate limits and use `controller-runtime`'s built-in rate limiting.
- **Shard workloads across clusters**: When a single cluster exceeds ~1,000 nodes or ~150,000 objects, the correct architectural answer is cluster sharding — don't try to tune your way past the physics of a single etcd ring.
- **Observability signals**: Monitor `apiserver_request_duration_seconds`, `etcd_request_duration_seconds`, and `apiserver_current_inflight_requests` via the EKS control-plane CloudWatch metrics namespace; alert before throttling becomes visible to workloads.

---

### Q: A team wants to use EKS Fargate exclusively for all workloads to eliminate node management overhead. What are the architectural constraints you would surface before approving this, and under what conditions would you push back?

**Model Answer:**

Fargate on EKS eliminates node management but imposes significant architectural constraints that must be surfaced explicitly:

- **No DaemonSets**: Fargate pods run one-pod-per-virtual-node; DaemonSets are unsupported. Any sidecar-based observability, security agents (Falco, Datadog), or log forwarders must be injected as sidecars via admission webhooks — increasing pod complexity and resource overhead.
- **No privileged containers or host networking**: Workloads requiring `hostNetwork`, `hostPID`, or privileged security contexts (e.g., eBPF-based tools, GPU workloads, some service meshes) cannot run on Fargate.
- **Persistent storage limitations**: Only EFS (via CSI) is supported; EBS is not. Workloads needing block storage or high-IOPS persistent volumes cannot use Fargate.
- **Cold start latency**: Fargate provisions a new microVM per pod, which takes 30–90 seconds. This is unacceptable for latency-sensitive autoscaling, Job workloads with tight deadlines, or burst traffic patterns.
- **Cost at scale**: Fargate pricing is per-vCPU/memory-second with no Reserved or Savings Plan pricing equivalent for EKS Fargate (unlike EC2). At sustained high utilisation, EC2-based node groups are materially cheaper.
- **My recommendation**: Fargate is excellent for low-volume, variable, or bursty workloads where operational simplicity outweighs cost. For sustained, high-throughput, or infrastructure-dependent workloads, I would push back and propose a hybrid model — Fargate for auxiliary services, managed node groups for core workloads.

---

### Q: How do you design an EKS multi-cluster fleet management strategy, including config synchronisation, policy enforcement, and visibility, without creating an unmanageable operational burden?

**Model Answer:**

At scale, ad hoc per-cluster management becomes untenable. The strategy layers across three concerns:

- **Config synchronisation**: Use a GitOps controller (Flux or ArgoCD) with an **app-of-apps** or **ApplicationSet** pattern to declaratively synchronise cluster addons, namespaces, RBAC, and workloads from a single Git source of truth. Cluster-specific overrides are expressed as Kustomize overlays or Helm values files keyed by cluster metadata.
- **Policy enforcement**: Deploy Kyverno or OPA/Gatekeeper as a standard addon via the GitOps pipeline to every cluster. Policies are authored centrally and versioned in Git; `PolicyExceptions` are peer-reviewed. Use AWS Config with a custom rule or Security Hub integration to detect clusters missing required policy controllers.
- **Add-on lifecycle**: Use **EKS Managed Add-ons** (VPC CNI, CoreDNS, kube-proxy, EBS CSI) to delegate patching to AWS for common components. For third-party addons, pin versions in Git and use Renovate or Dependabot to propose version bumps via PR.
- **Fleet visibility**: Aggregate metrics and alerts into a central observability plane (e.g., Amazon Managed Prometheus with cross-account scraping, or a centralised Grafana fleet dashboard). Tag all clusters consistently (`environment`, `team`, `region`) and surface this in AWS Resource Explorer.
- **Cluster API or eksctl pipelines**: Codify cluster creation itself — VPC, node groups, addons — in infrastructure-as-code (Terraform or CDK) with a cluster vending machine pattern so new clusters are born already compliant.
- **Key guardrail**: Resist the temptation to allow per-cluster manual drift. Every exception applied by SSH or `kubectl` outside GitOps becomes invisible operational debt. Enforce this culturally and technically via RBAC that limits direct cluster access.

---

### Q: Describe how you would conduct and structure a blameless post-mortem after a customer-impacting EKS incident, and how you translate its findings into durable architectural improvements rather than one-off fixes.

**Model Answer:**

A high-quality post-mortem does two things: it builds shared understanding without blame, and it produces systemic improvements rather than tactical patches.

- **Timeline construction**: Within 24 hours, assemble a precise timeline from CloudTrail, CloudWatch Logs, ALB access logs, and application logs. Every action — automated or human — is included. This prevents competing narratives and surfaces the true sequence of contributing factors.
- **Five-whys to systemic causes**: Push the analysis past the proximate cause ("a pod OOMKilled") to systemic causes ("resource limits were absent because the admission policy only warned, not denied, and the staging environment had more memory than production"). Resist stopping at human error as a root cause — human error is always a symptom.
- **Action items with owners and deadlines**: Each finding maps to a concrete action with a named owner and a due date. Categorise actions: **detection** (we didn't know fast enough), **prevention** (the failure should have been impossible), and **mitigation** (blast radius should have been smaller). Unowned actions become shelfware.
- **Architectural translation**: Prevention actions should challenge the architecture. If a single misconfigured Deployment caused cluster-wide disruption, the architectural answer is namespace-scoped resource quotas, pod disruption budgets, and admission control — not "be more careful next time." Document these as Architecture Decision Records (ADRs) so the rationale is preserved.
- **Feedback loops**: Share the post-mortem openly across teams (sanitised if needed for external parties). Track action item completion in a backlog reviewed monthly. Re-run GameDay exercises or chaos tests specifically targeting the failure mode after mitigations are in place to verify effectiveness.
- **Culture signal**: How leadership responds to post-mortems sets the cultural tone. If engineers fear punishment, incidents get under-reported and analysis stays shallow. Publicly acknowledging good post-mortem work reinforces the behaviour you want at scale.


---

## 🗓️ Added 2026-09-19 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-19 17:45 -->

### Q: How do you design an EKS strategy for cross-cluster service discovery and traffic routing without a full service mesh?

**Model Answer:**

- **CoreDNS chaining / stub zones**: Configure CoreDNS with stub zones that forward `<cluster>.local`-style FQDNs to a central Route 53 Private Hosted Zone, allowing pods in one cluster to resolve services in another without a mesh sidecar.
- **AWS Cloud Map**: Register services at deploy-time into Cloud Map namespaces; clients resolve via DNS or the Cloud Map API, decoupling discovery from cluster internals.
- **NLB + PrivateLink anchors**: Expose inter-cluster services through internal NLBs (or PrivateLink endpoints for strict isolation) so that cross-cluster traffic has a stable IP and never hairpins through the public internet.
- **ExternalDNS**: Run ExternalDNS in each cluster to publish `Service` and `Ingress` records into shared Route 53 zones automatically, keeping DNS entries consistent with the actual live endpoints.
- **Trade-offs to articulate**: This approach eliminates sidecar overhead and control-plane complexity but sacrifices mTLS, fine-grained retries, and traffic-shifting that a mesh provides; it's appropriate when latency budget is tight or mesh operational maturity is low.
- **Failure modes**: DNS TTL caching can cause stale routing after a pod or node failure; mitigate with short TTLs plus health-check-based weighted records, and ensure clients implement exponential back-off.

---

### Q: A team wants to adopt GitOps with Flux or Argo CD on EKS, but the cluster manages sensitive production workloads. What security boundaries and operational safeguards do you enforce?

**Model Answer:**

- **Separate GitOps controller permissions from application permissions**: The Argo CD / Flux controller's ServiceAccount uses IRSA scoped only to the resources it reconciles; it should never inherit broad cluster-admin rights.
- **Repository access hygiene**: Source repos use deploy keys (read-only) or OIDC-based GitHub App tokens; secrets are never committed — only sealed-secret or SOPS-encrypted ciphertext, with the decryption key held in AWS KMS accessible only by the controller's IRSA role.
- **Admission gate before sync**: Pair the GitOps controller with an OPA/Gatekeeper or Kyverno policy engine so that even a PR that passes code review is rejected at admission if it violates policy (e.g., `privileged: true`, missing resource limits).
- **Progressive delivery gating**: For production, require a manual sync gate or a Argo CD `SyncWindow` that restricts automatic reconciliation to maintenance windows; automated rollout only in non-prod.
- **Drift detection as a security signal**: Enable Argo CD's out-of-sync alerting; unexpected drift (someone `kubectl apply`-ing directly) triggers a PagerDuty alert and should be treated as a potential incident, not just an ops nuisance.
- **Multi-tenancy isolation**: Use Argo CD `AppProject` resources to fence teams — each project can only target specific destination namespaces/clusters and source repos, preventing one team's GitOps pipeline from touching another's workloads.
- **Audit trail**: All reconcile events write to CloudTrail (via the API server) and Argo CD's own audit log, shipped to a SIEM; this satisfies change-management audit requirements in regulated environments.

---

### Q: How do you design an EKS strategy for handling long-running, stateful gRPC streaming connections through AWS Load Balancer infrastructure, and what failure modes must you plan for?

**Model Answer:**

- **NLB over ALB for persistent streams**: ALB terminates HTTP/2 streams at the load balancer and multiplexes them, which can cause unexpected stream resets; NLB operates at L4 and preserves end-to-end gRPC framing, making it the preferred choice for long-lived bidirectional streams.
- **Connection draining alignment**: Set NLB target-group deregistration delay to be longer than your longest expected stream lifetime (or your client's reconnect timeout); a mismatch causes in-flight streams to be abruptly reset during deployments.
- **`preStop` hook + `terminationGracePeriodSeconds`**: Configure pods with a `preStop` sleep matching the draining delay so the process doesn't exit before connections are fully drained; gRPC servers should also honour `SIGTERM` by stopping new stream acceptance while completing existing ones.
- **Health check vs. keepalive tuning**: NLB TCP health checks and gRPC keepalive pings (`KEEPALIVE_TIME`, `KEEPALIVE_TIMEOUT`) must be co-tuned; overly aggressive keepalives cause idle connection churn, while too-loose values mask dead backend detection.
- **Client-side load balancing consideration**: For very high fan-out (e.g., thousands of streaming subscribers), consider moving load balancing to the client layer using xDS/Envoy rather than relying solely on NLB, since NLB connections are persistent and can create hot backends if streams are long-lived.
- **Failure modes**: Spot interruption or node drain terminates streams without client retry logic noticing immediately — ensure clients implement gRPC status code `UNAVAILABLE` retry with exponential back-off and cap; also plan for NAT gateway idle-timeout (350 seconds) resetting streams if no data flows.

---

### Q: Describe how you would lead a blameless post-mortem after a major EKS production incident, and what structural outputs you expect to drive lasting improvement.

**Model Answer:**

- **Psychological safety first**: Open the post-mortem by explicitly stating the blameless principle — the goal is to understand system and process failure, not to assign personal fault; this is especially important in organisations where engineers fear retribution for outages.
- **Timeline reconstruction**: Collaboratively build a precise timeline (to the minute) using CloudTrail, CloudWatch Logs Insights, and kubectl audit logs; surface the gap between when the issue started and when it was detected, as that gap is usually where the biggest reliability investment should go.
- **Five-whys on contributing factors**: Identify both the proximate cause (e.g., "CoreDNS OOMKilled") and systemic causes (e.g., "no memory limit set, no autoscaling for CoreDNS, no alert on DNS error rate"); surface organisational factors like missing runbooks, insufficient on-call training, or skipped staging tests.
- **Structured action items**: Every action item must have an owner, a due date, and a severity classification (P1 = must fix before next deploy, P2 = sprint, P3 = backlog); vague actions like "improve monitoring" are rejected — replace with "add CloudWatch alarm on `coredns_dns_request_duration_seconds` p99 > 500 ms, owner: SRE team, due: 2 weeks."
- **Reliability metrics linkage**: Map findings to SLO impact — how many error-budget minutes were consumed? This frames the business case for investing engineering time in preventive work rather than features.
- **Follow-up cadence**: Schedule a 30-day review to confirm action items are closed and that any new monitoring has actually fired in test; publish the post-mortem to a shared internal wiki to build organisational learning across teams, not just the incident team.
- **Behavioural signal as an architect**: Demonstrating that you treat post-mortems as a first-class engineering artefact — not a box-ticking exercise — is what differentiates a senior architect who builds resilient cultures from one who only designs resilient systems.


---

## 🗓️ Added 2026-09-20 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-20 17:55 -->

### Q: How do you design an EKS strategy for managing cluster upgrades at scale across a large fleet with minimal blast radius and zero unplanned downtime?

**Model Answer:**

- **Upgrade rings:** Segment clusters into rings (dev → staging → canary prod → full prod) with mandatory soak periods between each ring; automate promotion gates using health checks and SLO metrics.
- **Control-plane first:** EKS in-place control-plane upgrades are AWS-managed and non-disruptive; validate add-on compatibility (VPC CNI, CoreDNS, kube-proxy) against the target version before proceeding, using the EKS add-on version compatibility matrix.
- **Node group strategy:** Use surge rolling updates on managed node groups (set `maxUnavailable=0`, `maxSurge=1`) or blue/green node group replacement for Karpenter-managed nodes by updating `NodePool` AMI family and draining old nodes gradually.
- **Add-on sequencing:** Upgrade add-ons in dependency order — CNI before CoreDNS before kube-proxy — and pin versions explicitly; use EKS managed add-ons to get AWS-managed rollback on failure.
- **Validation gates:** Run Pluto or `kubectl convert` in CI to detect deprecated API usage before each upgrade; execute smoke tests and PodDisruptionBudget compliance checks post-node-roll.
- **Rollback posture:** Control-plane downgrade is not supported; rollback means maintaining a parallel old-version cluster or a tested restore-from-backup procedure, which reinforces the importance of pre-upgrade validation over post-upgrade recovery.
- **Behavioral angle:** Communicate upgrade timelines and deprecation windows to application teams at least one version ahead, establishing a shared responsibility model so teams own API compatibility within their workloads.

---

### Q: A pod in your EKS cluster is consuming unbounded memory and triggering OOMKill repeatedly, but the owning team insists their application is functioning correctly. How do you investigate and resolve this systematically?

**Model Answer:**

Start by distinguishing between a genuine memory leak, working-set growth under load, and a misconfigured limit that is too low relative to legitimate usage. Pull `kubectl top pod` and Container Insights metrics to plot RSS, working set, and page cache over time — page cache inflation is benign and excluded from OOM accounting in some kernel versions but not all. Review the `oom_kill_constraint` in CloudWatch Container Insights to confirm whether OOMKill is triggered by the pod limit or node-level memory pressure (system OOM killer). Use `kubectl describe node` to check `MemoryPressure` condition and node-level allocatable vs. requested ratios. Profile the application using heap dumps, async-profiler, or language-specific tooling — coordinate with the team to capture a heap snapshot just before the OOMKill threshold. If the limit is genuinely too low, right-size it using the VPA recommendation in "Off" mode to generate a non-enforcing suggestion. Enforce `LimitRange` minimums per namespace to prevent unbounded containers, and set `requests == limits` for memory on latency-sensitive workloads to guarantee QoS class `Guaranteed`, avoiding eviction before OOMKill. As a governance outcome, require memory limits on all containers via an OPA/Gatekeeper policy and expose per-workload memory efficiency dashboards to shift ownership back to teams.

---

### Q: How do you design an EKS strategy for federated identity and cross-account workload access without distributing long-lived credentials?

**Model Answer:**

- **IRSA as the foundation:** Use IAM Roles for Service Accounts (IRSA) so every pod assumes an IAM role via OIDC token projection; the token is scoped to the service account and automatically rotated by the kubelet, eliminating static credentials entirely.
- **Cross-account trust:** In the target account, create an IAM role with a trust policy that allows `sts:AssumeRoleWithWebIdentity` from the source cluster's OIDC provider ARN, scoped to the specific namespace and service account name using `StringEquals` conditions on `sub` and `aud` claims.
- **EKS Pod Identity (newer alternative):** Evaluate EKS Pod Identity (GA 2023) as a simpler alternative to IRSA — it removes the need to manage per-cluster OIDC providers and supports role chaining natively, but currently lacks some fine-grained OIDC claim conditions.
- **Secrets isolation:** Never store cross-account credentials in Kubernetes Secrets or environment variables; use IRSA to authenticate directly to Secrets Manager or Parameter Store in the target account.
- **Audit trail:** Enable CloudTrail in all target accounts and correlate `AssumeRoleWithWebIdentity` events with the `kubernetes.io/serviceaccount` claim in the JWT to attribute API calls to specific pods and namespaces.
- **Least privilege enforcement:** Use IAM Access Analyzer to continuously validate that cross-account role policies do not grant unintended external access; integrate checks into the IaC pipeline.
- **Governance:** Maintain a centralised role catalogue (e.g., in Terraform or AWS Service Catalog) so cross-account roles are peer-reviewed, versioned, and linked to owning teams.

---

### Q: Describe how you would design an EKS platform to support developer self-service namespace provisioning while maintaining hard security and cost guardrails.

**Model Answer:**

The core pattern is a "namespace-as-a-service" model: developers submit a pull request or fill a portal form to declare a namespace, and automation handles provisioning with enforced guardrails rather than manual cluster-admin intervention. Use a Namespace controller or a GitOps-driven Helm/Kustomize template that creates the namespace alongside a standard bundle: `ResourceQuota`, `LimitRange`, `NetworkPolicy` (default-deny ingress/egress), RBAC role bindings scoped to the team's IdP group, and an IRSA service account. Gate namespace creation through an OPA/Gatekeeper `ValidatingAdmissionPolicy` that enforces naming conventions, mandatory labels (`team`, `cost-centre`, `environment`), and quota size tiers rather than arbitrary values. For cost guardrails, map the `cost-centre` label to an AWS Cost Allocation Tag using a Kubernetes label-to-tag propagation strategy (e.g., via the AWS Billing tag propagation feature or a custom controller), and set up per-namespace Kubecost alerts that notify teams when projected monthly spend exceeds a threshold. Use Hierarchical Namespace Controller (HNC) if teams need sub-namespace delegation, propagating policies from the parent without manual duplication. Enforce a CI lint step on namespace PRs that validates quota tiers against a policy matrix so engineers cannot approve excessive allocations without an explicit exception workflow. Behaviorally, publish a self-service runbook and SLA (e.g., namespace provisioned within 5 minutes of merge), which removes platform team bottlenecks while keeping the security boundary clear.


---

## 🗓️ Added 2026-09-21 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-21 19:51 -->

### Q: How do you design an EKS strategy for managing and securing the AWS VPC CNI plugin at scale, including custom networking, prefix delegation, and security group per pod?

**Model Answer:**

The VPC CNI is the most operationally impactful add-on in EKS because it directly controls IP allocation and pod networking. Key design decisions:

- **Prefix delegation** (`ENABLE_PREFIX_DELEGATION=true`) dramatically increases pod density per node by assigning /28 CIDR prefixes to ENIs rather than individual IPs — critical for large clusters but requires subnet CIDR planning to avoid fragmentation.
- **Custom networking** (`AWS_VPC_K8S_CNI_CUSTOM_NETWORK_CFG=true`) lets you assign pods to different subnets and AZs than the node's primary ENI, useful for IP conservation or isolating pod traffic to private subnets while nodes live in public ones.
- **Security Group for Pods (SGP)** enables ENI-trunking for branch ENIs, allowing pods to carry their own SGs; it's powerful for compliance but incompatible with prefix delegation, Fargate, and Windows nodes — understand these mutual exclusions before committing.
- Manage the CNI as an EKS managed add-on with version pinning; avoid allowing auto-upgrade during business hours, and test CNI upgrades in non-production first because a bad upgrade can cause a full networking outage.
- Apply IAM least-privilege to the `aws-node` DaemonSet's node IAM role — it needs `ec2:AssignPrivateIpAddresses` and related actions, not broad EC2 permissions.
- Monitor `ipamd` metrics (Prometheus endpoint on port 61678) for IP pool exhaustion (`awscni_total_ip_addresses`, `awscni_assigned_ip_addresses`) and alert before pods start failing to schedule due to IP starvation.

---

### Q: A production EKS deployment using Argo CD suddenly has hundreds of applications flipping to "OutOfSync" simultaneously with no recent git commits. How do you diagnose and resolve this?

**Model Answer:**

A mass OutOfSync event with no git activity points to a cluster-side change rather than a source-of-truth change. Systematic diagnosis:

1. **Check the timing**: Correlate the event with cluster activities — a Kubernetes minor-version upgrade, EKS managed add-on update, or admission webhook change can cause Argo CD to detect API version or field mutations.
2. **Inspect the diff**: Pull a representative app's diff in the Argo CD UI or `argocd app diff`. If fields like `managedFields`, `creationTimestamp`, or server-defaulted values appear, the issue is likely normalisation — Argo CD is seeing server-side-applied defaults that differ from the declared manifests.
3. **Common root causes**:
   - Kubernetes upgrade changed default field values or deprecated API versions, making stored manifests mismatched.
   - A mutation webhook started injecting sidecar fields not present in git.
   - Argo CD itself was upgraded and its diff logic changed.
   - Someone ran `kubectl apply` outside Argo CD, drifting live state.
4. **Short-term**: If the diff is benign (e.g., server defaults), configure Argo CD `ignoreDifferences` for known injected fields. Do not mass-sync without understanding the diff — a blind sync could overwrite legitimate in-cluster state.
5. **Long-term**: Enforce that all cluster mutations go through Argo CD (use a validating webhook or OPA policy to block direct `kubectl apply` in production). Pin Argo CD upgrades to maintenance windows with diff validation beforehand.
6. **API version drift**: If an EKS upgrade removed a beta API (e.g., `networking.k8s.io/v1beta1`), update manifests in git to the stable API version and re-sync deliberately.

---

### Q: How do you design an EKS strategy for cluster autoscaling decisions when workloads have highly heterogeneous resource profiles — mixing CPU-heavy, memory-heavy, and GPU jobs on the same cluster?

**Model Answer:**

Heterogeneous workload profiles require deliberate node pool segmentation and autoscaler configuration to avoid inefficiency and scheduling deadlocks:

- **Karpenter over Cluster Autoscaler**: Karpenter's `NodePool` and `EC2NodeClass` model allows fine-grained instance selection policies (e.g., `karpenter.k8s.aws/instance-family: [c7i, c6i]` for CPU-heavy, `r7i` for memory-heavy, `p4d/g5` for GPU). It evaluates the pending pod's exact resource request to right-size the instance rather than scaling up a fixed node group.
- **NodePool per workload archetype**: Define separate Karpenter NodePools with `taints` corresponding to workload type (`workload-type: gpu`, `workload-type: memory-optimized`). Require matching `tolerations` and `nodeSelector` on pods. This prevents CPU jobs from landing on expensive GPU nodes.
- **Bin-packing vs. spread**: For cost efficiency, prefer `consolidationPolicy: WhenUnderutilized` to right-size after scale-out. For GPU nodes (high hourly cost, slow to launch), set a tighter consolidation window.
- **Resource requests accuracy**: Autoscalers only work as well as the resource requests they see. Use VPA in recommendation mode to surface chronically under-requested workloads, and enforce request/limit ranges via LimitRange per namespace.
- **GPU-specific considerations**: Label GPU node pools and deploy the NVIDIA device plugin DaemonSet with a matching `nodeSelector`. Use `nvidia.com/gpu: 1` resource requests, not CPU/memory approximations. Consider time-slicing (`nvidia.com/gpu.sharing-strategy: time-slicing`) for inference workloads that don't need a full GPU.
- **Avoid over-diversification**: Too many NodePools increases Karpenter decision complexity and can cause consolidation loops. Group instance families with similar cost/performance characteristics into a single NodePool where possible.

---

### Q: Describe a situation where an EKS platform you owned suffered an unexpected outage caused by a dependency you did not control. What happened, how did you respond, and what architectural changes did you make afterward?

**Model Answer:**

*(Behavioral — answer should be structured, specific, and show ownership without blame-shifting.)*

**Situation**: At a previous role, our EKS platform used an external Vault cluster (not AWS Secrets Manager) for secret injection via the Agent Sidecar Injector. A Vault upgrade in an adjacent team's change window caused the Vault Agent Injector webhook to become unavailable for ~25 minutes. During that window, any pod restart or new deployment failed admission because the mutating webhook was configured with `failurePolicy: Fail`.

**Response**:
- Immediately identified the failing webhook via `kubectl describe pods` showing `admission webhook denied` errors.
- Temporarily patched the webhook to `failurePolicy: Ignore` to restore pod scheduling (with the trade-off that new pods would launch without secrets injected — acceptable for a subset of stateless services in degraded mode).
- Escalated to the Vault team and coordinated rollback of their upgrade.
- Communicated status to engineering leads on a 15-minute cadence.

**Architectural changes afterward**:
1. Changed all non-critical mutating webhooks to `failurePolicy: Ignore` with a circuit-breaker pattern — critical webhooks (security controls) remain `Fail` but have dedicated HA deployments with PodDisruptionBudgets.
2. Added synthetic canary tests that fire against the webhook endpoint every 60 seconds; alerts page on two consecutive failures.
3. Migrated the most critical secrets to AWS Secrets Manager + ASCP (Secrets Store CSI Driver) so the blast radius of a Vault outage is bounded.
4. Established a cross-team change coordination process requiring notification in a shared Slack channel before any shared-infrastructure dependency upgrade in business hours.


---

## 🗓️ Added 2026-09-22 (auto-generated · 4 new Q&A)

<!-- agent:2026-09-22 18:29 -->

### Q: How do you design an EKS strategy for webhook-heavy clusters where validating and mutating admission webhooks become a reliability and latency bottleneck?

Admission webhooks are synchronous, in-band with the API server, and can cause cascading failures if they become slow or unavailable. Key design points:

- **Fail-open vs. fail-closed trade-offs**: Set `failurePolicy: Fail` only for security-critical webhooks (e.g., OPA/Gatekeeper); use `Ignore` for non-critical ones to prevent cluster-wide disruption.
- **Scope narrowing**: Apply tight `namespaceSelector` and `objectSelector` rules so webhooks only intercept relevant resources — reducing unnecessary latency for unrelated objects.
- **Timeout budgets**: Keep `timeoutSeconds` at 3–5 s maximum; the API server has a 30 s hard limit but long webhooks block goroutines and degrade throughput.
- **High availability**: Run webhook servers with PodDisruptionBudgets, anti-affinity across AZs, and HPA or Karpenter-backed autoscaling so upgrade or node failure doesn't make them unavailable.
- **Sidestepping during bootstrapping**: Use `reinvocationPolicy` carefully and exempt `kube-system` namespaces from policy webhooks to avoid chicken-and-egg problems during control-plane recovery.
- **Latency SLOs**: Instrument webhook servers with p99 latency metrics; alert if p99 exceeds 500 ms, which is a leading indicator of API server latency degradation visible in `apiserver_admission_webhook_admission_duration_seconds`.

---

### Q: A team migrates a stateful EKS workload from a single large StatefulSet to multiple smaller StatefulSets for operational flexibility, and immediately observes that persistent volume provisioning is intermittently failing with "volume node affinity conflict." How do you diagnose and resolve this?

This error means a PersistentVolume was provisioned in an AZ that no schedulable node for the pod exists in. Diagnosis and resolution:

1. **Root cause**: When multiple StatefulSets are created simultaneously, the EBS CSI driver provisions volumes eagerly in whichever AZ the first scheduling attempt lands in; if nodes in that AZ are full or unavailable, subsequent pod scheduling fails with affinity conflict.
2. **Check node/PV AZ alignment**: Cross-reference `kubectl get pv -o yaml` (`spec.nodeAffinity.required`) against available nodes per AZ with `kubectl get nodes --label-columns topology.kubernetes.io/zone`.
3. **Immediate fix for stuck volumes**: Delete the PVC and pod, allow dynamic re-provisioning, or manually patch the PV's node affinity — though the safest path is deletion and re-creation.
4. **Structural fix — WaitForFirstConsumer**: Ensure all StorageClasses use `volumeBindingMode: WaitForFirstConsumer`; this delays volume provisioning until a pod is actually scheduled, co-locating the EBS volume with the selected node's AZ.
5. **Topology spread constraints**: Add `topologySpreadConstraints` across StatefulSets to distribute pods — and therefore volume provisioning — evenly across AZs.
6. **Karpenter consideration**: If using Karpenter, ensure `NodePool` AZ weights align with available EBS capacity; misaligned provisioning budgets can recreate the same problem.

---

### Q: How do you design an EKS strategy for managing cluster-level network egress costs, particularly inter-AZ data transfer charges that are invisible until the AWS bill arrives?

Inter-AZ traffic is one of the most common hidden cost drivers in EKS. A mature strategy addresses this at multiple layers:

- **Topology-aware routing**: Enable `topologyAwareHints` (Kubernetes 1.24+) or `service.kubernetes.io/topology-mode: auto` so kube-proxy or the AWS Load Balancer Controller prefers endpoints in the same AZ, reducing cross-AZ service traffic.
- **Affinity and spread alignment**: Use `podAffinity` or `topologySpreadConstraints` to co-locate tightly coupled services (e.g., app + cache) in the same AZ rather than spreading them for availability at a cost premium.
- **VPC flow log cost attribution**: Enable VPC flow logs with per-AZ source/destination tagging and feed them into Athena or CloudWatch Contributor Insights to identify chatty cross-AZ service pairs before they escalate.
- **CNI prefix delegation and local-zone awareness**: With prefix delegation, ensure node pools are AZ-scoped (separate node groups per AZ) so IP locality aligns with scheduling locality.
- **NAT Gateway consolidation**: A common mistake is routing all inter-AZ traffic through a centralised NAT Gateway in one AZ — each cross-AZ hop incurs $0.01/GB. Architect one NAT Gateway per AZ for outbound internet traffic.
- **FinOps feedback loops**: Integrate Kubecost or CAST AI with AWS Cost and Usage Reports to show per-team, per-namespace data transfer costs, creating accountability that drives architectural change organically.

---

### Q: Describe how you would handle a situation where a platform team needs to deprecate and remove a widely used internal Kubernetes Custom Resource Definition (CRD) that dozens of tenant teams depend on.

CRD deprecation is as much an organisational challenge as a technical one, and mishandling it breaks production workloads cluster-wide. A structured approach:

- **Inventory and impact assessment**: Use `kubectl get <crd-name> -A` and audit GitOps repos to enumerate every namespace, team, and manifest consuming the CRD before any communication goes out.
- **Versioned migration path**: Introduce a replacement CRD or API version first; run both in parallel, using a conversion webhook if the schema is compatible, so teams can migrate at their own pace within a defined window (typically 60–90 days for mature orgs).
- **Deprecation notices in-band**: Annotate existing custom resources with a deprecation warning annotation and configure an admission webhook to return warnings (`admission.k8s.io/warning`) on any CREATE or UPDATE of the old kind — surfacing the deprecation directly in CI/CD pipelines.
- **Governance gate**: Set a hard removal date in the platform roadmap, communicate it via RFC/ADR, and require team leads to sign off on completion. Use a shared migration tracker (Jira/Linear board) with per-namespace migration status.
- **Automated migration tooling**: Provide a migration script or Helm chart that converts old CRs to the new format, lowering the migration cost for teams and reducing the risk of inconsistent manual conversions.
- **Staged removal**: First remove the CRD from new cluster versions, then progressively remove it from existing clusters during the next upgrade cycle — ensuring that a missed team's workload fails noisily at upgrade time rather than silently at runtime.
- **Behavioral reflection**: In a retrospective, evaluate why the CRD became so entrenched without a versioning strategy from day one, and introduce a CRD lifecycle policy to prevent recurrence.
