# Visual cheat sheets

Reference diagrams kept alongside the written material for quick revision.

| File | Topic | Source |
|---|---|---|
| `kubernetes-ingress-cheatsheet.jpg` | Kubernetes Ingress — 10 Q&A panels: Ingress vs Service, path- and host-based routing, TLS, `pathType`, and a troubleshooting runbook | Third-party infographic, author not identified on the image |
| `ingress-vs-gateway-api-vs-api-gateway.gif` | Side-by-side scope comparison: Ingress (single namespace) vs Gateway API (multi-namespace) vs API Gateway (multi-cluster / external backends) | Vishakha Sadhwani — [@vsadhwani](https://www.linkedin.com/in/vishakhasadhwani/) (credit visible in the image) |

## Attribution and use

These are third-party educational graphics retained for personal interview
preparation. Original author credits are left intact in the images themselves
and must not be cropped out. They are **not** original work of this repository.

Note that this repo is published via GitHub Pages, so anything here is publicly
reachable. If either author objects to redistribution, remove the file and the
corresponding entry in `index.html`.

## Notes

- `ingress-vs-gateway-api-vs-api-gateway.gif` is **13 MB** (305 frames). It is
  slow to load on mobile connections. If that becomes a problem, convert it to
  a single still frame or an MP4/WebM — `gifsicle -O3 --lossy=80` or `ffmpeg`
  will both cut it dramatically.
- Git stores binaries in full for every revision. Prefer replacing these files
  rarely, or not at all, to keep clone size reasonable.

## Interview relevance

The Ingress → Gateway API progression is a common senior-level follow-up: once
you explain Ingress routing, expect "what are its limitations?" The short
answer is that Ingress overloads annotations for anything beyond host/path
rules and is namespace-scoped, which is exactly what Gateway API's role-oriented
resources (`GatewayClass` / `Gateway` / `HTTPRoute`) were introduced to fix.
The second graphic is the fastest way to hold that distinction in memory.
