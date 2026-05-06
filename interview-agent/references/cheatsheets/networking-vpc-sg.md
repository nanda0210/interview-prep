# Cheatsheet — Networking (VPC / SG / NACL / Routing)

## VPC building blocks (mental model)
```
Internet ── IGW ── public subnet ── NAT GW ── private subnet ── workloads
                                       │
                                       └─ TGW ─ other VPCs / on-prem
                                       └─ VPC endpoints ─ AWS services privately
                                       └─ VPN ─ corp / partner
```

## Subnets — sizing rule of thumb
- EKS wants ≥ /24 per subnet × 3 AZs.
- Pods burn IPs (1 per pod with VPC CNI). Use **prefix delegation** to multiply ENI capacity by ×16.
- Reserve secondary CIDR (e.g. 100.64.0.0/16) just for pods if VPC is tight.

## Security Group vs NACL
| | SG | NACL |
|---|---|---|
| Stateful | yes | no |
| Layer | ENI | subnet |
| Allow/Deny | allow only | allow + deny, ordered |
| Use case | normal access control | blanket block / DDoS triage |

## EKS SG topology
- **Cluster SG** (auto): control-plane ↔ nodes, intra-cluster.
- **Node SG** (you): SSH, scrape, datadog, etc.
- **Additional cluster SG** (you, optional): extra inbound to control plane.
- **SG-for-Pods** (`SecurityGroupPolicy`): per-pod SG via Trunk ENI (m5+, c5+, etc.).

## Common inbound rules for EKS
| Source | Port | Purpose |
|---|---|---|
| Cluster SG | 443 | API server → kubelet |
| Cluster SG | 10250 | metrics-server, exec, logs |
| Self (node SG) | all | pod-to-pod |
| ALB SG | NodePort range / pod port | LB → pod |

## Egress
- **No proxy:** straight to NAT GW → IGW → AWS APIs.
- **Proxy:** NodeConfig + container env `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` (must include `.svc,.cluster.local,169.254.169.254,<vpc-cidr>,<pod-cidr>,<service-cidr>`).
- **VPC endpoints:** Interface (PrivateLink, $/hour) for STS/SM/ECR/Logs; Gateway (free) for S3 + DynamoDB.

## Diagnose "pod can't reach X"
1. DNS: `kubectl exec -- nslookup x` → CoreDNS healthy?
2. SG: source SG (pod or node) outbound to dest port.
3. Dest SG: inbound from source SG / CIDR.
4. NACL on either subnet.
5. Route table on source subnet → dest CIDR routed via NAT/TGW/endpoint?
6. If VPC endpoint: endpoint policy; private DNS on?
7. Proxy env: is the dest in NO_PROXY?
