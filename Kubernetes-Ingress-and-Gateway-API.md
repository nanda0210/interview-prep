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
