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
