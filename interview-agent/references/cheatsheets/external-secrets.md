# Cheatsheet — External Secrets Operator (ESO)

## Architecture (one diagram)
```
[ Backend ]            [ Cluster ]
SecretsManager  ──┐    ┌─ ClusterSecretStore (provider + auth)
SSM Param Store ──┼──> │
Vault           ──┘    └─ ExternalSecret (refs CSS) ──> K8s Secret (synced)
                                                         ↑
                                                         └ refreshInterval (e.g. 1h)
```

## ClusterSecretStore (AWS Secrets Manager via IRSA)
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata: { name: aws-sm }
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-west-2
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets
            namespace: external-secrets
```

## ExternalSecret (typical)
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata: { name: app-db, namespace: my-app }
spec:
  refreshInterval: 1h
  secretStoreRef: { kind: ClusterSecretStore, name: aws-sm }
  target:
    name: app-db
    creationPolicy: Owner
    template:
      type: Opaque
      data:
        DB_URL: "postgres://{{ .user }}:{{ .pass }}@{{ .host }}:5432/{{ .db }}"
  data:
    - { secretKey: user, remoteRef: { key: prod/app/db, property: user } }
    - { secretKey: pass, remoteRef: { key: prod/app/db, property: pass } }
    - { secretKey: host, remoteRef: { key: prod/app/db, property: host } }
    - { secretKey: db,   remoteRef: { key: prod/app/db, property: db } }
```

## Pod restart on rotation
ESO updates the K8s Secret in place. To roll pods automatically:
- Annotate Deployment: `reloader.stakater.com/auto: "true"` (Stakater Reloader), **or**
- Use `secret.reloader.stakater.com/reload: app-db`.

## Common bugs
- IRSA SA missing `secretsmanager:GetSecretValue` → ES status "secret not found / not authorized".
- Secret has special chars in JSON → use `template` and Go-template escaping.
- `refreshInterval: 1m` against SM in prod → throttling; default 1h.
- Missing `decodingStrategy: Base64` when remote secret is base64.

## Diagnose
```bash
kubectl describe externalsecret app-db -n my-app
# Look at Status.Conditions and events.
kubectl logs -n external-secrets deploy/external-secrets
```
