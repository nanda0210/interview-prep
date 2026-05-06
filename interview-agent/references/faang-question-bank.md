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
