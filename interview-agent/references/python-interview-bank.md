# Python Interview Bank — SRE / Platform flavour

> Format: **Q** → **What they want to see** → **Answer** (with code) → **Gotchas**.
> Difficulty escalates by section: warm-up → idioms → concurrency → AWS/boto3 → systems.

---

## Section A — Warm-ups (phone screen)

### A1. Reverse the words in a sentence in-place-ish.
```python
def reverse_words(s: str) -> str:
    return " ".join(reversed(s.split()))
```
*Gotcha:* `s.split()` collapses multiple spaces. If asked to preserve them, use `re.split(r'(\s+)', s)`.

### A2. Group a list of dicts by a key.
```python
from collections import defaultdict
def group_by(items, key):
    out = defaultdict(list)
    for it in items:
        out[it[key]].append(it)
    return dict(out)
```
Follow-up: do it in O(n) without `defaultdict` → `out.setdefault(k, []).append(it)`.

### A3. Find duplicates in a list.
```python
from collections import Counter
dups = [k for k, v in Counter(xs).items() if v > 1]
```

### A4. Implement an LRU cache without `functools.lru_cache`.
```python
from collections import OrderedDict
class LRU:
    def __init__(self, n):
        self.n, self.d = n, OrderedDict()
    def get(self, k):
        if k not in self.d: return -1
        self.d.move_to_end(k); return self.d[k]
    def put(self, k, v):
        if k in self.d: self.d.move_to_end(k)
        self.d[k] = v
        if len(self.d) > self.n: self.d.popitem(last=False)
```

---

## Section B — Idioms FAANG interviewers love

### B1. Mutable default argument bug.
```python
def append_to(x, lst=[]):  # BUG
    lst.append(x); return lst
```
Why: default is evaluated once at function-def time. Fix: `lst=None; lst = lst or []`.

### B2. `is` vs `==`.
- `is` → identity (same object). `==` → equality (`__eq__`). `None`, `True`, `False` always with `is`. Small ints (-5..256) and interned strings can fool you.

### B3. Generators vs lists — when?
- Generators: lazy, O(1) memory, single-pass. Use for streaming logs, paginating boto3.
```python
def paginate(client, op, **kw):
    paginator = client.get_paginator(op)
    for page in paginator.paginate(**kw):
        yield from page.get("Items", [])
```

### B4. `__slots__` — when and why?
- Skip per-instance `__dict__`; faster attribute access; less memory. Use for value classes with millions of instances. Trade-off: no dynamic attributes, no multiple inheritance with non-slot classes.

### B5. Decorator that retries with exponential backoff.
```python
import time, functools, random
def retry(tries=3, base=0.2, jitter=True, exc=(Exception,)):
    def deco(fn):
        @functools.wraps(fn)
        def wrap(*a, **k):
            for i in range(tries):
                try: return fn(*a, **k)
                except exc:
                    if i == tries - 1: raise
                    sleep = base * (2 ** i) + (random.random() * base if jitter else 0)
                    time.sleep(sleep)
        return wrap
    return deco
```

---

## Section C — Concurrency

### C1. Threads vs processes vs asyncio — pick one for: (a) parallel S3 PUTs, (b) CPU-bound image resize, (c) 10k HTTP fan-out.
- (a) threads or asyncio (network-bound, GIL releases on I/O).
- (b) processes (`ProcessPoolExecutor`) — GIL blocks CPU-bound threads.
- (c) asyncio (`httpx.AsyncClient`) — best memory profile.

### C2. Implement a bounded concurrent fetcher with asyncio.
```python
import asyncio, httpx
async def fetch_all(urls, concurrency=20):
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(timeout=10) as c:
        async def one(u):
            async with sem:
                r = await c.get(u); return r.status_code, u
        return await asyncio.gather(*(one(u) for u in urls), return_exceptions=True)
```

### C3. What does the GIL actually lock?
- The Python bytecode interpreter — only one thread executes Python bytecode at a time. Released around I/O syscalls and inside C extensions that explicitly release it.

---

## Section D — boto3 / AWS

### D1. Why is `boto3.client('s3')` not thread-safe in some cases?
- `Session` is not thread-safe; `client` is generally thread-safe. Best practice: one Session per thread.

### D2. Paginate every IAM role and find ones with `*` in policy.
```python
import boto3
iam = boto3.client("iam")
def risky_roles():
    for page in iam.get_paginator("list_roles").paginate():
        for r in page["Roles"]:
            for pol in iam.list_attached_role_policies(RoleName=r["RoleName"])["AttachedPolicies"]:
                pv = iam.get_policy(PolicyArn=pol["PolicyArn"])["Policy"]
                doc = iam.get_policy_version(PolicyArn=pol["PolicyArn"], VersionId=pv["DefaultVersionId"])
                if "*" in str(doc):
                    yield r["Arn"], pol["PolicyName"]
```

### D3. STS AssumeRole and refresh creds.
```python
import boto3
from botocore.session import Session
from botocore.credentials import RefreshableCredentials, AssumeRoleCredentialFetcher
def assumed_session(role_arn, session_name="sre"):
    fetcher = AssumeRoleCredentialFetcher(
        client_creator=boto3.client,
        source_credentials=Session().get_credentials(),
        role_arn=role_arn, extra_args={"RoleSessionName": session_name},
        cache={},
    )
    creds = RefreshableCredentials.create_from_metadata(
        metadata=fetcher.fetch_credentials(),
        refresh_using=fetcher.fetch_credentials,
        method="sts-assume-role",
    )
    s = Session(); s._credentials = creds
    return boto3.Session(botocore_session=s)
```

---

## Section E — Kubernetes API from Python

### E1. List all pods across all namespaces and report the ones not Ready.
```python
from kubernetes import client, config
config.load_kube_config()  # or load_incluster_config()
v1 = client.CoreV1Api()
for p in v1.list_pod_for_all_namespaces(watch=False).items:
    ready = next((c.status for c in (p.status.conditions or []) if c.type == "Ready"), None)
    if ready != "True":
        print(p.metadata.namespace, p.metadata.name, ready)
```

### E2. Watch ConfigMap changes.
```python
from kubernetes import client, config, watch
config.load_kube_config(); v1 = client.CoreV1Api()
w = watch.Watch()
for ev in w.stream(v1.list_namespaced_config_map, namespace="kube-system", timeout_seconds=0):
    print(ev["type"], ev["object"].metadata.name)
```

---

## Section F — Systems / design-y

### F1. Design a rate-limited webhook receiver in FastAPI.
- Sliding-window counter in Redis (`ZADD` ts, `ZREMRANGEBYSCORE` < now-60s, `ZCARD` < limit). Reject with 429 + `Retry-After`.

### F2. Idempotency key on a POST.
- Hash `(method, path, body)` → store in Redis with TTL = 24h → if key exists, return cached response.

### F3. Implement a deduper for noisy alerts (60-min window).
```python
import time, hashlib
class Dedup:
    def __init__(self, window=3600): self.w, self.seen = window, {}
    def _k(self, alert): return hashlib.sha1(repr(sorted(alert.items())).encode()).hexdigest()
    def accept(self, alert):
        now = time.time()
        self.seen = {k: t for k, t in self.seen.items() if now - t < self.w}
        k = self._k(alert)
        if k in self.seen: return False
        self.seen[k] = now; return True
```

---

## Section G — Trick questions

### G1. What does `[[]]*3` produce vs `[[] for _ in range(3)]`?
- The first is **three references to the same list**; appending to one changes all. Common bug in matrix init.

### G2. `dict.get(k, default)` vs `dict.setdefault(k, default)`?
- `get` doesn't insert; `setdefault` inserts if missing.

### G3. What's wrong:
```python
async def main():
    result = httpx.get("https://x")  # blocking inside async!
```
- Blocks the event loop. Use `httpx.AsyncClient`.
