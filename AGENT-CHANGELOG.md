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

## Run · 2026-09-22 18:29:30

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (6938 chars)
- How do you design an EKS strategy for webhook-heavy clusters where validating and mutating admission webhooks become a reliability and latency bottleneck?
- A team migrates a stateful EKS workload from a single large StatefulSet to multiple smaller StatefulSets for operational flexibility, and immediately observes that persistent volume provisioning is intermittently failing with "volume node affinity conflict." How do you diagnose and resolve this?
- How do you design an EKS strategy for managing cluster-level network egress costs, particularly inter-AZ data transfer charges that are invisible until the AWS bill arrives?
- Describe how you would handle a situation where a platform team needs to deprecate and remove a widely used internal Kubernetes Custom Resource Definition (CRD) that dozens of tenant teams depend on.

_Committed & pushed: yes_

## Run · 2026-09-23 18:49:58

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7260 chars)
- How do you design an EKS strategy for handling service account token projection and audience validation to prevent cross-service token misuse?
- A Karpenter-provisioned node fails to join the EKS cluster within the registration timeout window, causing workload scheduling delays. How do you diagnose and remediate this systematically?
- How do you design an EKS strategy for zero-trust pod-to-pod communication within a cluster, and what are the practical limitations of each enforcement layer?
- Describe how you would design a disaster recovery (DR) strategy for an EKS-hosted platform with an RTO of 30 minutes and RPO of 5 minutes, and what are the hardest parts to achieve in practice?

_Committed & pushed: yes_

## Run · 2026-09-24 18:49:39

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7599 chars)
- How do you design an EKS strategy for managing and securing Helm releases at scale across a multi-team cluster fleet, and what governance controls prevent configuration drift?
- A node in your EKS cluster is marked "Ready" by the Kubernetes API but workloads on it are silently dropping requests. How do you systematically identify and remediate the root cause?
- How do you design an EKS strategy for managing cluster add-on lifecycle — such as CoreDNS, kube-proxy, and VPC CNI — to avoid version skew and reduce toil across a large cluster fleet?
- Describe a situation where you identified a systemic EKS reliability risk that was not on anyone's radar. How did you surface it, build alignment, and drive remediation?

_Committed & pushed: yes_

## Run · 2026-09-25 19:07:33

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (8005 chars)
- How do you design an EKS strategy for managing and rotating mTLS certificates for service-to-service communication without a full service mesh, and what are the operational failure modes?
- A team running EKS reports that their pods are being evicted at a high rate during business hours despite nodes showing available memory in `kubectl describe node`. What is your diagnostic and remediation approach?
- How do you design an EKS strategy for multi-region active-active workloads where both regions must serve writes simultaneously, and what are the irreducible distributed-systems constraints you must communicate to stakeholders?
- Describe a situation where a cost optimisation initiative on EKS had unintended reliability consequences, and how you detected, resolved, and institutionalised learnings from it.

_Committed & pushed: yes_

## Run · 2026-09-26 18:17:29

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (6998 chars)
- How do you design an EKS strategy for managing and enforcing Pod Security Standards (PSS) across a multi-team cluster fleet, and what are the operational gaps left by the built-in admission controller?
- A team reports that their EKS service's P99 latency spikes sharply every 30 minutes like clockwork, even under constant load. How do you systematically diagnose and resolve this?
- How do you design an EKS strategy for managing and surfacing Kubernetes events at scale for operational awareness without overwhelming your observability backend?
- Describe a situation where a platform decision you made early in an EKS architecture created significant operational debt later. What would you do differently, and how do you now guard against this class of mistake?

_Committed & pushed: yes_

## Run · 2026-09-27 18:53:25

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7230 chars)
- How do you design an EKS strategy for managing and enforcing fine-grained IAM permissions for workloads using IRSA at scale, and what failure modes should architects anticipate?
- A production EKS cluster's CoreDNS pods are healthy, but intermittent DNS resolution failures are causing cascading service timeouts. How do you systematically diagnose and resolve this?
- How do you design an EKS strategy for secure, auditable, and operationally safe `kubectl` access for engineers across multiple teams and clusters, without distributing long-lived kubeconfig credentials?
- Describe a situation where a seemingly routine EKS cluster upgrade caused a production incident that wasn't caught in staging. What systemic controls did you put in place afterward?

_Committed & pushed: yes_

## Run · 2026-09-28 21:03:52

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7172 chars)
- How do you design an EKS strategy for managing and enforcing network segmentation between tenants in a shared cluster using a combination of Kubernetes NetworkPolicy and AWS-native controls?
- A production EKS cluster's Cluster Autoscaler (or Karpenter) is consistently under-provisioning during sudden, sharp traffic spikes, causing 30–60 seconds of pod-pending time before new nodes are ready. How do you diagnose and architect a solution?
- Describe a situation where a change to an EKS cluster's IAM or RBAC configuration caused an unintended privilege escalation. How did you detect it, contain it, and what systemic changes did you make afterward?
- How do you design an EKS strategy for observability data cardinality explosions caused by high-label-count metrics from large-scale workloads, and what are the architectural trade-offs between Prometheus, AMP, and ADOT?

_Committed & pushed: yes_

## Run · 2026-09-29 19:46:58

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (8113 chars)
- How do you design an EKS strategy for managing and enforcing resource-based network policies at the AWS level (security groups per pod) alongside Kubernetes-native network policies, and what are the operational pitfalls of running both simultaneously?
- A critical EKS workload is experiencing periodic "context deadline exceeded" errors on API server calls from within the cluster, but external kubectl commands succeed. How do you systematically diagnose and resolve this?
- How do you design an EKS strategy for managing multi-architecture (x86_64 and ARM64/Graviton) node pools within the same cluster, and what are the failure modes teams encounter when they first migrate workloads?
- Describe a situation where you had to re-architect EKS networking mid-flight because the initial design could not support the scale the platform reached. What were the signals, the constraints, and the migration path?

_Committed & pushed: yes_

## Run · 2026-09-30 19:48:27

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7890 chars)
- How do you design an EKS strategy for managing persistent volume lifecycle — including provisioning, resizing, snapshotting, and cross-AZ recovery — for stateful workloads at scale?
- A production EKS cluster running a service mesh (Istio or AWS App Mesh) is exhibiting a sudden increase in 503 errors between two services that were communicating correctly the day before. No application code was changed. Walk me through your investigation.
- How do you design an EKS strategy for managing and enforcing cost allocation and chargeback for shared multi-tenant clusters, and what are the gaps you cannot fully close?
- Describe a situation where you had to design or rescue an EKS cluster that was approaching or hitting Kubernetes API rate limits (client-side 429s), and how you systematically identified and remediated the top throttling sources.

_Committed & pushed: yes_

## Run · 2026-10-01 20:05:52

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7984 chars)
- How do you design an EKS strategy for managing and enforcing OPA/Gatekeeper or Kyverno policy-as-code at scale across a multi-team cluster fleet, and how do you handle policy drift and exemption management?
- A production EKS workload suddenly shows a large number of pods stuck in "Terminating" for hours. The owning team has already tried `kubectl delete pod --force`. Walk through your systematic diagnosis and resolution approach.
- How do you design an EKS strategy for managing cluster-level audit log ingestion, retention, and alerting without incurring runaway costs as cluster scale and API call volume grow?
- Describe a situation where you had to design or significantly evolve the EKS platform team's operating model — including on-call, SLO ownership, and the boundary between platform and application teams. What were the hardest organisational trade-offs?

_Committed & pushed: yes_

## Run · 2026-10-02 19:44:42

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (6752 chars)
- How do you design an EKS strategy for managing IPv4 address exhaustion in large-scale clusters, and what are the trade-offs between available mitigation approaches?
- A production EKS cluster's AWS Load Balancer Controller stops reconciling Ingress objects after a routine IAM policy update. Services are unreachable for newly deployed applications. How do you diagnose and recover?
- How do you design an EKS strategy for managing workload identity at the boundary between Kubernetes and on-premises systems that cannot use AWS IAM, and what are the security controls you apply?
- Describe a situation where you had to make a significant architectural trade-off between EKS operational simplicity and security posture under business time pressure. What did you decide, and what did you do to manage the residual risk?

_Committed & pushed: yes_

## Run · 2026-10-03 18:32:01

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7548 chars)
- How do you design an EKS strategy for managing and enforcing image supply-chain security — from build to runtime — across a multi-team cluster fleet?
- A production EKS cluster's VPC CNI (aws-node) DaemonSet is exhausting ENI and IP address capacity on nodes, causing new pods to remain in "ContainerCreating" indefinitely. How do you diagnose and resolve this?
- How do you design an EKS strategy for managing cluster-level API server availability and request prioritisation when a runaway controller or batch job floods the API server with requests?
- Describe a situation where you had to design or justify a move from a shared multi-tenant EKS cluster to dedicated per-team clusters, or vice versa. What drove the decision and what did you learn?

_Committed & pushed: yes_

## Run · 2026-10-04 18:31:42

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (8434 chars)
- How do you design an EKS strategy for managing and enforcing namespace-level resource quotas and LimitRanges across a large multi-team cluster without becoming a bottleneck to team velocity?
- A security audit finds that several EKS workloads are sharing a single IAM role via IRSA, granting them collectively more permissions than any individual workload needs. How do you remediate this at scale without causing service disruption?
- How do you design an EKS strategy for graceful node termination that ensures zero in-flight request loss during Spot reclamation, cluster autoscaler scale-in, or rolling node group upgrades?
- Describe a situation where you had to design or enforce a migration from kube-proxy iptables mode to a more scalable networking data plane (e.g., eBPF/Cilium) on a live EKS cluster. What were the risks, and how did you manage them?

_Committed & pushed: yes_

## Run · 2026-10-05 21:48:59

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (8630 chars)
- How do you design an EKS strategy for managing workload disruption budgets (PodDisruptionBudgets) at scale to prevent cascading unavailability during cluster maintenance or node recycling events?
- A high-throughput EKS workload suddenly begins experiencing elevated TCP connection reset errors after AWS announced an underlying EC2 instance type retirement and nodes were automatically migrated. How do you diagnose and resolve this?
- How do you design an EKS strategy for managing secrets rotation — including database credentials, API keys, and TLS certificates — with zero application downtime and full auditability?
- Describe a situation where you had to design a strategy to handle EKS control plane API server rate limiting (HTTP 429 / "client-side throttling" errors) caused by a proliferation of controllers and operators running in the cluster.

_Committed & pushed: yes_

## Run · 2026-10-06 19:58:27

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7187 chars)
- How do you design an EKS strategy for managing node-level kernel and OS-level tuning (sysctl, ulimits, hugepages) for performance-sensitive workloads without violating Pod Security Standards?
- A production EKS cluster's Horizontal Pod Autoscaler is oscillating — scaling up and immediately back down in rapid cycles — causing repeated pod churn and degraded service availability. How do you diagnose and resolve this?
- Describe a situation where you had to justify and implement an EKS control plane logging and observability strategy to satisfy a regulatory compliance requirement (e.g., PCI-DSS, SOC 2, or FedRAMP). What architectural decisions did you make and what were the hardest trade-offs?
- How do you design an EKS strategy for managing and enforcing topology-aware scheduling — including AZ spread, node affinity, and pod topology spread constraints — to maximise both availability and cost efficiency simultaneously?

_Committed & pushed: yes_

## Run · 2026-10-07 20:24:40

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (8008 chars)
- How do you design an EKS strategy for managing etcd-backed Kubernetes object bloat — such as excessive ConfigMaps, Secrets, and Events — to prevent API server degradation at scale?
- A blue/green EKS cluster upgrade is underway and traffic has been shifted to the green cluster, but post-cutover you observe that the green cluster's Service accounts are not inheriting the correct IRSA annotations from the blue cluster. How do you diagnose and prevent this class of migration failure?
- How do you design an EKS strategy for managing and enforcing Kubernetes API deprecation across a large cluster fleet ahead of version upgrades, and how do you operationalize this at the platform team level?
- Describe a situation where you had to design or enforce a strategy for managing EKS node group AMI currency — balancing security patching cadence against stability — and what organizational friction you encountered.

_Committed & pushed: yes_

## Run · 2026-10-08 20:29:42

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (8066 chars)
- How do you design an EKS strategy for managing and enforcing Pod disruption and termination safety for batch and ML training workloads that cannot tolerate mid-job node preemption?
- A production EKS cluster suddenly shows a sharp rise in `etcd request duration` and API server `watch` event latency. Control-plane metrics are healthy otherwise. How do you diagnose and remediate?
- How do you design an EKS strategy for managing and enforcing GPU resource allocation, isolation, and observability for multi-tenant ML workloads on the same cluster?
- Describe a situation where you had to design or enforce an EKS cluster fleet-wide incident response and forensics capability — including what data you preserved, how you contained blast radius, and what you changed architecturally afterwards.

_Committed & pushed: yes_

## Run · 2026-10-09 19:59:29

**1 file(s) updated** by sub-agents:

### 📄 AWS-EKS-Senior-Architect-v1.0.md  ·  +4 Q&A  (7569 chars)
- How do you design an EKS strategy for managing and enforcing FinOps practices around Spot Instance usage at scale, including handling interruption-driven cost spikes and ensuring workload suitability gates?
- A production EKS cluster's Vertical Pod Autoscaler (VPA) is causing repeated pod evictions and OOMKills in a feedback loop. How do you diagnose and resolve this without disabling VPA entirely?
- How do you design an EKS strategy for managing and enforcing cluster-wide admission control rollout safely — ensuring new webhook policies don't cause unintended deployment failures across teams?
- Describe a situation where EKS cross-account or cross-cluster service mesh federation introduced unexpected latency or reliability problems, and how you resolved it.

_Committed & pushed: yes_
