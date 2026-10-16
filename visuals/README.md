# Cheat sheets — Kubernetes networking

Reference material kept as **Markdown, not images**: searchable with `grep`,
readable on any device, diffable in git, and usable by the daily agent. The
source infographics were transcribed rather than committed.

| File | Topic | Source |
|---|---|---|
| [`kubernetes-ingress.md`](kubernetes-ingress.md) | Ingress in 10 questions: Ingress vs Service, path- and host-based routing, TLS, `pathType`, and a troubleshooting runbook with commands | Third-party infographic, author not identified on the image |
| [`ingress-vs-gateway-api-vs-api-gateway.md`](ingress-vs-gateway-api-vs-api-gateway.md) | Scope comparison: Ingress (single namespace) vs Gateway API (multi-namespace) vs API Gateway (multi-cluster / external backends) | Vishakha Sadhwani — [@vsadhwani](https://www.linkedin.com/in/vishakhasadhwani/) |

## Why text instead of the original images

- **Searchable** — `grep -r pathType .` finds it; an image doesn't.
- **Small** — the two files are ~11 KB combined. The original GIF alone was
  13 MB, and git stores binaries in full for every revision.
- **Accessible** — works with screen readers, text selection, and copy-paste of
  the YAML, none of which an image supports.
- **Agent-readable** — the daily agent can generate Q&A from Markdown.

## Fidelity

The transcriptions are faithful to the originals in content and structure.
Three YAML typos in the Ingress graphic were corrected so the manifests are
actually valid (`app2.axample.com` → `app2.example.com`, `hostt:` → `host:`,
and the `tls.hosts` indentation). A small amount of context was added and is
marked as such — the `kubectl create secret tls` command, the note that empty
`kubectl get endpoints` output usually means a selector mismatch, and the
interview-framing sections.

## Attribution

These summarise third-party educational material and are **not** original work
of this repository. Credit is recorded above and in each file. This repo is
published via GitHub Pages, so anything here is publicly reachable; if an
author objects, delete the file and its entry in `index.html`.
