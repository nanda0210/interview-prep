# Cheatsheet — IAM: IRSA vs Pod Identity vs Node Role

## Decision matrix
| Need | Use |
|---|---|
| New cluster, fresh design | **Pod Identity** |
| Legacy cluster, projected-token tooling | **IRSA** |
| Cluster-wide blanket creds (anti-pattern) | Node role |
| Multi-cluster, one role | Pod Identity (associations) |
| Cross-account assume-role | IRSA → STS chain or PI → STS chain |

## IRSA — anatomy
1. EKS publishes an OIDC issuer URL.
2. You create an IAM OIDC provider for that URL in the account.
3. You create an IAM role with trust:
```json
{
  "Effect": "Allow",
  "Principal": {"Federated": "arn:aws:iam::ACCT:oidc-provider/oidc.eks.us-west-2.amazonaws.com/id/EXAMPLE"},
  "Action": "sts:AssumeRoleWithWebIdentity",
  "Condition": {
    "StringEquals": {
      "oidc.eks.us-west-2.amazonaws.com/id/EXAMPLE:sub": "system:serviceaccount:NS:SA",
      "oidc.eks.us-west-2.amazonaws.com/id/EXAMPLE:aud": "sts.amazonaws.com"
    }
  }
}
```
4. Annotate SA: `eks.amazonaws.com/role-arn: arn:aws:iam::ACCT:role/ROLE`.
5. Pod gets projected token at `/var/run/secrets/eks.amazonaws.com/serviceaccount/token`.

## Pod Identity — anatomy
1. Install **EKS Pod Identity Agent** addon (DaemonSet).
2. Trust policy is just:
```json
{ "Effect": "Allow",
  "Principal": {"Service": "pods.eks.amazonaws.com"},
  "Action": ["sts:AssumeRole", "sts:TagSession"] }
```
3. Create a **PodIdentityAssociation**: `(cluster, namespace, sa, role-arn)`.
4. No SA annotation, no OIDC provider per cluster.

## Common bugs
- IRSA: missing `:aud` → `WebIdentityErr`.
- IRSA: missing `:sub` condition → privilege escalation across SAs.
- Pod Identity: agent DaemonSet missing on node → SDK falls back to IMDS (node role).
- Wrong OIDC thumbprint after IdP rotation (rare; AWS usually auto-handles).

## How to verify inside a pod
```bash
aws sts get-caller-identity
# Look at the Arn — should be the *role* you expect, not the node role.
```
