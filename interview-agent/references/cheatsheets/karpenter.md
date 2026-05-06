# Cheatsheet — Karpenter (v1)

## CRDs
- **EC2NodeClass:** AMI family, subnets (selector tags), SGs (selector tags), instance role, blockDeviceMappings, userData, metadataOptions.
- **NodePool:** scheduling requirements, taints, labels, limits, disruption (consolidation, expireAfter), weight.

## Minimal NodePool
```yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata: { name: default }
spec:
  template:
    spec:
      nodeClassRef: { group: karpenter.k8s.aws, kind: EC2NodeClass, name: default }
      requirements:
        - { key: kubernetes.io/arch, operator: In, values: [amd64] }
        - { key: karpenter.sh/capacity-type, operator: In, values: [spot, on-demand] }
        - { key: karpenter.k8s.aws/instance-family, operator: In, values: [m6i, m7i, c6i] }
      expireAfter: 720h
  disruption:
    consolidationPolicy: WhenEmptyOrUnderutilized
    consolidateAfter: 1m
  limits: { cpu: 1000 }
```

## Disruption knobs
- `consolidationPolicy: WhenEmpty` (safe) vs `WhenEmptyOrUnderutilized` (aggressive bin-pack).
- `disruption.budgets`: cap concurrent disruptions (e.g. `nodes: "10%"`).
- `expireAfter`: forces node rotation (use 720h to roll AMIs monthly).

## Spot interruption flow
EventBridge `EC2 Spot Instance Interruption Warning` → Karpenter cordons + drains within 2 min → provisions replacement first if disruption budget allows.

## Common pitfalls
- Pod with `nodeSelector` not in any NodePool → stays Pending forever; check `karpenter` controller logs.
- `topologySpreadConstraints` with `whenUnsatisfiable: DoNotSchedule` + tight zones → no node provisioned.
- Missing IAM perms on instance role for `ec2:RunInstances`, `iam:PassRole`, `eks:*`.
- AMI-selector tags don't match new AMI → nodes stuck on old AMI.

## Diagnose pending pod
```bash
kubectl get events --sort-by=.lastTimestamp | grep <pod>
kubectl logs -n kube-system deploy/karpenter -f | grep -i <pod>
```
Look for: "no instance type satisfied", "incompatible requirements", "limits exceeded".
