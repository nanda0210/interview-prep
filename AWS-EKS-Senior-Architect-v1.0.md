# AWS / EKS Senior Architect — Interview Prep · v1.0

> Single-file study document for a senior-software-developer / architect role
> spanning AWS networking, EKS, Karpenter, ArgoCD, External Secrets, Helm,
> CI/CD, and application onboarding. Treat this as your **night-before**
> manual: skim the architecture, drill the steps, then run the questions.

**Last updated:** Apr 30, 2026 · **Version:** 1.0

---

## Table of contents

1. [Architecture overview](#1-architecture-overview)
2. [End-to-end setup, in order (Phases 1–10)](#2-end-to-end-setup-in-order)
3. [Workflow diagram](#3-workflow-diagram-ascii)
4. [Cheat-sheet: core services & when to pick what](#4-cheat-sheet-core-services--when-to-pick-what)
5. [Technical interview questions (with answers)](#5-technical-interview-questions)
6. [STAR behavioural questions (Situation · Task · Action · Result)](#6-star-behavioural-questions)
7. [Top FAANG-style questions](#7-top-faang-style-questions)
8. [Common pitfalls / "gotchas" to mention](#8-common-pitfalls--gotchas-to-mention)
9. [Day-of-interview checklist](#9-day-of-interview-checklist)

---

## 1. Architecture overview

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

## 2. End-to-end setup, in order

### Phase 1 — Network foundations (in the network account)

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

### Phase 2 — IAM & permissions

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

### Phase 3 — EKS cluster bootstrap

1. **Create cluster** (Terraform / CDK / eksctl). Use private endpoint with public-via-allowlist if external `kubectl` is needed.
2. **Add-ons** (managed): VPC CNI, kube-proxy, CoreDNS, EKS Pod Identity Agent, EBS CSI driver, EFS CSI driver, AWS Load Balancer Controller.
3. **CoreDNS sizing:** scale replicas to 2 minimum, set HPA for high-throughput clusters. Configure NodeLocal DNS Cache to reduce CoreDNS load.
4. **VPC CNI:** enable **prefix delegation** (`ENABLE_PREFIX_DELEGATION=true`) to massively increase pod-density per node. Enable **WARM_PREFIX_TARGET** so node startup doesn't block on ENI ops.
5. **Logging:** enable cluster control-plane logs → CloudWatch (api, audit, authenticator, controllerManager, scheduler).
6. **kube-system network policies** to restrict pod-to-pod traffic by default once steady-state.

### Phase 4 — Karpenter (autoscaling)

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

### Phase 5 — ArgoCD (GitOps)

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

### Phase 6 — External Secrets Operator (secrets)

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

### Phase 7 — Storage (EFS)

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

### Phase 8 — Load balancers

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

### Phase 9 — Application onboarding (the developer-facing flow)

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

### Phase 10 — Observability & Day 2

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

## 3. Workflow diagram (ASCII)

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

## 4. Cheat-sheet: core services & when to pick what

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

## 5. Technical interview questions

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

## 6. STAR behavioural questions

> Use these as scaffolding for your real stories. Replace **\<\<placeholder\>\>** with concrete numbers / dates from your work.

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

## 7. Top FAANG-style questions

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

## 8. Common pitfalls / "gotchas" to mention

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

## 9. Day-of-interview checklist

| Before | What |
|---|---|
| 24 h before | Re-read the architecture diagram, draw it from memory once. |
| 2 h before | Skim STAR section 6 — pick 3 stories you'd lead with. |
| 1 h before | Open the cheat-sheet (§4). Practice one whiteboard answer aloud. |
| 5 min before | Water, deep breath. You don't need to be perfect, just clear. |

| During | What |
|---|---|
| Every answer | **Frame** the problem before solving. Two-sentence restatement: "What I think you're asking is X. The trade-off is between Y and Z. I'd start with…". |
| When stuck | Talk out loud. "I'm not sure between A and B — let me think about which dimension matters most for your use case." Senior interviewers reward visible reasoning. |
| When you don't know | Say it once, briefly, then say what you'd do to find out. "I haven't run that at scale. Here's how I'd start a small POC to learn." |
| When you do know | Lead with the answer. Detail second. "Karpenter — because of consolidation. Specifically, it…" |

| After | What |
|---|---|
| End of each round | Three questions for them: about scope, ownership, on-call rotation, the team's biggest current pain. |
| End of the day | Send a short thank-you note within 24 h. |

---

> **You've got this.** Confidence comes from preparation. You've prepared. Walk in like you've already done the job — because you have.

— *AWS / EKS Senior Architect Interview Prep · v1.0 · Apr 30, 2026*

---

## Appendix A — Practical commands & manifests (whiteboard-ready)

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

## Appendix B — Deep-dive answers to selected FAANG questions

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

## Appendix C — Security baseline (one-page)

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

## Appendix D — Disaster recovery & backups (talking-points)

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

## Appendix E — Two more STAR stories (extra ammo)

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

## Appendix F — Recap: 30-second elevator pitch for "what's your stack?"

Memorise this. Variant of it works in 95% of interviews.

> *"Multi-account AWS with a network account holding the Transit Gateway, IGW/NAT, and VPN. Application accounts each run an EKS cluster with **Karpenter** for node autoscaling — picks Spot for stateless, on-demand for system. **ArgoCD** handles GitOps from a `gitops/` monorepo using app-of-apps + ApplicationSets. Pods authenticate to AWS via **EKS Pod Identity** — simpler than IRSA. Secrets come from **External Secrets Operator** projecting from AWS Secrets Manager. **AWS Load Balancer Controller** terminates TLS at ALBs in IP target mode. **EFS** for ReadWriteMany; EBS via the managed CSI for ReadWriteOnce. Networking: VPC CNI with prefix delegation, NodeLocal DNSCache to offload CoreDNS. Observability is Prometheus + AMP, Fluent Bit → CloudWatch, X-Ray for traces, Kubecost for chargeback. Multi-tenant via namespace + NetworkPolicy + ResourceQuota + Karpenter NodePool taints by trust tier."*

That's the whole stack in 90 seconds. The interviewer will pick a thread to drill into — you've already mapped each thread in this document.

---

*Real end of v1.0. Good luck.*

