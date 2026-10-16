# Ingress vs Gateway API vs API Gateway

Three things with confusingly similar names that solve different problems. The
distinction is **scope** — how far the thing can reach.

Original graphic by Vishakha Sadhwani ([@vsadhwani](https://www.linkedin.com/in/vishakhasadhwani/)).

---

## At a glance

| | Ingress | Gateway API | API Gateway |
|---|---|---|---|
| **Scope** | Same cluster, **single namespace** | Same cluster, **multiple namespaces** | **Multiple clusters**, external backends |
| **Kind of thing** | Kubernetes API object | Kubernetes API objects (successor to Ingress) | Product / platform, usually outside the cluster |
| **Routing** | Host and path | `HTTPRoute`, `TCPRoute`, `GRPCRoute` | Routes/APIs with versioning, transforms, policies |
| **Implementations** | NGINX, Traefik, HAProxy | Istio, NGINX, Contour | Kong, Apigee, AWS API Gateway, Traefik Hub |
| **Extensibility** | Annotations | Typed, role-oriented resources | Full policy engine |

## Request flow

**Ingress**
```
Client → External Load Balancer (cloud provider)
       → Ingress Controller (NGINX / Traefik / HAProxy)
       → Ingress Rules (host / path based)
       → Services → Pods          [namespace: app-ns]
```

**Gateway API**
```
Client → External Load Balancer (cloud provider)
       → Gateway (GatewayClass: Istio / NGINX / Contour)
       → Routes (HTTPRoute, TCPRoute, GRPCRoute)
       → Services → Pods          [namespace team-A, team-B, team-C]
```

**API Gateway**
```
Client → External Load Balancer or CDN
       → API Gateway (Kong, Apigee, AWS API GW, NGINX, Traefik Hub)
       → Routes / APIs (versioning, transform, policies)
       → Backends: multiple clusters, microservices, legacy systems,
                   serverless (Lambda), third-party APIs
```

## What each one adds

**Ingress** — the original. One namespace, host/path rules, and anything beyond
that gets bolted on through controller-specific **annotations**. That is its
defining limitation: annotations aren't typed, aren't portable between
controllers, and don't validate.

**Gateway API** — the successor, built to fix exactly that. Splits one
overloaded object into **role-oriented resources**:

| Resource | Owned by |
|---|---|
| `GatewayClass` | Infrastructure provider |
| `Gateway` | Cluster operator |
| `HTTPRoute` / `TCPRoute` / `GRPCRoute` | Application developer |

That separation is the point: a platform team runs the `Gateway`, and app teams
attach routes from **their own namespaces** without editing a shared object.

**API Gateway** — a different category, not a Kubernetes object. Sits in front
of everything and owns cross-cutting concerns:

- Authentication / authorization
- Caching
- WAF
- Rate limiting
- Analytics
- Request/response transformation

It can route to multiple clusters *and* to things that aren't clusters at all —
legacy systems, Lambda, third-party APIs.

## Choosing between them

- Single cluster, single team, simple host/path rules → **Ingress** is fine.
- Multiple teams or namespaces sharing ingress infrastructure, or you need
  traffic splitting, header matching, or gRPC → **Gateway API**.
- You need auth, rate limiting, quotas, API versioning, or you're fronting
  backends beyond Kubernetes → **API Gateway**.

They also compose: an API Gateway in front, Gateway API inside the cluster.

---

## Interview framing

The common senior-level follow-up after you explain Ingress is *"what are its
limitations?"* The short answer:

> Ingress is namespace-scoped and overloads annotations for anything beyond
> host/path rules, which makes configuration controller-specific and
> unportable. Gateway API replaces it with typed, role-separated resources so
> platform and application teams own different objects.

And if asked whether Gateway API replaces an API Gateway: **no** — Gateway API
is in-cluster traffic routing, an API Gateway is an edge product doing policy,
auth, and cross-system routing.

See also: [Kubernetes Ingress cheat sheet](kubernetes-ingress.md).
