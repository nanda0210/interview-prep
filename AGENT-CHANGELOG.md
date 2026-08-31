# Agent Changelog

Daily log of content appended by the interview-prep monitoring agent.

## Run · 2026-08-15 12:44:05

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (5353 chars)
- How do you design multi-tenant isolation in EKS when multiple teams or customers share the same cluster?
- Walk me through how you would troubleshoot intermittent pod-to-pod connectivity failures in a VPC CNI-based EKS cluster.
- Compare the trade-offs between using AWS Fargate for EKS versus managed EC2 node groups. When would you choose each?
- Describe your approach to GitOps-based continuous delivery on EKS. What tooling choices would you make and what failure modes do you guard against?

_Committed & pushed: no_

## Run · 2026-08-29 16:32:37

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (5729 chars)
- How do you design a cost-optimised EKS compute strategy using Spot Instances, and how do you handle interruptions gracefully?
- Walk me through how you secure the EKS API server and the data plane network, from IAM through to pod-level controls.
- How do you architect observability for a large EKS fleet — metrics, logs, and traces — without creating runaway cost or operational toil?
- Tell me about a time an EKS upgrade caused a production incident. What happened, what was your remediation, and what did you change permanently?

_Committed & pushed: yes_

## Run · 2026-08-30 18:24:18

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7257 chars)
- How do you design a secure, scalable EKS networking architecture — including CNI choice, network policies, and ingress — for a highly regulated environment?
- Walk me through how you would implement robust secrets management for workloads running in EKS, and what the failure modes of each approach are.
- Describe how you would architect EKS cluster autoscaling in 2024 — Cluster Autoscaler versus Karpenter — and when each is appropriate.
- A team reports that their pods are experiencing intermittent "OOMKilled" events, but the application developers insist memory usage looks fine in their profiling tools. How do you systematically diagnose and resolve this?

_Committed & pushed: yes_

## Run · 2026-08-31 20:38:51

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7067 chars)
- How do you design a highly available, cross-region EKS strategy for a workload that requires near-zero RTO and RPO?
- Walk me through how you would harden an EKS cluster to meet CIS Benchmark and SOC 2 requirements without crippling developer velocity.
- Explain how EKS Pod Identity (the newer mechanism) differs from IRSA, and when you would migrate to it.
- A critical microservice on EKS is experiencing high tail latency (p99) during peak load but p50 is fine. How do you systematically diagnose and resolve it?

_Committed & pushed: yes_
