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

## Run · 2026-09-01 18:09:00

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (6696 chars)
- How do you approach EKS cluster autoscaling — and when would you choose Karpenter over Cluster Autoscaler?
- Walk me through how you would harden EKS workloads to meet CIS Kubernetes Benchmark and SOC 2 requirements without blocking developer velocity.
- A deployment rollout on EKS is causing cascading failures because the new pods pass readiness checks but start returning 5xx errors under real traffic seconds later. How do you diagnose and prevent this?
- How do you design an EKS IAM strategy using IRSA and EKS Pod Identity, and what are the security pitfalls to avoid?

_Committed & pushed: yes_

## Run · 2026-09-02 18:24:43

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (6349 chars)
- How do you design and manage EKS control-plane and data-plane upgrades at scale with minimal disruption?
- Walk me through how you would debug and resolve an EKS networking issue where pods on different nodes cannot communicate intermittently.
- How do you design an EKS secret management strategy that satisfies both security and developer-experience requirements?
- A cost audit reveals your EKS workloads are consuming 60% more compute than capacity planning predicted. How do you investigate and remediate over-provisioning?

_Committed & pushed: yes_

## Run · 2026-09-03 18:19:53

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (6783 chars)
- How do you design an EKS storage strategy for stateful workloads, and what are the trade-offs between the available volume options?
- Walk me through how you would design and enforce a supply-chain security posture for container images running on EKS.
- Your EKS cluster's API server starts returning 429/503 errors intermittently during business hours. How do you diagnose and resolve this?
- How do you design an EKS service mesh strategy, and when is a service mesh the wrong answer?

_Committed & pushed: yes_

## Run · 2026-09-04 18:03:58

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7931 chars)
- How do you design an EKS pod security strategy post-PodSecurityPolicy deprecation, and what controls do you layer together?
- Your EKS cluster nodes are joining but pods remain in "Pending" with no scheduler events. How do you systematically diagnose and resolve this?
- How do you design an EKS disaster recovery strategy that accounts for both the control plane and stateful workload data, and how do you validate it?
- A security audit finds that several EKS workloads are making unexpected AWS API calls outside their intended permissions. How do you investigate the blast radius and harden the environment going forward?

_Committed & pushed: yes_

## Run · 2026-09-05 17:07:37

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7360 chars)
- How do you design an EKS networking strategy for IPv6, and what are the operational trade-offs compared to IPv4?
- How do you design an EKS add-on and cluster configuration drift-prevention strategy at scale?
- A newly onboarded EKS cluster in a regulated industry fails a CIS Kubernetes Benchmark scan. How do you systematically remediate it without breaking running workloads?
- How do you design an EKS strategy for machine-learning inference workloads that require GPU nodes, and what are the key operational pitfalls?

_Committed & pushed: yes_

## Run · 2026-09-06 17:30:01

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (6605 chars)
- How do you design an EKS ingress strategy at scale, and what are the trade-offs between the AWS Load Balancer Controller, NGINX, and Gateway API?
- Your EKS cluster's DNS resolution is intermittently timing out under load. How do you systematically diagnose and resolve this?
- How do you design an EKS workload identity and supply-chain security strategy to meet SLSA Level 3 requirements?
- A large EKS cluster is experiencing node-level "NotReady" flapping on a subset of nodes every few hours, but the nodes recover without manual intervention. How do you diagnose the root cause?

_Committed & pushed: yes_

## Run · 2026-09-07 18:59:11

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7877 chars)
- How do you design an EKS cluster networking strategy to support PrivateLink-based communication between clusters and external AWS services, and what are the operational pitfalls?
- Your EKS pods intermittently lose connectivity to an RDS Aurora cluster for 30–60 seconds, then self-recover. How do you diagnose and eliminate the root cause?
- How do you design an EKS platform team operating model — including cluster fleet topology, self-service developer experience, and guardrails — for an organisation with 50+ engineering teams?
- Walk me through how you would implement and operationalise fine-grained network segmentation for EKS workloads using both Kubernetes NetworkPolicy and AWS-native controls, and explain where each layer is insufficient alone.

_Committed & pushed: yes_

## Run · 2026-09-08 18:17:30

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (8045 chars)
- How do you design an EKS cluster bootstrap and node initialisation strategy to ensure nodes are security-hardened and configuration-compliant before they accept workloads?
- How do you design an EKS strategy for batch and queue-driven workloads — such as data-processing pipelines — and what are the trade-offs between Kubernetes Jobs, Kueue, and purpose-built AWS services like AWS Batch?
- A security team reports that a compromised pod in your EKS cluster has attempted a lateral movement attack by querying the EC2 Instance Metadata Service (IMDS) to harvest node IAM credentials. How do you contain the incident and harden the cluster long-term?
- How do you design an EKS platform for regulated financial services workloads that must comply with PCI-DSS and achieve sub-100 ms p99 latency SLAs simultaneously — and where do compliance and performance requirements conflict?

_Committed & pushed: yes_

## Run · 2026-09-09 18:17:56

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7081 chars)
- How do you design an EKS cluster observability strategy for cost attribution and chargeback across multiple teams sharing a cluster?
- A critical EKS workload shows correct pod logs but customers report partial request failures that never appear in application traces. How do you diagnose and resolve gaps in your distributed tracing pipeline?
- How do you design an EKS platform to support safe, progressive multi-cluster canary releases where traffic is shifted across clusters rather than within a single cluster?
- Describe a time you had to make a significant architectural decision on EKS under uncertainty, where the right answer wasn't clear. How did you frame the decision and what was the outcome?

_Committed & pushed: yes_

## Run · 2026-09-10 18:04:15

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7796 chars)
- How do you design an EKS strategy for Windows node workloads running alongside Linux nodes, and what are the key operational constraints?
- A team's EKS workload passes all load tests in staging but suffers from severe thundering-herd startup failures in production during a cold deployment. How do you diagnose and remediate this?
- How do you design an EKS cluster topology and scheduling strategy to support strict data-residency requirements where certain workloads must never leave a specific AWS Availability Zone?
- Describe how you would design an EKS-based platform to support secure, isolated development environments (per-developer or per-feature-branch) without runaway cost or cluster sprawl.

_Committed & pushed: yes_

## Run · 2026-09-11 18:09:47

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (8228 chars)
- How do you design an EKS cluster strategy for extremely latency-sensitive workloads — such as high-frequency trading or real-time bidding — where microsecond-level jitter is unacceptable?
- A cluster operator reports that Karpenter is repeatedly launching and terminating nodes in a tight loop — "thrashing" — causing instability and elevated AWS costs. How do you diagnose and resolve this?
- How do you design an EKS platform to support safe, zero-downtime schema migrations for stateful services that use relational databases, where both old and new pod versions coexist during a rolling deployment?
- Describe how you would design an EKS platform governance model — including policy guardrails, admission controls, and audit mechanisms — for a large enterprise with hundreds of development teams operating under a hub-and-spoke cluster topology.

_Committed & pushed: yes_

## Run · 2026-09-12 17:41:03

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (8182 chars)
- How do you design an EKS strategy for graceful pod disruption during node maintenance, and what are the common failure modes that cause SLA breaches?
- A multi-tenant EKS cluster starts hitting the 110-pod-per-node limit on several nodes, causing scheduling failures. How do you systematically address this without emergency cluster expansion?
- How do you design an EKS strategy for handling API deprecations across Kubernetes minor-version upgrades, and what governance mechanisms prevent deprecated APIs from blocking future upgrades?
- Describe how you would design an EKS-based platform to support a SaaS product where each customer requires a dedicated, isolated Kubernetes namespace with guaranteed resource quotas — and the customer count is expected to grow from 50 to 5,000 over 18 months.

_Committed & pushed: yes_

## Run · 2026-09-13 17:54:43

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (5994 chars)
- How do you design an EKS strategy for handling control-plane audit log volume at scale without incurring runaway CloudWatch costs?
- How do you design an EKS platform to enforce and validate resource quotas and admission policies as a hard multi-team governance boundary, and what breaks when you get it wrong?
- A blue/green cluster migration on EKS (moving workloads from an old cluster to a new one) is running weeks behind schedule and causing escalating risk. How do you diagnose the bottleneck and recover the programme?
- How do you design an EKS strategy for running and securing AI/LLM inference workloads that have large model artefacts, long startup times, and unpredictable per-request latency profiles?

_Committed & pushed: yes_

## Run · 2026-09-14 19:43:52

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7006 chars)
- How do you design an EKS strategy for handling IPv4 exhaustion in large VPCs, and what are the trade-offs between the available CIDR-extension approaches?
- A senior engineer proposes replacing all EKS managed node groups with fully self-managed node groups to gain more control. How do you evaluate and respond to this proposal?
- How do you design an EKS strategy for compliance-driven image scanning and runtime threat detection, and what are the gaps that each tool layer leaves?
- Describe how you would design the EKS cluster RBAC model for a platform team that must grant developers self-service access without allowing privilege escalation.

_Committed & pushed: yes_

## Run · 2026-09-15 18:42:28

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7473 chars)
- How do you design an EKS strategy for control-plane scalability when running thousands of Custom Resource Definitions and high-volume operators, and what are the failure modes to watch for?
- A team has enabled the EKS VPC CNI's network policy controller, but pods that should be isolated are still communicating freely. How do you systematically diagnose and fix this?
- How do you design an EKS platform to support tenant-level egress control — ensuring different teams' pods exit to the internet through different NAT Gateways or egress IPs — and what are the trade-offs?
- Describe how you would architect and operate an EKS cluster fleet upgrade program across 50+ clusters with varying team ownership, and what governance mechanisms prevent clusters from falling critically behind on Kubernetes versions.

_Committed & pushed: yes_

## Run · 2026-09-16 18:38:38

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7299 chars)
- How do you design an EKS strategy for handling cluster-level secrets rotation without causing application downtime, and what are the common failure modes?
- How do you design an EKS strategy for high-churn, short-lived job workloads — such as CI runners or ephemeral build environments — and what are the scaling and cost trade-offs?
- A multi-team EKS cluster is experiencing intermittent scheduling failures where pods sit in "Pending" despite nodes appearing to have sufficient CPU and memory. How do you systematically diagnose and resolve this?
- Describe a situation where you had to advocate against a business stakeholder's preferred EKS architectural decision. How did you handle the disagreement and what was the outcome?

_Committed & pushed: yes_

## Run · 2026-09-17 18:48:00

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7999 chars)
- How do you design an EKS strategy for handling node-level kernel and OS vulnerabilities on Bottlerocket and Amazon Linux 2023 managed nodes, and what are the operational trade-offs?
- A team reports that their EKS workload's HorizontalPodAutoscaler is not scaling despite CPU metrics being well above the target threshold. How do you systematically diagnose and resolve this?
- How do you design an EKS strategy for cost-optimised, resilient use of Spot Instances for production workloads, and what failure modes must you explicitly engineer against?
- Describe how you would lead a post-incident review after a major EKS outage, and what systemic changes you would drive to prevent recurrence. Walk through a realistic example.

_Committed & pushed: yes_

## Run · 2026-09-18 18:03:42

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (8168 chars)
- How do you design an EKS strategy for etcd health and API server request throttling as the cluster scales to thousands of nodes and tens of thousands of objects?
- A team wants to use EKS Fargate exclusively for all workloads to eliminate node management overhead. What are the architectural constraints you would surface before approving this, and under what conditions would you push back?
- How do you design an EKS multi-cluster fleet management strategy, including config synchronisation, policy enforcement, and visibility, without creating an unmanageable operational burden?
- Describe how you would conduct and structure a blameless post-mortem after a customer-impacting EKS incident, and how you translate its findings into durable architectural improvements rather than one-off fixes.

_Committed & pushed: yes_

## Run · 2026-09-19 17:45:33

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7533 chars)
- How do you design an EKS strategy for cross-cluster service discovery and traffic routing without a full service mesh?
- A team wants to adopt GitOps with Flux or Argo CD on EKS, but the cluster manages sensitive production workloads. What security boundaries and operational safeguards do you enforce?
- How do you design an EKS strategy for handling long-running, stateful gRPC streaming connections through AWS Load Balancer infrastructure, and what failure modes must you plan for?
- Describe how you would lead a blameless post-mortem after a major EKS production incident, and what structural outputs you expect to drive lasting improvement.

_Committed & pushed: yes_

## Run · 2026-09-20 17:55:56

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7024 chars)
- How do you design an EKS strategy for managing cluster upgrades at scale across a large fleet with minimal blast radius and zero unplanned downtime?
- A pod in your EKS cluster is consuming unbounded memory and triggering OOMKill repeatedly, but the owning team insists their application is functioning correctly. How do you investigate and resolve this systematically?
- How do you design an EKS strategy for federated identity and cross-account workload access without distributing long-lived credentials?
- Describe how you would design an EKS platform to support developer self-service namespace provisioning while maintaining hard security and cost guardrails.

_Committed & pushed: yes_

## Run · 2026-09-21 19:51:58

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7771 chars)
- How do you design an EKS strategy for managing and securing the AWS VPC CNI plugin at scale, including custom networking, prefix delegation, and security group per pod?
- A production EKS deployment using Argo CD suddenly has hundreds of applications flipping to "OutOfSync" simultaneously with no recent git commits. How do you diagnose and resolve this?
- How do you design an EKS strategy for cluster autoscaling decisions when workloads have highly heterogeneous resource profiles — mixing CPU-heavy, memory-heavy, and GPU jobs on the same cluster?
- Describe a situation where an EKS platform you owned suffered an unexpected outage caused by a dependency you did not control. What happened, how did you respond, and what architectural changes did you make afterward?

_Committed & pushed: yes_
