# Cheatsheet — EKS ConfigMaps you'll be asked about

The 7 ConfigMaps from the FSRE-20 brief. Each entry: where it lives, what it does, what to look for.

---

## 1. `kube-system/amazon-vpc-cni`
**Owns:** AWS VPC CNI runtime config.
**Key keys (env-style):**
- `WARM_IP_TARGET` / `MINIMUM_IP_TARGET` — pre-warm IPs per node.
- `WARM_ENI_TARGET` — pre-warm ENIs.
- `ENABLE_PREFIX_DELEGATION=true` — assign /28 prefixes (×16 IPs/ENI).
- `AWS_VPC_K8S_CNI_CUSTOM_NETWORK_CFG` — secondary CIDR pod IPs.
- `ENABLE_POD_ENI=true` — required for SecurityGroupPolicy (SG-for-Pods).
**Look for:** prefix delegation flipped on for IP exhaustion fixes.

## 2. `kube-system/aws-auth`
**Owns:** maps IAM ARNs → K8s usernames + RBAC groups (legacy auth path).
**Keys:** `mapRoles`, `mapUsers`, `mapAccounts` (YAML inside YAML).
**Footguns:** single ConfigMap; concurrent edits race; malformed YAML locks everyone out *except* the cluster creator. Migrate to **EKS access entries** (API).

## 3. `kube-system/coredns`
**Owns:** the **Corefile** for the CoreDNS deployment.
**Key blocks:**
- `kubernetes cluster.local in-addr.arpa ip6.arpa { pods insecure }`
- `forward . /etc/resolv.conf` (or per-zone forward to internal resolvers).
- `cache 30`, `loadbalance`, `reload`.
**Look for:** added internal zone stanzas; NodeLocal DNSCache deployed alongside.

## 4. `kube-system/extension-apiserver-authentication`
**Owns:** root CA used by aggregated API servers (e.g. metrics-server) to authenticate clients.
**Keys:** `client-ca-file`, `requestheader-client-ca-file`, `requestheader-allowed-names`, `requestheader-extra-headers-prefix`, `requestheader-group-headers`, `requestheader-username-headers`.
**You rarely edit this** — managed by the control plane. If broken, aggregated APIs fail with TLS errors.

## 5. `kube-system/kube-apiserver-legacy-sa-token-tracking`
**Owns:** since-time marker for tracking *legacy* (non-projected) ServiceAccount tokens still in use. Used to plan removal in newer K8s versions.
**Keys:** `since_time` (RFC3339).
**Look for:** present on clusters that have started the legacy-token deprecation tracking; no manual edits.

## 6. `kube-system/kube-proxy`
**Owns:** the **kubeconfig** kube-proxy uses to talk to the API server.
**Keys:** `kubeconfig` (a YAML kubeconfig).
**Look for:** server URL pointing at the API endpoint; cluster CA data correct.

## 7. `kube-system/kube-proxy-config`
**Owns:** the kube-proxy **KubeProxyConfiguration**.
**Key fields:**
- `mode: iptables | ipvs | nftables`
- `clusterCIDR` (pod CIDR).
- `iptables.masqueradeAll`, `iptables.syncPeriod`.
- `ipvs.scheduler` if mode=ipvs.
**Look for:** mode flipped to `ipvs` for clusters with > 5k Services.

---

## Diff command
```bash
for cm in amazon-vpc-cni aws-auth coredns extension-apiserver-authentication kube-apiserver-legacy-sa-token-tracking kube-proxy kube-proxy-config; do
  echo "=== $cm ==="
  kubectl --context=$CLUSTER_A get cm -n kube-system $cm -o yaml > /tmp/a-$cm.yaml
  kubectl --context=$CLUSTER_B get cm -n kube-system $cm -o yaml > /tmp/b-$cm.yaml
  diff -u /tmp/a-$cm.yaml /tmp/b-$cm.yaml || true
done
```
