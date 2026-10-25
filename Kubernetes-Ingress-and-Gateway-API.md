# Kubernetes Ingress & Gateway API

A reference for external traffic routing in Kubernetes — what Ingress does, why
Gateway API replaced it, and where an API Gateway fits.

**Contents**

- [The three layers at a glance](#the-three-layers-at-a-glance)
- [Part 1 — Ingress](#part-1--ingress)
  - [What it is](#what-it-is)
  - [Why use it](#why-use-it)
  - [The Ingress Controller](#the-ingress-controller)
  - [Ingress vs Service](#ingress-vs-service)
  - [Path-based routing](#path-based-routing)
  - [Host-based routing](#host-based-routing)
  - [TLS termination](#tls-termination)
  - [pathType](#pathtype)
  - [Architecture](#architecture)
  - [Troubleshooting](#troubleshooting)
- [Part 2 — Gateway API](#part-2--gateway-api)
- [Part 3 — API Gateway](#part-3--api-gateway)
- [Choosing between them](#choosing-between-them)
- [Quick answers](#quick-answers)

---

## The three layers at a glance

| | Ingress | Gateway API | API Gateway |
|---|---|---|---|
| **Scope** | One cluster, single namespace | One cluster, multiple namespaces | Multiple clusters, external backends |
| **Type** | Kubernetes API object | Kubernetes API objects | Product, usually outside the cluster |
| **Routing** | Host and path | `HTTPRoute`, `TCPRoute`, `GRPCRoute` | Routes and APIs with versioning, transforms, policies |
| **Implementations** | NGINX, Traefik, HAProxy | Istio, NGINX, Contour | Kong, Apigee, AWS API Gateway, Traefik Hub |
| **Extensibility** | Annotations | Typed resources | Full policy engine |

They compose rather than compete: an API Gateway at the edge, Gateway API
inside the cluster.

---

# Part 1 — Ingress

## What it is

A Kubernetes API object that manages **external HTTP/HTTPS traffic** entering
the cluster and routes it to Services.

- Provides a **single entry point** for multiple applications
- Supports **host-based** and **path-based** routing
- Operates at layer 7, primarily HTTP/HTTPS

```
Internet → Ingress (HTTP/HTTPS) → Service A (/app1) → Pods
                                → Service B (/app2) → Pods
```

## Why use it

Without Ingress, every Service you expose needs its own public IP or cloud
LoadBalancer. That is expensive, hard to manage, and doesn't scale.

| Without Ingress | With Ingress |
|---|---|
| A separate public IP / LoadBalancer per service | One entry point for all services |
| Difficult to manage | Routing rules in one place |
| Not scalable | Scalable and clean |

The cost argument is the one to lead with: cloud load balancers are billed per
hour, per rule, and per GB. Ingress collapses many into one.

## The Ingress Controller

An Ingress object on its own does **nothing**. It is a set of rules; the
controller is the component that reads them and acts.

- Watches Ingress resources and implements their rules
- Configures a reverse proxy to route traffic to the correct Services

Common controllers: **NGINX**, **Traefik**, **HAProxy**, and cloud-specific
ones such as the AWS Load Balancer Controller.

```
Ingress (rules) → Ingress Controller (implements them)
                        ↓
                 Services → Pods
```

> A cluster with no Ingress Controller installed will accept your Ingress YAML
> without complaint and route nothing. This is the single most common reason a
> "correct" Ingress does not work.

## Ingress vs Service

| Service | Ingress |
|---|---|
| Stable network access to Pods | HTTP/HTTPS routing |
| Connects clients to Pods | Routes requests to Services |
| ClusterIP, NodePort, LoadBalancer | Host-based and path-based rules |
| Supports TCP/UDP | Primarily HTTP/HTTPS |
| Usually internal | Usually external |

**Ingress does not replace a Service.** They work in sequence:

```
Internet → Ingress → Service → Pods
```

Ingress handles external routing *to* Services; Services route *to* Pods.

## Path-based routing

Routes to different Services based on URL path.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: example-ingress
spec:
  rules:
    - http:
        paths:
          - path: /app1
            pathType: Prefix
            backend:
              service:
                name: frontend
                port:
                  number: 80
          - path: /app2
            pathType: Prefix
            backend:
              service:
                name: backend
                port:
                  number: 80
```

## Host-based routing

Routes on hostname — for multiple applications on different domains.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: host-ingress
spec:
  rules:
    - host: app1.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: frontend
                port:
                  number: 80
    - host: app2.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: backend
                port:
                  number: 80
```

## TLS termination

Ingress can terminate HTTPS using a TLS Secret that holds the certificate and
private key.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tls-ingress
spec:
  tls:
    - hosts:
        - example.com
      secretName: example-tls
  rules:
    - host: example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: frontend
                port:
                  number: 80
```

Create the Secret:

```bash
kubectl create secret tls example-tls --cert=tls.crt --key=tls.key
```

The Secret must live in the **same namespace** as the Ingress.

## pathType

Defines how a path is matched against the incoming request.

| pathType | Meaning |
|---|---|
| `Prefix` | Matches the path prefix. Most commonly used. |
| `Exact` | Matches the exact path only. |
| `ImplementationSpecific` | Behaviour depends on the controller. |

```yaml
path: /api
pathType: Prefix     # matches /api and /api/users
```

`pathType` is **required** in `networking.k8s.io/v1`. Omitting it is a common
leftover habit from the old `extensions/v1beta1` API.

## Architecture

```
Client (HTTP/HTTPS)
      ↓
   Internet
      ↓
Ingress Controller   (Load Balancer / NodePort)
      ↓
   Ingress           (routing rules)
      ↓
  Services
      ↓
    Pods
```

## Troubleshooting

Work outside-in.

```bash
# 1. The Ingress resource
kubectl get ingress
kubectl describe ingress <name>

# 2. The Ingress Controller
kubectl get pods -n <ingress-namespace>
kubectl logs <controller-pod>

# 3. Services and Endpoints
kubectl get svc
kubectl get endpoints          # empty = selector/label mismatch

# 4. Rules — host, path, annotations
# 5. DNS and TLS certificates
# 6. Application logs
```

**Common causes**

| Symptom | Likely cause |
|---|---|
| Nothing routes at all | Ingress Controller not running |
| 404 from the proxy | Incorrect host or path |
| 502 / 503 | Service not reachable, or wrong service name/port |
| Connection times out | DNS not pointing at the Ingress IP |
| Certificate warnings | TLS secret missing, wrong namespace, or wrong host |
| Works internally, not externally | Firewall or security group blocking traffic |

> Step 3 catches the most common failure: Ingress and Service both look
> perfect, but `kubectl get endpoints` is empty because the Service selector
> matches no Pod labels. Always check endpoints before suspecting the Ingress.

---

# Part 2 — Gateway API

Gateway API is the successor to Ingress, built to fix two structural problems.

**Problem 1: annotations.** Anything beyond host/path rules — timeouts,
rewrites, header matching, traffic splitting — has to be expressed as
controller-specific annotations. They are untyped, unvalidated, and not
portable between controllers.

**Problem 2: scope.** An Ingress is namespace-scoped, but ingress
infrastructure is usually shared. Multiple teams end up editing one object.

Gateway API splits the single overloaded object into **role-oriented
resources**:

| Resource | Owned by | Responsibility |
|---|---|---|
| `GatewayClass` | Infrastructure provider | What kind of gateway exists |
| `Gateway` | Cluster operator | Listeners, ports, TLS |
| `HTTPRoute` / `TCPRoute` / `GRPCRoute` | Application developer | Routing rules |

That separation is the point. A platform team owns the `Gateway`; application
teams attach routes **from their own namespaces** without touching shared
configuration.

```
Client → External Load Balancer
       → Gateway (GatewayClass: Istio / NGINX / Contour)
       → Routes (HTTPRoute, TCPRoute, GRPCRoute)
       → Services → Pods        [namespaces: team-a, team-b, team-c]
```

It is also typed: traffic splitting, header matching, and gRPC routing are
first-class fields rather than annotation strings.

---

# Part 3 — API Gateway

A different category — a product at the edge, not a Kubernetes object. It owns
cross-cutting concerns that neither Ingress nor Gateway API addresses:

- Authentication and authorization
- Rate limiting and quotas
- Caching
- WAF
- Analytics
- Request/response transformation
- API versioning

It can route to multiple clusters *and* to things that are not clusters at all.

```
Client → Load Balancer or CDN
       → API Gateway (Kong, Apigee, AWS API Gateway, Traefik Hub)
       → Routes / APIs (versioning, transforms, policies)
       → Backends: multiple clusters, microservices, legacy systems,
                   serverless functions, third-party APIs
```

---

## Choosing between them

| Situation | Use |
|---|---|
| Single cluster, one team, simple host/path rules | **Ingress** |
| Multiple teams or namespaces sharing ingress infrastructure | **Gateway API** |
| Traffic splitting, header matching, gRPC routing | **Gateway API** |
| Auth, rate limiting, quotas, API versioning | **API Gateway** |
| Backends beyond Kubernetes | **API Gateway** |

---

## Quick answers

**What is Ingress?**
A Kubernetes object that routes external HTTP/HTTPS traffic to Services using
host and path rules, giving many applications one entry point instead of one
load balancer each.

**Does Ingress replace a Service?**
No. Ingress routes external traffic to Services; Services route to Pods.

**What are Ingress's limitations?**
It is namespace-scoped and overloads annotations for anything beyond host/path
rules, which makes configuration controller-specific and unportable. Gateway
API replaces it with typed, role-separated resources so platform and
application teams own different objects.

**Does Gateway API replace an API Gateway?**
No. Gateway API is in-cluster traffic routing. An API Gateway is an edge
product handling policy, authentication, and routing across systems.

**My Ingress isn't working — what do you check?**
Outside-in: is the controller running, do the host and path match, does
`kubectl get endpoints` return Pods, is DNS pointing at the Ingress IP, is the
TLS secret present in the right namespace. Empty endpoints is the most common
cause and points at a Service selector mismatch, not the Ingress.


---

## 🗓️ Added 2026-10-16 (auto-generated · 4 new Q&A)

<!-- agent:2026-10-16 18:37 -->

### Q: What is the difference between a Kubernetes Ingress resource and the Gateway API, and when would you choose one over the other?

Ingress is the original Kubernetes HTTP(S) routing abstraction, backed by a controller (e.g., NGINX, Traefik) and a single `Ingress` resource kind. It handles basic host/path-based routing but relies heavily on vendor-specific annotations for advanced features like header manipulation, traffic splitting, or timeouts. The Gateway API is a newer, standardized set of CRDs (`GatewayClass`, `Gateway`, `HTTPRoute`, `TCPRoute`, etc.) designed with role separation, extensibility, and richer semantics built in. Choose Ingress for simple, stable workloads where the team is already familiar with it and advanced routing is not needed. Choose Gateway API when you need multi-tenancy (infrastructure vs. application team role split), protocol diversity (TCP, gRPC, TLS passthrough), or portable advanced traffic management without annotation lock-in.

---

### Q: Explain the role-oriented model of the Gateway API and how it improves multi-team operations.

The Gateway API defines three distinct personas: **infrastructure provider** (manages `GatewayClass`), **cluster operator** (manages `Gateway`), and **application developer** (manages `HTTPRoute`/`GRPCRoute`). This separation means a platform team can provision and own the load-balancer lifecycle while application teams attach routes to a shared Gateway without touching its configuration, enforced through Kubernetes RBAC. `ReferenceGrant` further controls cross-namespace route-to-backend references, preventing unauthorized traffic targeting. In contrast, Ingress conflates all concerns into one resource, making least-privilege delegation difficult. This model scales well in large organizations where security boundaries between infra and dev teams are mandatory.

---

### Q: A production Ingress is returning 502 errors intermittently for one service but not others. Walk me through your troubleshooting process.

**Start at the data plane:**
1. Check Ingress controller pod logs (`kubectl logs`) for upstream connect errors or timeout messages to isolate whether the controller can reach the backend.
2. Verify the `Service` selector matches running pod labels and that `Endpoints` (or `EndpointSlices`) are populated (`kubectl get endpoints <svc>`).
3. Confirm backend pods are healthy — check readiness probes, pod events, and recent restarts.

**Check configuration:**
4. Inspect the Ingress resource for correct `serviceName`/`servicePort` and any annotation overrides (e.g., custom timeouts, proxy buffer sizes).
5. Review whether the controller's generated upstream config (e.g., NGINX `nginx.conf` via `kubectl exec`) actually reflects the current state.

**Network layer:**
6. Test direct connectivity from the controller pod to the service ClusterIP and to a pod IP to rule out CNI or NetworkPolicy issues.
7. Look at HPA or pod disruption — if the target pods are being replaced rapidly, short endpoint propagation delays can cause transient 502s; consider tuning `minReadySeconds` or `preStop` lifecycle hooks.

---

### Q: How does TLS termination work with Kubernetes Ingress, and what are the security considerations you must address?

TLS termination at the Ingress controller means the controller decrypts HTTPS traffic and forwards plain HTTP (or re-encrypted HTTPS) to backend pods. You reference a Kubernetes `Secret` of type `kubernetes.io/tls` in the Ingress `tls` block; the controller mounts the cert/key and presents it to clients. **Security considerations:**
- **Secret access control:** The controller's service account must read `Secret` resources; scope this with RBAC to specific namespaces to limit blast radius.
- **Certificate rotation:** Use cert-manager with an `Issuer`/`ClusterIssuer` to automate renewal and trigger controller reloads without downtime.
- **Re-encryption vs. passthrough:** For compliance workloads (PCI, HIPAA), plain-text backend traffic may be unacceptable; use TLS passthrough (via SNI) or re-encrypt to the pod and validate backend certificates.
- **Cipher suites & TLS version:** Enforce TLS 1.2+ and strong cipher suites via controller-specific annotations or a global ConfigMap; avoid defaults that may still allow weak ciphers.
- **Secret sprawl:** Avoid storing wildcard certs in multiple namespaces; use a single source of truth and sync with tools like External Secrets Operator.


---

## 🗓️ Added 2026-10-17 (auto-generated · 4 new Q&A)

<!-- agent:2026-10-17 17:45 -->

### Q: How does the Gateway API's role-oriented model (GatewayClass, Gateway, HTTPRoute) improve multi-tenant cluster management compared to the flat Ingress model?

The Gateway API separates concerns across three distinct personas: infrastructure providers manage **GatewayClass**, cluster operators manage **Gateway**, and application developers manage **HTTPRoute** (or other route types). This role separation means namespace-scoped teams can own their routing rules without requiring cluster-admin privileges, which is impossible with Ingress where a single resource conflates infrastructure and application concerns. Cross-namespace route attachment, controlled via `allowedRoutes` and `ReferenceGrant`, gives operators fine-grained control over which namespaces can bind to a shared Gateway. In practice this eliminates the dangerous anti-pattern of granting developers broad RBAC on Ingress resources just so they can manage their own paths.

---

### Q: Describe a production incident where Ingress annotations diverged between two controllers (e.g., nginx and Traefik) running in the same cluster. How would you prevent and detect this?

Annotation-based configuration is controller-specific and silently ignored by any controller that doesn't recognise it, so running two controllers means a single Ingress object may be interpreted differently or partially, leading to split-brain routing. Prevention starts with enforcing `ingressClassName` on every resource and using admission webhooks or OPA/Kyverno policies that reject Ingress objects lacking it or using unknown classes. Detection relies on controller-emitted events and status sub-resources — scrape `kubectl get ingress -o jsonpath='{.status}'` in CI or alert on Ingress objects whose `loadBalancer.ingress` field is empty for more than N minutes. The long-term fix is migrating to Gateway API, where the typed spec (not free-form annotations) is validated by the API server itself.

---

### Q: What strategies would you use to achieve canary or traffic-weighted routing with Kubernetes Ingress, and what are the limitations of each approach?

Most nginx-based Ingress controllers support canary via annotations (`nginx.ingress.kubernetes.io/canary-weight`), but this is controller-specific, not portable, and limited to simple percentage splits without header/cookie matching in some versions. Service Mesh integration (Istio `VirtualService`) overlaid on top of Ingress gives richer traffic shaping but adds operational complexity and a second control plane. The Gateway API's **HTTPRoute** `backendRefs` with `weight` fields provides a portable, spec-level canary primitive that works across conformant implementations without annotations. The key limitation of weight-based approaches is that weights apply at the request level, not session level, so sticky sessions require additional affinity configuration to avoid users bouncing between versions mid-session.

---

### Q: A team reports intermittent 502 errors during rolling deployments behind an Ingress. Walk through your systematic diagnosis and the architectural changes that would prevent it.

502s during rollouts typically indicate the Ingress controller is forwarding traffic to pods that have already received `SIGTERM` but whose endpoints haven't been pruned from `kube-proxy`/iptables yet — a race between the endpoint reconciliation loop and pod shutdown. Diagnosis steps: correlate 502 timestamps with deployment events (`kubectl rollout history`), inspect controller access logs for upstream connection errors, and check endpoint churn with `kubectl get endpoints -w`. The fix involves two coordinated changes: add a `preStop` lifecycle hook with a short sleep (e.g., 5s) so the pod stays routable until endpoint removal propagates, and configure `minReadySeconds` plus a `readinessProbe` to ensure new pods are serving before old ones are terminated. At the controller level, enabling `keepalive` upstream connections and setting `proxy_next_upstream` correctly prevents a single failed upstream from surfacing as a user-visible 502.


---

## 🗓️ Added 2026-10-18 (auto-generated · 4 new Q&A)

<!-- agent:2026-10-18 17:48 -->

### Q: How would you implement cross-namespace routing with the Gateway API, and what security controls prevent abuse?

The Gateway API introduces **ReferenceGrant** as the explicit mechanism allowing a resource in one namespace to reference a resource in another. Without a ReferenceGrant in the target namespace, cross-namespace references are silently rejected, making isolation the secure default. In practice, a platform team owns the Gateway in an `infra` namespace, and application teams create HTTPRoutes in their own namespaces that attach to it via `parentRefs`; the platform team grants attachment only to approved namespaces via ReferenceGrant. This contrasts sharply with Ingress, where cross-namespace backend references were either unsupported or controlled only by ad-hoc annotations. Key security controls to highlight:
- **ReferenceGrant** scoping: grants are namespace-scoped and can be limited to specific resource kinds and names.
- **Gateway `allowedRoutes`** field restricts which namespaces/labels can attach routes, giving a second layer of defense.
- RBAC still applies independently; a team can't create a ReferenceGrant they don't have write access to.
- Auditing ReferenceGrants and Gateway `allowedRoutes` policies should be part of your compliance runbook.

---

### Q: Walk me through how you would debug a situation where an HTTPRoute is accepted by the controller but traffic is still returning 404.

The Gateway API surfaces condition types on the route's `status` field—start with `kubectl get httproute <name> -o yaml` and inspect `.status.parents[].conditions`. A route can be `Accepted: True` (the controller parsed it) yet `ResolvedRefs: False` (a backend Service or port doesn't exist), which produces 404s. Common root causes include:
- **Service name or port mismatch** – the HTTPRoute references a port number that differs from what the Service exposes.
- **Missing ReferenceGrant** – backend is in another namespace and the grant was not created.
- **Hostname mismatch** – the Gateway listener's `hostname` glob doesn't cover the HTTPRoute's declared hostname.
- **Weight summing to zero** – a misconfigured traffic split where all backends have weight 0.
After fixing references, confirm the controller has re-reconciled by checking the condition's `observedGeneration` matches the route's `generation`. Correlate with controller logs and, if using a mesh integration, with sidecar proxy config dumps (e.g., `istioctl proxy-config routes`).

---

### Q: What are the trade-offs between handling SSL passthrough at the Ingress/Gateway layer versus terminating TLS inside the application pod?

**SSL passthrough** forwards encrypted traffic directly to the pod; the Ingress/Gateway operates at L4 and cannot inspect HTTP headers, apply routing rules based on paths, or reuse certificates centrally. It is appropriate when the application requires mutual TLS end-to-end (e.g., database clients that validate server identity) or when regulatory requirements prohibit decryption at the edge. **TLS termination at the gateway** enables L7 features—path-based routing, header manipulation, rate limiting, WAF integration—and centralizes certificate lifecycle management (e.g., cert-manager issuing Let's Encrypt certs). The trade-offs:
- Passthrough loses observability; you can't log HTTP request details at the proxy layer.
- Gateway termination introduces a trust boundary: traffic inside the cluster is plaintext unless you add a service mesh for mTLS.
- Certificate rotation is simpler at the gateway; per-pod termination requires distributing and rotating secrets to every workload.
- Performance: termination at the gateway offloads crypto from application CPUs but concentrates load on the proxy fleet.
In most multi-tenant SaaS platforms, gateway termination plus in-cluster mTLS via a service mesh is the preferred balance.

---

### Q: How do you approach rate limiting and request authentication at the Ingress/Gateway layer, and what changes when you move from Ingress annotations to the Gateway API's extensibility model?

With NGINX Ingress, rate limiting is implemented via controller-specific annotations (`nginx.ingress.kubernetes.io/limit-rps`), which are opaque strings with no schema validation and vary across controller versions. Authentication (JWT, OAuth2) similarly relies on annotations or auxiliary sidecar patterns. The Gateway API addresses this through **policy attachment** using vendor extension resources such as `RateLimitPolicy` or `AuthPolicy` CRDs that attach to a Gateway or HTTPRoute via `targetRef`. Key improvements:
- **Portability boundary is explicit**: core Gateway API spec is portable; policies are implementation-specific but follow a common attachment pattern documented in GEP-713.
- **Hierarchical precedence**: a Gateway-level policy sets defaults/overrides; an HTTPRoute-level policy can narrow but not exceed Gateway limits, enforcing tenant guardrails.
- **Status feedback**: policy resources surface their own conditions, so you can tell whether a policy was accepted, conflicted, or overridden.
- **Validation**: because policies are typed CRDs, schema validation happens at admission time rather than at runtime annotation parsing.
Operationally, migration means replacing annotation-based configs with new CRD manifests and updating CI validation pipelines to lint against the new schemas—plan for parallel environments during the cutover.


---

## 🗓️ Added 2026-10-19 (auto-generated · 4 new Q&A)

<!-- agent:2026-10-19 20:21 -->

### Q: How would you debug a situation where an HTTPRoute is correctly configured but traffic is not reaching the backend pods?

**Model Answer:**
Start by verifying the full resource chain: confirm the GatewayClass is accepted by the controller, the Gateway has a `Ready` condition, and the HTTPRoute's `parentRef` matches the correct Gateway name and namespace. Check HTTPRoute status conditions—controllers surface `ResolvedRefs` and `Accepted` conditions that indicate misconfigured backend references or namespace permission issues. Validate that a ReferenceGrant exists if the HTTPRoute and Service are in different namespaces, as missing grants silently block traffic. Inspect the data-plane proxy logs (e.g., Envoy access logs in Istio or Contour) to see whether requests arrive at the proxy but fail upstream, pointing to a pod-readiness or port mismatch. Use `kubectl port-forward` directly to the backend Service and pods to isolate whether the issue is in the gateway layer or the application itself. Finally, verify NetworkPolicies are not blocking traffic from the gateway's pod CIDR to the backend pods, a frequently overlooked cause.

---

### Q: What are the performance and operational trade-offs of running a single shared Ingress controller versus one controller per namespace or team?

**Model Answer:**
A single shared controller minimizes resource overhead and simplifies certificate management and observability, but creates a "noisy neighbor" problem—one team's heavy traffic or misconfigured annotation can degrade routing for all. It also concentrates blast radius: a controller crash or bad config reload affects the entire cluster. Per-team controllers (using `IngressClass` or separate GatewayClasses) provide fault isolation, independent upgrade cadences, and cleaner RBAC boundaries, at the cost of multiplied resource consumption and more complex certificate/DNS management. The Gateway API's role model is specifically designed to ease this trade-off: platform teams own GatewayClass and Gateway objects, while application teams manage their own HTTPRoutes without needing cluster-wide privileges. In practice, a middle ground—one controller per environment tier (e.g., public-internet vs. internal)—often balances isolation with operational simplicity. Capacity planning must account for connection table size and TLS handshake overhead when consolidating many domains onto one controller.

---

### Q: How do you handle certificate lifecycle management for Ingress or Gateway resources at scale, and what can go wrong?

**Model Answer:**
cert-manager is the de-facto standard: it watches Ingress `tls` blocks or `Certificate` CRDs and automates ACME (Let's Encrypt) or internal CA issuance and renewal. For Gateway API, cert-manager's `Gateway` support allows attaching certificates directly to `Gateway` listeners via `certificateRefs`, decoupling cert provisioning from HTTPRoute authors. Common failure modes include: ACME HTTP-01 challenge failures when the Ingress controller rewrites paths before the solver pod can respond; rate-limit exhaustion on Let's Encrypt's 50-certs-per-domain-per-week limit during mass rollouts; and certificate Secret propagation lag causing brief TLS errors after renewal. At scale, wildcard certificates with DNS-01 challenges reduce the number of certificates needed but require DNS provider credentials with broad write access, a security concern that should be scoped tightly via IAM. Monitoring certificate expiry with Prometheus metrics from cert-manager and alerting at 30 and 7 days before expiry is essential. Store Secrets in an external vault (e.g., HashiCorp Vault, AWS Secrets Manager) and sync with the External Secrets Operator to avoid storing sensitive key material solely in etcd.

---

### Q: Walk me through how you would migrate a production workload from Ingress resources to the Gateway API with zero downtime.

**Model Answer:**
Begin with an inventory of all Ingress objects, their annotations, and controller-specific behavior—many annotations have no direct Gateway API equivalent and require translation to policy attachments or vendor CRDs. Run the Gateway API controller in parallel alongside the existing Ingress controller; both can coexist because they watch different resource kinds. Create equivalent GatewayClass, Gateway, and HTTPRoute resources in a staging environment and validate functional parity, paying special attention to rewrite rules, header manipulation, and auth integrations. For cutover, use weighted DNS or an upstream load balancer to shift a small percentage of traffic (e.g., 5%) to the new Gateway endpoint, monitor error rates and latency, then gradually increase. Keep the old Ingress resources live until the new path is fully validated—do not delete them prematurely. Implement automated rollback by scripting DNS weight reversion if error-rate thresholds are breached. Document annotation-to-policy mapping for your team because institutional knowledge of Ingress annotations is often undocumented and critical for post-migration support.


---

## 🗓️ Added 2026-10-20 (auto-generated · 4 new Q&A)

<!-- agent:2026-10-20 18:54 -->

### Q: How would you design a blue/green deployment strategy using Gateway API HTTPRoute traffic splitting, and what rollback mechanism would you implement?

Blue/green with Gateway API uses `HTTPRoute` `backendRefs` weights—initially 100% to the blue `Service`, then shifting weight to green incrementally or atomically. Unlike canary, blue/green typically cuts over fully at once, so you'd set green's weight to 100 and blue's to 0 in a single `kubectl apply`, which is atomic from the API server's perspective. Rollback is equally fast: revert the weight fields or apply the previous `HTTPRoute` manifest from version control. Key considerations:

- **Readiness gates**: Ensure green pods pass readiness probes before shifting weight; combine with a pre-flight smoke test against a header-matched shadow route.
- **Session affinity**: Stateful sessions mid-flight may break on cutover; use cookie-based affinity or drain blue gracefully with a 0-weight (not deletion) so existing connections complete.
- **GitOps integration**: Store `HTTPRoute` manifests in Git; a failed deployment triggers a PR revert or ArgoCD sync to the last known-good revision.
- **Observability gate**: Wire a Prometheus/Datadog query into your CD pipeline—if error rate on green exceeds threshold within N minutes, the pipeline auto-reverts the weight, keeping MTTR low.

---

### Q: Explain how GatewayClass infrastructure parameters work, and how you would use them to enforce organizational standards across multiple Gateway instances.

`GatewayClass` accepts a `parametersRef` field pointing to a provider-specific custom resource (e.g., `GatewayClassConfig` for Envoy Gateway or `AWSGatewayClassConfig` for ACK). This lets platform teams encode defaults—load balancer tier, logging level, connection limits, or VPC/subnet placement—in a single object that every `Gateway` referencing that class inherits. To enforce organizational standards:

- Define separate `GatewayClasses` per tier (e.g., `internal`, `external-public`, `partner-dmz`), each pointing to a parameters object with pre-approved settings.
- Use RBAC to restrict who can create or modify `GatewayClass` resources to the platform team; application teams only select the appropriate class name.
- Validate compliance with an OPA/Gatekeeper or Kyverno policy that rejects `Gateway` resources referencing unapproved class names or attempting to override restricted fields.
- Apply mutating webhooks to stamp organizational labels and ownership annotations onto every `Gateway` at admission time, enabling cost attribution and audit.
- Periodically reconcile parameters objects through GitOps; drift triggers alerts rather than silent overrides.

---

### Q: What happens to in-flight requests during an Ingress controller rolling update, and how do you minimize request loss?

During a rolling update the old controller pod begins terminating while the new one starts. The gap creates two risk windows: (1) the terminating pod stops accepting new connections before draining existing ones, and (2) `kube-proxy`/iptables rules may still route traffic to a terminating pod. Mitigation strategies:

- **`preStop` hook + sleep**: Add a `preStop` hook that sleeps 5–15 s before the process begins its shutdown sequence, giving `kube-proxy` time to remove the endpoint from the service.
- **`terminationGracePeriodSeconds`**: Set this high enough to outlast the longest expected request (e.g., long-poll or file upload); the controller's own drain timeout should be slightly shorter.
- **PodDisruptionBudget**: Set `minAvailable` to at least 1 so the rollout never takes all replicas down simultaneously.
- **`maxUnavailable: 0`** in the Deployment ensures a new pod is healthy before an old one is terminated, keeping capacity constant.
- **Connection draining at the LB layer**: Cloud load balancers (AWS NLB/ALB, GCP LB) support connection draining; configure deregistration delay to overlap with the `preStop` sleep.
- After the rollout, validate with metrics: watch for 502/504 spikes and `upstream_response_time` anomalies in the controller's access logs.

---

### Q: How would you implement and test a WAF policy at the Gateway layer, and what are the operational pitfalls of doing so?

A WAF at the Gateway layer is typically implemented via an extension point: an `ExtensionRef` in an `HTTPRoute` filter (Gateway API) or a custom annotation/sidecar (Ingress). Providers like Envoy Gateway support `SecurityPolicy` CRDs that attach OWASP Core Rule Set (CRS) logic; others delegate to an external WAF (AWS WAF, Cloudflare, ModSecurity sidecar).

**Implementation steps:**
1. Deploy the WAF as a `SecurityPolicy` (or equivalent) referencing the `Gateway` or specific `HTTPRoute`.
2. Start in **detection mode**: log rule matches without blocking, then analyze false-positive rate against real traffic for at least one traffic cycle.
3. Promote to **prevention mode** rule-by-rule, not wholesale, to limit blast radius.
4. Write integration tests (OWASP ZAP, Nikto, or custom scripts) in your CI pipeline that assert known attack payloads (SQLi, XSS, path traversal) are blocked and return 403.

**Operational pitfalls:**
- **False positives on legitimate traffic** (e.g., JSON bodies triggering SQL injection rules); require a tuning process and a rule-exclusion workflow.
- **Latency overhead**: Regex-heavy rule evaluation adds CPU and latency; benchmark at production request rates before enabling.
- **Rule-set drift**: CRS updates can introduce new false positives; treat CRS version bumps as deployable changes with a validation gate.
- **Bypass via chunked encoding or HTTP/2 normalization quirks**: Verify the WAF engine normalizes requests before inspection.


---

## 🗓️ Added 2026-10-21 (auto-generated · 4 new Q&A)

<!-- agent:2026-10-21 19:07 -->

### Q: How would you configure and operationalize header-based routing with Gateway API HTTPRoute, and what pitfalls should you watch for in production?

Header-based routing is expressed in HTTPRoute via `matches[].headers` fields, supporting exact, prefix, and regex match types. A common pattern is routing canary traffic by injecting an `X-Canary: true` header at the client or via a middleware, then matching that header to a separate backend. **Key pitfalls:**

- **Regex support is controller-dependent** — the Gateway API spec marks regex as an optional feature (`RegularExpression` conformance level), so verify your implementation actually supports it before relying on it.
- **Header order and case sensitivity** — HTTP/2 lowercases headers, but HTTP/1.1 does not; ensure your match values are lowercase and that the upstream service doesn't strip or rename headers.
- **Security exposure** — if external clients can spoof the routing header, they can target internal or canary backends directly; always strip untrusted header values at the Gateway before re-evaluating them, or use signed tokens instead.
- **Observability gap** — header matches are invisible in standard access logs; instrument your controller's metrics or add a response header echoing the matched route for traceability.
- Test routing logic with synthetic traffic using tools like `curl -H` in staging, and use `httproute` status conditions (`ResolvedRefs`, `Accepted`) to confirm the controller has reconciled the intended configuration.

---

### Q: What is GatewayClass and how does its lifecycle affect cluster-wide routing availability?

`GatewayClass` is a cluster-scoped resource that names and configures an Ingress/Gateway controller implementation, analogous to `StorageClass` for volumes. Each `Gateway` references exactly one `GatewayClass`; if the class is deleted or its controller is uninstalled, all `Gateway` objects referencing it will lose reconciliation and existing data-plane configuration may become stale or entirely removed, depending on the implementation. **Operational implications:**

- **Controller uninstall order matters** — always drain and migrate `Gateway`/`HTTPRoute` resources before removing a `GatewayClass` to avoid traffic blackholes.
- **`controllerName` field is immutable** — changing the backing controller requires creating a new `GatewayClass` and migrating resources, not editing the existing one.
- **Status propagation** — the `Accepted` condition on `GatewayClass` tells you whether the responsible controller is running; use this in readiness checks and alerting.
- **Multi-implementation clusters** — you can run multiple `GatewayClass` objects side-by-side (e.g., internal Envoy Gateway and external NGINX), but teams must coordinate naming conventions to prevent accidental cross-attachment.

Always treat `GatewayClass` as an infrastructure-level resource managed by platform engineers, with RBAC restricting who can create or modify it.

---

### Q: How would you handle a scenario where Ingress or HTTPRoute changes are deployed continuously by CI/CD and cause transient 502 errors in production?

Transient 502s during rapid route updates typically stem from the controller's reconciliation loop applying partial state — e.g., updating the upstream list before the route rule is consistent — or from backend pods not yet being ready when the route is activated. **Mitigation strategy:**

- **Synchronize route rollout with deployment readiness** — use `kubectl rollout status` or wait on `Deployment` readiness gates before applying new `HTTPRoute` manifests in the pipeline.
- **Use `ReferenceGrant` and service pre-creation** — ensure the target `Service` and its `Endpoints` exist and are healthy before the route references them; an HTTPRoute pointing at a service with zero ready endpoints will 502 immediately.
- **Progressive apply with health checks** — apply route changes in stages (e.g., shift 10% weight first, validate error rate, then shift 100%) rather than atomic cutover.
- **Controller reconciliation batching** — some controllers (e.g., Envoy-based) batch xDS updates; understand your controller's push interval and tune it to reduce partial-state windows.
- **Canary the route change itself** — treat the `HTTPRoute` manifest as an artifact with a version, deploy a shadow copy alongside the existing one, and use weight-based splitting to validate before full promotion.

Instrument your CI/CD pipeline with a post-deploy smoke test that asserts HTTP 200 on critical paths within a configurable timeout before marking a deployment successful.

---

### Q: A team reports that their Ingress resource works correctly in one namespace but identical configuration fails silently in another. Walk me through your diagnostic approach.

"Silent failure" in a second namespace usually means the Ingress is accepted by the API server but ignored or misconfigured at the controller level. **Diagnostic steps:**

1. **Check Ingress status** — `kubectl get ingress -n <ns> -o yaml`; a missing or empty `status.loadBalancer.ingress` field indicates the controller has not reconciled the resource, often due to a missing or mismatched `ingressClassName`.
2. **Verify IngressClass and controller scope** — confirm the `IngressClass` referenced exists cluster-wide, and check whether the controller is configured with `--watch-namespace` or `--ingress-class` flags that exclude the failing namespace.
3. **Inspect controller logs** — filter for the failing namespace and Ingress name; common messages include "ignoring ingress without class annotation," namespace access errors, or RBAC denial.
4. **RBAC audit** — the controller's `ServiceAccount` must have `get/list/watch` on `Ingress` and `Secret` resources in every namespace it serves; a missing `RoleBinding` in the new namespace silently blocks reconciliation.
5. **Secret and TLS availability** — if TLS is configured, confirm the referenced `Secret` exists in the same namespace as the Ingress; controllers do not cross namespaces for secrets unless explicitly allowed.
6. **Annotation parity** — diff annotations between working and failing namespaces; some controllers require namespace-level annotations or `ConfigMap` entries to enable features like auth or rewrites.
7. **NetworkPolicy** — confirm no `NetworkPolicy` in the new namespace blocks traffic from the Ingress controller's pod namespace to the backend pods.

Resolve by correcting the `ingressClassName`, adding required RBAC, and ensuring all referenced secrets are present, then verify with an end-to-end `curl` through the Ingress hostname.


---

## 🗓️ Added 2026-10-22 (auto-generated · 4 new Q&A)

<!-- agent:2026-10-22 19:03 -->

### Q: How would you design an observability stack specifically for Ingress/Gateway-layer traffic, and what signals matter most?

**Answer:**
- **Golden signals to capture at the gateway**: request rate, error rate (4xx vs 5xx split), latency percentiles (p50/p95/p99), and active connection count. Distinguish upstream errors (backend) from gateway errors (routing, TLS, auth).
- **Access logs**: emit structured JSON logs with fields like `route`, `backend`, `status`, `latency_ms`, `upstream_pod`, and `tls_version` so logs are queryable and correlatable with traces.
- **Metrics**: most controllers expose Prometheus metrics natively (e.g., `nginx_ingress_controller_requests_total`, Envoy's `cluster.upstream_rq_*`). Create per-route/per-backend dashboards so you can isolate which HTTPRoute or Ingress rule is degraded.
- **Distributed tracing**: propagate `traceparent`/`x-request-id` headers at the gateway layer and sample traces into a backend (Jaeger, Tempo). This links a gateway 502 to a specific backend span.
- **Alerting thresholds**: alert on error-rate spikes above baseline *per route*, not only globally—a noisy tenant must not hide a critical service degrading.
- **Pitfall**: many teams only monitor the controller pod's health, missing per-upstream latency degradation that only appears in backend-level metrics.

---

### Q: How do you manage conflicting Ingress or HTTPRoute rules when multiple teams deploy resources targeting the same hostname or path, and how does the Gateway API handle conflict resolution?

**Answer:**
The Gateway API defines a deterministic **conflict resolution** model: if two HTTPRoutes match the same hostname and path with equal specificity, the older resource wins (by `creationTimestamp`); ties are broken lexicographically by namespace/name. Nginx Ingress and similar controllers have historically merged rules silently or applied last-write-wins, which is unpredictable at scale.

Key practices:
- **Use ReferenceGrants and namespace isolation** so routes from different teams attach only to Gateways they are permitted to use, reducing the blast radius of conflicts.
- **Specificity rules**: more specific path matches (`/api/v2/orders` beats `/api`) and more specific header matches take precedence; understanding this prevents unexpected routing.
- **Admission webhooks / policy controllers** (e.g., OPA Gatekeeper) can enforce hostname uniqueness at admission time rather than discovering conflicts at runtime.
- **Status conditions** on HTTPRoute (`ResolvedRefs`, `Accepted`) will reflect conflict or rejection—monitoring these conditions via alerts or a controller-runtime reconciler is essential for fast detection.
- **Behavioral pitfall**: a conflicting Ingress rule being silently dropped means traffic silently 404s; teams rarely check controller logs for "skipped" annotations.

---

### Q: What are the architectural implications of using an external load balancer (e.g., AWS NLB/ALB) in front of an in-cluster Ingress controller versus relying solely on the cloud provider's Ingress controller (e.g., AWS Load Balancer Controller)?

**Answer:**
**In-cluster controller behind a cloud LB (NLB → nginx/Envoy):**
- Full control over routing logic, middleware (auth, rate-limiting, header manipulation), and upgrade cadence.
- NLB operates at L4, so TLS termination and HTTP routing happen inside the cluster—giving you richer, controller-native features.
- Additional network hop increases latency slightly; the in-cluster controller becomes a potential bottleneck and must be scaled horizontally.
- Easier portability—the same controller config works on any cloud or on-prem.

**Cloud-native controller (ALB Ingress / AWS LBC):**
- TLS termination and routing offloaded to a managed service—reduces operational burden and leverages AWS WAF, ACM, and Shield natively.
- ALB is provisioned *per Ingress* by default, which causes cost explosion and IP exhaustion in multi-service clusters without IngressGroup annotations to merge rules.
- Feature set is gated by what AWS exposes via annotations; advanced routing (e.g., gRPC, traffic mirroring) may be unavailable or require workarounds.
- Tighter AWS lock-in; migrating to another cloud or on-prem requires rewriting Ingress annotations entirely.

**Decision criteria**: choose cloud-native when managed TLS, WAF integration, and reduced ops overhead outweigh portability and advanced feature needs; choose in-cluster when you need fine-grained control, multi-cloud portability, or features the cloud LB doesn't support.

---

### Q: Walk me through how you would safely migrate a production workload from Kubernetes Ingress to Gateway API HTTPRoute with zero downtime.

**Answer:**
1. **Audit existing Ingress**: export all rules, annotations, and TLS secrets; map each annotation to its Gateway API equivalent (e.g., `nginx.ingress.kubernetes.io/rewrite-target` → HTTPRoute `URLRewrite` filter). Identify any annotations with no direct equivalent—these need custom policies or `ExtensionRef`.
2. **Deploy a parallel Gateway**: install the Gateway API CRDs and configure a new `Gateway` resource (potentially using the same controller if it supports both APIs, e.g., ingress-nginx ≥ 1.9 or Cilium). Point it to a *separate* cloud LB or a second listener so it handles no live traffic yet.
3. **Create HTTPRoutes mirroring Ingress rules**: configure identical hostnames and paths on the new HTTPRoutes. Use traffic mirroring (`RequestMirror` filter) from the old Ingress to shadow-copy requests to the new backend—validate behavior without affecting production responses.
4. **Shift traffic incrementally**: update DNS (weighted routing, or TTL-lowered A records) to send a small percentage of traffic to the new Gateway LB. Monitor error rate, latency, and backend logs in parallel.
5. **Validate and cut over**: once metrics match, shift 100% of DNS traffic to the new Gateway. Keep the old Ingress resource live (but receiving no traffic) for a rollback window—revert DNS if issues arise within the rollback period.
6. **Cleanup**: delete old Ingress resources and decommission the old controller or listener. Remove deprecated annotation-based logic and document the new HTTPRoute-based configuration in your GitOps repo.
7. **Pitfalls**: session-affinity annotations, custom error pages, and CORS headers are common gaps; test these explicitly during the shadow phase.


---

## 🗓️ Added 2026-10-23 (auto-generated · 4 new Q&A)

<!-- agent:2026-10-23 18:53 -->

### Q: How do you configure and enforce HTTPS redirection and HSTS at the Ingress/Gateway layer, and what subtle failure modes exist?

**Model Answer:**

For Ingress, HTTPS redirection is typically handled via controller-specific annotations (e.g., `nginx.ingress.kubernetes.io/ssl-redirect: "true"`), while HSTS is set through the `nginx.ingress.kubernetes.io/configuration-snippet` or global ConfigMap values. With Gateway API, you model this explicitly: a `Gateway` listener on port 80 uses an `HTTPRoute` with a `RequestRedirect` filter (scheme: https, statusCode: 301), and the HSTS response header is injected via a `ResponseHeaderModifier` filter on the HTTPS `HTTPRoute`.

**Key failure modes to call out:**
- **Redirect loops** when the backend itself also redirects to HTTPS and the controller doesn't strip the `X-Forwarded-Proto` header correctly.
- **HSTS lock-in** — setting `includeSubDomains` or `preload` incorrectly can make an entire domain inaccessible if the certificate lapses; never set preload without full domain readiness.
- **Mixed-content** issues when internal services are referenced by HTTP URLs even though the edge is HTTPS.
- **Annotation drift** between environments (staging allows HTTP, production doesn't) causing CI pipelines to pass but production to behave differently.
- With Gateway API, the redirect and the TLS listener must be on separate `Gateway` listeners; a common mistake is attaching the redirect `HTTPRoute` to the HTTPS listener, making it unreachable over HTTP.

HSTS `max-age` should start small (e.g., 300s) in staging and be promoted to 31536000 only after full validation.

---

### Q: How does the Gateway API's `ReferenceGrant` resource work, and what attack surface does it close compared to classic Ingress?

**Model Answer:**

`ReferenceGrant` is a namespace-scoped resource in the target namespace that explicitly permits a resource in another namespace (e.g., an `HTTPRoute` in namespace `team-a`) to reference something it owns (e.g., a `Service` or `Secret` in namespace `platform`). Without a matching `ReferenceGrant`, the controller must reject the cross-namespace reference, treating it as if the target doesn't exist.

**Security improvement over classic Ingress:**
- Classic Ingress has no native cross-namespace reference control; a misconfigured or malicious `Ingress` in one namespace can potentially route to a `Service` in another namespace if the controller doesn't enforce namespace isolation (most don't by default).
- `ReferenceGrant` shifts trust: the *owner* of the target resource explicitly consents to being referenced, following a capability/grant model rather than relying purely on RBAC on the `Ingress` object itself.
- It enables least-privilege: a platform team exposes a shared TLS `Secret` to specific tenant namespaces without mounting it or copying it everywhere.

**Operational considerations:**
- Forgetting to create `ReferenceGrant` is a common cause of `HTTPRoute` showing `ResolvedRefs: False` with a `RefNotPermitted` condition — always check route status conditions first when debugging.
- `ReferenceGrant` itself should be managed by the platform/ops team via GitOps, not by tenants, to preserve its security value.
- Deleting a `ReferenceGrant` is a breaking change; gate it behind a review process.

---

### Q: How would you design a multi-region active-active architecture where Kubernetes Gateway API resources are synchronized across clusters, and what consistency problems arise?

**Model Answer:**

A typical approach layers three concerns: **DNS-level routing** (e.g., latency-based or geolocation routing via Route 53 / Azure Traffic Manager pointing to per-region `Gateway` external IPs), **config synchronization** (GitOps tooling like Flux or Argo CD deploying identical `GatewayClass`, `Gateway`, and `HTTPRoute` manifests to each region), and **data-plane isolation** (each region's controller is independent; there is no shared control plane).

**Consistency problems to address:**
- **Config skew**: If a cluster is temporarily unreachable during a GitOps sync, one region may run a stale `HTTPRoute` version. Solve with health-gating: don't promote DNS weight to a cluster until its route reconciliation is confirmed via status conditions.
- **Secret/certificate sync**: TLS secrets must be replicated across regions (e.g., using External Secrets Operator with a global secrets backend or cert-manager with a shared CA). A certificate expiring in one region but not another causes partial outages that are hard to detect without per-region synthetic monitoring.
- **`ReferenceGrant` and policy objects** must also be synced; it's easy to sync `HTTPRoute` but forget `ReferencePolicy` or `BackendTLSPolicy`, breaking routes silently in one region.
- **Canary/traffic-split state**: If a weighted `HTTPRoute` is mid-rollout in one region and the sync wave hasn't reached another, users get inconsistent behavior depending on which region serves them. Use feature flags or synchronize rollout promotion across regions before updating weights.
- Prefer immutable, version-tagged manifests over mutable `latest`-style references, and always validate `HTTPRoute` status conditions post-sync before shifting DNS weight.

---

### Q: A security audit flags that your Ingress controller pods are running with cluster-admin privileges. How do you remediate this, and what is the minimum permission set the controller actually needs?

**Model Answer:**

This is a real and common finding, particularly with older Helm chart defaults. The remediation involves replacing the `ClusterRoleBinding` to `cluster-admin` with a purpose-built `ClusterRole` granting only what the controller's reconciliation loop actually requires.

**Minimum RBAC surface for a typical Ingress controller (e.g., ingress-nginx):**
- `get/list/watch` on `Ingress`, `IngressClass`, `Services`, `Endpoints`/`EndpointSlices`, `Secrets` (scoped to namespaces it manages), `ConfigMaps` (for leader election).
- `update/patch` on `Ingress` status subresource (to write the assigned IP/hostname back).
- `create/get/update` on `ConfigMaps` and `Leases` in the controller's own namespace (leader election).
- **No** `cluster-admin`, no `pods/exec`, no `secrets` cluster-wide.

**For Gateway API controllers**, additionally: `get/list/watch/patch` on `GatewayClass`, `Gateway`, `HTTPRoute`, `ReferenceGrant`, and their `status` subresources.

**Remediation steps:**
1. Audit current permissions with `kubectl auth can-i --list --as=system:serviceaccount:<ns>:<sa>`.
2. Apply a least-privilege `ClusterRole`; use the upstream chart's dedicated RBAC templates rather than rolling your own.
3. Restrict `Secrets` access to specific namespaces using `Role`/`RoleBinding` instead of cluster-wide, if the controller supports namespace-scoped secret watching.
4. Enable `ValidatingAdmissionWebhook` for the controller so misconfigured resources are rejected before reaching the controller loop, reducing the blast radius if the controller SA is compromised.
5. Run `kube-score` or OPA/Gatekeeper policies to prevent future privilege escalation via chart upgrades reverting to `cluster-admin`.


---

## 🗓️ Added 2026-10-24 (auto-generated · 4 new Q&A)

<!-- agent:2026-10-24 17:50 -->

### Q: How do you implement gRPC routing with the Gateway API, and what makes it different from standard HTTP routing?

The Gateway API introduced a dedicated `GRPCRoute` resource (v1alpha2/v1) that understands gRPC framing natively, whereas classic Ingress had no gRPC concept and required controller-specific annotations plus manual TLS+HTTP/2 configuration. A `GRPCRoute` matches on `service` and `method` fields (the gRPC path components) rather than URL path prefixes, making routing intentions explicit and less error-prone. Key differences to articulate:

- **Protocol**: gRPC runs exclusively over HTTP/2; the Gateway and backend `Service` must both advertise `appProtocol: kubernetes.io/h2c` (cleartext) or use TLS with ALPN `h2`.
- **Matching semantics**: `GRPCRoute` supports `Exact` and `RegularExpression` matches on service/method pairs; a misconfigured `HTTPRoute` targeting a gRPC backend will silently fail because HTTP/1.1 proxying breaks the framing.
- **Timeouts**: gRPC uses long-lived streaming RPCs; set `timeouts.request` high enough (or per-route) to avoid premature connection termination.
- **Health checks**: Backends should expose the gRPC Health Checking Protocol; configure the Gateway's backend health check accordingly, not an HTTP `/healthz` path.

Operationally, validate with `grpcurl` and capture traces that show `content-type: application/grpc` headers propagating end-to-end. If you see `HTTP 426 Upgrade Required`, the proxy is downgrading to HTTP/1.1.

---

### Q: What is the role of `parentReference` in Gateway API resources, and how do you use it to scope an HTTPRoute to a specific listener or port?

Every `HTTPRoute`, `GRPCRoute`, or `TLSRoute` attaches to a `Gateway` via the `spec.parentRefs` field, which replaces the implicit hostname-matching used by classic Ingress. You can target a specific `Gateway` by name/namespace, and further narrow to a single listener by setting `sectionName` (matching the listener's `name` field) and/or `port`. This is critical in multi-listener Gateways—e.g., one listener on 443 for external traffic and one on 8443 for internal—so routes don't accidentally attach to the wrong listener. An interviewer wants to hear:

- Without `sectionName`, the route attaches to **all listeners on that Gateway** that match the hostname, which can expose internal routes externally.
- The Gateway controller reflects attachment status in `route.status.parents[].conditions`; check `Accepted` and `ResolvedRefs` conditions to debug attachment failures.
- `parentRefs` supports cross-namespace attachment *only* when the Gateway's listener carries an `allowedRoutes.namespaces` policy permitting the route's namespace—this is the first line of multi-tenant isolation.
- Combining `sectionName` with `ReferenceGrant` gives fine-grained, auditable control over which teams can attach routes to which listeners.

---

### Q: How do you handle WebSocket or long-lived HTTP connections through a Kubernetes Ingress or Gateway, and what configuration mistakes cause connection drops?

WebSockets and SSE (Server-Sent Events) upgrade a standard HTTP connection to a persistent, bidirectional stream, so several default controller behaviors break them:

- **Proxy read/send timeouts**: Most controllers default to 60 s; long-lived connections will be killed. Set `proxy-read-timeout` / `proxy-send-timeout` (nginx) or equivalent annotations to match your application's heartbeat interval, or use `0` for no timeout paired with application-level keepalives.
- **HTTP/1.1 requirement**: WebSocket upgrades (`Upgrade: websocket`) require HTTP/1.1 between the proxy and backend; if the backend is incorrectly configured for HTTP/2 only, the upgrade handshake fails with a `400`.
- **Load balancer idle timeout**: The AWS NLB/ALB or GCP LB sitting in front has its own idle timeout (default 60 s on ALB). Set it to match or exceed your application timeout, or implement application-level ping frames to keep the connection alive.
- **Gateway API**: Use `HTTPRoute` with `timeouts.backendRequest` set appropriately; some implementations also require `connection: Upgrade` and `upgrade` headers to be forwarded explicitly in `RequestHeaderModifier` filters.
- **Session affinity**: WebSocket state is connection-local; if the proxy load-balances mid-stream (after a pod restart), the client must reconnect. Use `sessionAffinity: ClientIP` on the Service or cookie-based affinity at the Ingress layer.

Test by inspecting `101 Switching Protocols` in traces and monitoring WebSocket frame-level metrics if your controller exposes them.

---

### Q: A new engineering team wants to expose a service through your shared cluster Gateway but their HTTPRoute is stuck in "Not Accepted" status. Walk me through your diagnostic process.

This is a common operational scenario that tests systematic troubleshooting. The diagnostic sequence:

1. **Inspect route status**: `kubectl get httproute <name> -n <ns> -o yaml` → examine `status.parents[].conditions`. The `Accepted` condition reason (e.g., `NoMatchingParent`, `NotAllowedByListeners`, `HostnameConflict`) pinpoints the category of failure.
2. **Check parentRef accuracy**: Verify `parentRefs[].name`, `namespace`, and `sectionName` exactly match the target Gateway's metadata and listener name—typos are common.
3. **Verify allowedRoutes policy**: Inspect the Gateway's listener `allowedRoutes.namespaces`; if set to `Same` or a label selector, the team's namespace must satisfy it. Coordinate with the platform team to add a `ReferenceGrant` or update the selector.
4. **Hostname conflicts**: If another HTTPRoute already claims the same hostname+path with equal or higher specificity, the new route may be rejected. Check `HostnameConflict` or `RouteConflict` reason and resolve by adjusting path specificity.
5. **Backend reference resolution**: Even if the route is accepted, `ResolvedRefs` can be `False` if the backend `Service` doesn't exist, is in a different namespace without a `ReferenceGrant`, or the port name/number doesn't match. Fix the service reference or add the grant.
6. **Controller logs**: Tail the Gateway controller pods (`kubectl logs -n <gateway-ns> <controller-pod>`) for reconciliation errors that don't surface in status fields.
7. **GatewayClass provisioner readiness**: If the `GatewayClass` itself has `Accepted: False`, no routes under it will work—escalate to cluster admins.

Document findings and feed them into runbooks; "Not Accepted" with a clear reason field is one of the Gateway API's biggest UX improvements over opaque Ingress annotation failures.


---

## 🗓️ Added 2026-10-25 (auto-generated · 4 new Q&A)

<!-- agent:2026-10-25 18:06 -->

### Q: How do you implement timeout and retry policies in Gateway API, and what are the risks of misconfiguring them?

**Model Answer:**

Gateway API exposes timeouts natively via the `HTTPRoute` spec (GA in v1.1) through `timeouts.request` and `timeouts.backendRequest` fields, where `backendRequest` applies per-attempt and must be ≤ `request`. Retry policies are implementation-specific today (e.g., via policy attachment CRDs like `BackendLBPolicy` or vendor annotations), though a standardised `RetryFilter` is progressing upstream.

Key risks and considerations:

- **Retry amplification:** Aggressive retry counts without exponential back-off can multiply load on an already-degraded backend by an order of magnitude; always pair retries with jitter and a circuit breaker.
- **Timeout ladder misconfiguration:** If `backendRequest` > `request`, the per-attempt timeout is never the binding constraint, making the field misleading and masking slow backends.
- **Idempotency assumptions:** Retrying `POST` or non-idempotent mutations can cause duplicate side effects; limit automatic retries to `GET`, `HEAD`, or explicitly idempotent operations.
- **Interaction with client-side timeouts:** If the upstream client (browser, mobile SDK) has a shorter timeout than the gateway, the gateway may succeed on retry but the client has already given up—consuming backend resources for no user benefit.
- **Validation gap:** Implementations vary in whether they reject invalid timeout combinations at admission time; add OPA/CEL validation policies to enforce your organisation's safe ranges.

---

### Q: A team reports that large file uploads through your Ingress intermittently fail with 413 or time out mid-stream. How do you systematically diagnose and resolve this?

**Model Answer:**

This is a layered problem touching proxy config, cloud LB limits, and OS socket buffers. Systematic approach:

1. **Confirm the 413 source** — check whether the response comes from the Ingress controller (e.g., nginx's `client_max_body_size` default of 1 MB) or the application itself; the `Server` response header and controller access logs disambiguate.
2. **Ingress controller config** — for nginx-ingress, set the `nginx.ingress.kubernetes.io/proxy-body-size` annotation to the required limit (or `"0"` for unlimited); for Gateway API use an implementation-specific `HTTPRouteFilter` or `PolicyAttachment`.
3. **Cloud LB layer** — ALBs have a fixed 60-second idle timeout; NLBs support up to 350 seconds. Uploads that stall mid-transfer due to client bandwidth will hit this; increase the LB idle timeout and propagate it to the controller's `proxy-read-timeout`.
4. **Proxy buffering** — nginx's `proxy_request_buffering` buffers the entire body before forwarding; disabling it (`proxy-request-buffering: "off"`) allows streaming but means the backend receives the connection immediately, increasing backend concurrency.
5. **Pod resource limits** — ensure controller pods have enough ephemeral storage and memory if buffering is enabled; OOMKills mid-transfer produce the same symptom as timeouts.
6. **End-to-end test** — use `curl --limit-rate` to simulate slow clients and reproduce the timeout, confirming the fix before production rollout.

---

### Q: How do you enforce consistent routing policy across dozens of HTTPRoutes without duplicating configuration in every resource?

**Model Answer:**

Gateway API addresses this through **policy attachment** — specifically the `PolicyAttachment` pattern where implementation-defined CRDs (e.g., `TimeoutPolicy`, `RetryPolicy`, `BackendTLSPolicy`) attach to a target resource and can target a `Gateway`, `HTTPRoute`, or `Service` in a hierarchy.

Key design points:

- **Hierarchical inheritance:** Policies attached to a `Gateway` act as defaults for all child `HTTPRoute`s; more-specific policies attached to the route or backend override them. This lets platform teams set cluster-wide baselines without touching tenant manifests.
- **`BackendTLSPolicy`** is a standard (graduated to GA in v1.3) example: attach once to a `Service` to enforce mTLS from the gateway to the backend, rather than annotating every route.
- **Kustomize / Helm abstractions:** For controllers that don't yet implement policy attachment, use a shared Helm library chart that renders common annotation sets; a mutation webhook can also inject standard annotations cluster-wide.
- **OPA/Gatekeeper constraints:** Enforce that every `HTTPRoute` in a production namespace must have a corresponding `TimeoutPolicy`; this prevents teams from accidentally relying on unlimited defaults.
- **Observability check:** After applying a hierarchical policy, verify effective configuration via the controller's `/config-dump` endpoint or status conditions — not just the CRD spec — because inheritance resolution is implementation-specific and bugs exist.

---

### Q: Walk me through a scenario where you must migrate production traffic from a classic Ingress controller to Gateway API with zero downtime. What is your sequencing?

**Model Answer:**

This is a cut-over migration requiring parallel infrastructure, traffic shifting, and careful rollback gates:

1. **Inventory and compatibility audit** — catalogue all Ingress resources, annotations used, and TLS secrets; map each annotation to its Gateway API equivalent (native field, `PolicyAttachment`, or vendor CRD). Flag any features with no equivalent as migration blockers.
2. **Deploy Gateway API CRDs and a new GatewayClass** — install the target controller (e.g., Envoy Gateway, Cilium) alongside the existing nginx-ingress; both controllers run in parallel without interfering if they watch different resource types.
3. **Mirror routes** — create equivalent `Gateway` + `HTTPRoute` resources for a non-critical service. Use DNS-based or weighted LB traffic splitting to send a small percentage of real traffic to the new gateway; validate via metrics and error rates.
4. **Parallel run for all services** — progressively author `HTTPRoute` equivalents for all ingresses, validated by integration tests in staging. Keep old `Ingress` resources live; only the DNS/LB weight decides which path traffic uses.
5. **Incremental DNS cut-over** — shift DNS weights (10 % → 50 % → 100 %) service-by-service with monitoring burn-in periods. For external-dns users, annotate the new `Gateway` to take over DNS records once at 100 %.
6. **Rollback gate** — keep old Ingress resources and controller deployed but weighted at 0 % for at least one full traffic cycle (e.g., 24 h including peak); this allows instant rollback by re-weighting without a redeploy.
7. **Cleanup** — delete old `Ingress` resources, drain the old controller deployment, and remove the old `IngressClass`; update CI/CD pipelines to target `HTTPRoute` going forward.
