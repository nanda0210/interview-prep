# Kubernetes Ingress — interview cheat sheet

Ten questions that cover most of what gets asked about Ingress, with the YAML
you should be able to write on a whiteboard.

---

## 1. What is Kubernetes Ingress?

- A Kubernetes API object that manages **external HTTP/HTTPS traffic** entering
  the cluster and routes it to Services.
- Provides a **single entry point** for multiple applications.
- Supports **host-based** and **path-based** routing.

```
Internet → Ingress (HTTP/HTTPS) → Service A (/app1) → Pods
                                → Service B (/app2) → Pods
```

## 2. Why do we use Ingress?

- Expose multiple services behind a **single IP/hostname**.
- Manage routing rules by host and path.
- Works with a load balancer or NodePort service.
- Centralised HTTP/HTTPS routing.

| Without Ingress | With Ingress |
|---|---|
| Each service needs its own public IP / LoadBalancer | Single entry point |
| Difficult to manage | Rules route traffic |
| Not scalable | Easier to manage, scalable and clean |

> The cost angle is worth saying out loud: one cloud LoadBalancer per Service
> gets expensive fast. Ingress collapses that to one.

## 3. What is an Ingress Controller?

- The component that **watches Ingress resources and implements** their rules.
  The Ingress object alone does nothing without one.
- It configures a reverse proxy to route traffic to the correct Services.

Common controllers: **NGINX Ingress Controller**, **Traefik**, **HAProxy**,
and cloud-provider-specific controllers (AWS ALB, GKE, AGIC).

```
Ingress (resource with rules) → Ingress Controller (implements rules)
                                       ↓
                               Kubernetes Services → Pods
```

## 4. Difference between Ingress and Service

| Service | Ingress |
|---|---|
| Provides stable access to Pods | Provides HTTP/HTTPS routing |
| Connects clients to Pods | Routes requests to Services |
| Supports multiple types (ClusterIP, NodePort, LoadBalancer) | Supports host-based and path-based routing |
| Can support TCP/UDP | Primarily for HTTP/HTTPS |
| Usually used inside the cluster | Usually used to expose multiple services externally |

## 5. Path-based routing

Routes requests to different services based on **URL path**.

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

## 6. Host-based routing

Routes traffic based on **hostname** — useful for multiple applications on
different domains.

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

## 7. TLS in Kubernetes Ingress

- Ingress can terminate **HTTPS/TLS**.
- Uses a TLS **Secret** holding the certificate and private key.

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

Create the Secret with:

```bash
kubectl create secret tls example-tls --cert=tls.crt --key=tls.key
```

## 8. What is `pathType`?

Defines how the path is matched against the incoming request.

| pathType | Meaning |
|---|---|
| `Prefix` | Matches the path prefix. Most commonly used. |
| `Exact` | Matches the exact path. |
| `ImplementationSpecific` | Behaviour depends on the Ingress Controller. |

```yaml
path: /api
pathType: Prefix     # matches /api and /api/users
```

`pathType` is **required** in `networking.k8s.io/v1`. Omitting it is a common
mistake carried over from the old `extensions/v1beta1` API.

## 9. Does Ingress replace a Service?

**No.** Ingress works *together* with Services:

- Ingress handles external HTTP/HTTPS routing **to** Services.
- Services route traffic **to** Pods.

```
Internet → Ingress → Service → Pods
```

## 10. Troubleshooting an Ingress that isn't working

Work outside-in:

```bash
# 1. Check the Ingress resource
kubectl get ingress
kubectl describe ingress <name>

# 2. Check the Ingress Controller
kubectl get pods -n <ingress-namespace>
kubectl logs <controller-pod>

# 3. Verify Services and Endpoints
kubectl get svc
kubectl get endpoints        # empty endpoints = selector/label mismatch

# 4. Check rules: host, path, and annotations
# 5. Check DNS and TLS certificates
# 6. Check application logs
```

**Common causes**

- Ingress Controller not running
- Incorrect host or path
- Service not reachable
- Wrong service name or port
- DNS not pointing to the Ingress IP
- TLS certificate / secret issues
- Firewall or security group blocking traffic

> Step 3 catches the single most common case: the Ingress and Service look
> perfect but `kubectl get endpoints` is empty, meaning the Service selector
> doesn't match any Pod labels.

---

## Architecture (high level)

```
Client (HTTP/HTTPS)
      ↓
   Internet
      ↓
Ingress Controller  (Load Balancer / NodePort)
      ↓
   Ingress          (routing rules)
      ↓
  Services
      ↓
    Pods
```

---

### Transcription notes

Converted from a reference infographic for readability and searchability. Three
typos in the original image were corrected here so the YAML is valid:
`app2.axample.com` → `app2.example.com`, `hostt:` → `host:`, and the TLS block's
`- hosts:` indentation. The `kubectl create secret tls` command and the
endpoints/`pathType` notes are added context, not from the original.

See also: [Ingress vs Gateway API vs API Gateway](ingress-vs-gateway-api-vs-api-gateway.md).
