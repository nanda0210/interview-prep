# Cheatsheet — AWS EKS

## Anatomy
- **Control plane:** AWS-managed, 3 AZ, 99.95% SLA. You don't see EC2.
- **Data plane:** managed node groups (MNG) | self-managed nodes | Fargate | Karpenter.
- **API access:** kubeconfig → STS → `aws-iam-authenticator` (or EKS access entries).

## Versions / upgrade order
1. Control plane (`aws eks update-cluster-version`).
2. Core addons: `vpc-cni`, `coredns`, `kube-proxy` (match new k8s version).
3. Node groups (MNG: `update-nodegroup-version` with rolling) **or** Karpenter NodePools (bump AMI selector → `expireAfter`).
4. Smoke + ArgoCD drift check.

## Endpoint access
| Mode | API server reachable from |
|---|---|
| Public | Internet (whitelist via `publicAccessCidrs`) |
| Private | VPC only (needs hosted-zone records auto-managed) |
| Both | Both |

## Cluster-creator footgun
The IAM principal that *created* the cluster has implicit `system:masters` and **cannot be removed**. Always create with a dedicated automation role.

## Logs (control plane)
Enable: `api`, `audit`, `authenticator`, `controllerManager`, `scheduler` → CloudWatch.

## Useful one-liners
```bash
aws eks update-kubeconfig --name <cluster> --region <region>
kubectl get nodes -o wide
kubectl top pods -A --sort-by=memory
aws eks describe-cluster --name <c> --query 'cluster.identity.oidc.issuer'
aws eks list-access-entries --cluster-name <c>
```
