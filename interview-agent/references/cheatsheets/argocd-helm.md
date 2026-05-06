# Cheatsheet — ArgoCD + Helm

## ArgoCD core CRDs
- **Application** — one app, one source (Helm/Kustomize/plain manifests), one destination.
- **AppProject** — RBAC + allowed sources/destinations.
- **ApplicationSet** — generators (list, cluster, git, matrix, scmProvider) → fan-out.
- **AppOfApps** — one Application that templates child Applications (older pattern).

## Sync options worth knowing
```yaml
syncPolicy:
  automated: { prune: true, selfHeal: true, allowEmpty: false }
  syncOptions:
    - CreateNamespace=true
    - ServerSideApply=true
    - ApplyOutOfSyncOnly=true
    - PruneLast=true
  retry:
    limit: 5
    backoff: { duration: 30s, maxDuration: 5m, factor: 2 }
```

## Sync waves + hooks
- Annotation `argocd.argoproj.io/sync-wave: "-1"` (lower = earlier).
- Hooks: `PreSync`, `Sync`, `PostSync`, `SyncFail` via `argocd.argoproj.io/hook` annotation.
- Use case: run a `Job` (DB migration) PreSync, then deploy.

## ignoreDifferences (HPA fights)
```yaml
ignoreDifferences:
  - group: apps
    kind: Deployment
    jsonPointers: [/spec/replicas]
```

## ApplicationSet — cluster generator
```yaml
generators:
  - clusters:
      selector: { matchLabels: { env: nprd } }
template:
  metadata: { name: '{{name}}-platform' }
  spec:
    destination: { server: '{{server}}', namespace: platform }
    source: { repoURL: ..., path: charts/platform, helm: { valueFiles: [values-{{name}}.yaml] } }
```

## Helm essentials
- Release state stored as Secret in release namespace.
- `helm diff upgrade` (plugin) before every prod change.
- `--atomic --wait --timeout 10m` for safer prod installs.
- `library` charts: shared templates, no resources.

## Diagnose stuck sync
1. `argocd app get <a>` → look at conditions.
2. `argocd app logs <a>` (controller logs).
3. `kubectl describe application <a> -n argocd`.
4. Check resource health (Deployment `progressDeadlineSeconds`, Job non-completed).
5. Check hooks finished.
6. Check webhooks (Istio etc.) injecting fields → use `ignoreDifferences`.
