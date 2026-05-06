# Python Interview Bank — Extended (250 Qs, 3 Tracks)

> **How to read this file.** It is structured as **three tracks**, each readable end-to-end as a mini-book.
>
> - **Track A — SRE-first (Sections A.1-A.7, ~115 Qs).** Boto3 / AWS, Kubernetes Python client, asyncio + concurrency, system-design-in-Python, networking, file I/O, observability. This is what your real interview loops at AWS / Salesforce / Google SRE / Meta Production Engineering will hammer.
> - **Track B — Thematic (Sections B.8-B.17, ~125 Qs).** Testing, performance, type hints, decorators, generators, OOP, functional, strings/regex, data structures (with ~10 algos integrated), Pythonic gotchas. Builds the language fluency that bar-raisers probe.
> - **Track C — Algorithms appendix (Section C.18, ~50 Qs).** Top FAANG-asked LeetCode patterns translated to idiomatic Python: sliding window, two-pointer, BFS/DFS, heap, intervals, prefix sums, trie, union-find, monotonic stack, dynamic programming.
>
> **Each Q has 4 parts:**
> 1. **Prose** — 2-3 sentences on why interviewers ask it and the trap.
> 2. **Script** — runnable, type-hinted Python (often with `__main__` smoke).
> 3. **Dense one-liner** — the shortest correct version, for memorising.
> 4. **Complexity + Gotcha line.**
>
> **Q numbering is global** (Q.001–Q.250) so you can grep/cite any question fast.
>
> **Companies tagged** per the public reputation of the *question pattern*, not as leak claims. If you've seen the same shape at a different company, that's normal — these patterns are universal.

---

## Quick TOC

| Track | Section | Topic | Qs | Q-range |
|---|---|---|---|---|
| A | A.1 | boto3 / AWS deep | 25 | Q.001-Q.025 |
| A | A.2 | Kubernetes Python client | 15 | Q.026-Q.040 |
| A | A.3 | Concurrency: asyncio / threading / GIL | 20 | Q.041-Q.060 |
| A | A.4 | System design in Python | 20 | Q.061-Q.080 |
| A | A.5 | Networking (sockets, http, retries) | 12 | Q.081-Q.092 |
| A | A.6 | File I/O & serialization | 12 | Q.093-Q.104 |
| A | A.7 | Logging / metrics / tracing | 10 | Q.105-Q.114 |
| B | B.8 | Testing (pytest, mocking, hypothesis) | 15 | Q.115-Q.129 |
| B | B.9 | Performance & profiling | 12 | Q.130-Q.141 |
| B | B.10 | Type hints | 12 | Q.142-Q.153 |
| B | B.11 | Decorators / context managers / descriptors | 12 | Q.154-Q.165 |
| B | B.12 | Iterators / generators / coroutines | 12 | Q.166-Q.177 |
| B | B.13 | OOP / dataclasses / MRO / metaclasses | 12 | Q.178-Q.189 |
| B | B.14 | Functional | 12 | Q.190-Q.201 |
| B | B.15 | Strings & regex | 10 | Q.202-Q.211 |
| B | B.16 | Data structures (with integrated algos) | 22 | Q.212-Q.233 |
| B | B.17 | Pythonic gotchas / anti-patterns | 15 | Q.234-Q.248 |
| C | C.18 | Algorithms appendix (FAANG patterns) | 50 | Q.249-Q.298 |

> **Total: 298 questions** (target was 250; came in heavy on system-design-in-Python and algorithms because those are highest-leverage in interviews).

---

# Track A — SRE-first

## A.1 boto3 / AWS deep — Q.001-Q.025

### Q.001 Why is `boto3.client('s3')` thread-safe but `boto3.Session()` is not?

Interviewers test whether you've actually run boto3 in production. `Client` instances are thread-safe; `Session` (which holds credentials, config, region) is not — sharing one `Session` across threads can race on credential refresh.

```python
import boto3
import threading
from concurrent.futures import ThreadPoolExecutor

# WRONG: one shared Session across threads.
shared_session = boto3.Session()
def bad(key: str) -> int:
    s3 = shared_session.client("s3")  # may race on cred refresh
    return s3.head_object(Bucket="b", Key=key)["ContentLength"]

# RIGHT: one Session per thread, share the Client.
_local = threading.local()
def session() -> boto3.Session:
    if not hasattr(_local, "s"):
        _local.s = boto3.Session()
    return _local.s

def good(key: str) -> int:
    s3 = session().client("s3")
    return s3.head_object(Bucket="b", Key=key)["ContentLength"]
```

**Dense one-liner:** one `Session` per thread (via `threading.local()`), share the `Client`.

**Complexity:** N/A.  **Gotcha:** Even reading `Session.region_name` from multiple threads can race during a credential refresh.

---

### Q.002 Paginate every IAM role and yield those with `*` in any attached policy.

Tests paginator usage and stream-processing instead of loading everything into memory. Interviewers see candidates who `list_roles()` once and miss the truncation; that's an instant downgrade.

```python
import json
import boto3
from typing import Iterator

def risky_roles() -> Iterator[tuple[str, str]]:
    iam = boto3.client("iam")
    for page in iam.get_paginator("list_roles").paginate():
        for role in page["Roles"]:
            for pol in iam.list_attached_role_policies(RoleName=role["RoleName"])["AttachedPolicies"]:
                meta = iam.get_policy(PolicyArn=pol["PolicyArn"])["Policy"]
                doc = iam.get_policy_version(
                    PolicyArn=pol["PolicyArn"],
                    VersionId=meta["DefaultVersionId"],
                )["PolicyVersion"]["Document"]
                if "*" in json.dumps(doc):
                    yield role["Arn"], pol["PolicyName"]
```

**Dense one-liner:**
```python
[(r["Arn"], p["PolicyName"]) for page in iam.get_paginator("list_roles").paginate() for r in page["Roles"] for p in iam.list_attached_role_policies(RoleName=r["RoleName"])["AttachedPolicies"] if "*" in json.dumps(iam.get_policy_version(PolicyArn=p["PolicyArn"], VersionId=iam.get_policy(PolicyArn=p["PolicyArn"])["Policy"]["DefaultVersionId"])["PolicyVersion"]["Document"])]
```

**Complexity:** O(R × P) API calls (R roles, P policies/role).  **Gotcha:** `"*"` substring also matches benign uses inside ARNs; for prod, parse `Statement[*].Action` and check explicitly.

---

### Q.003 Stream a 50 GB S3 object line-by-line without buffering it all.

Tests whether you understand `StreamingBody` and that `Body.read()` loads the whole object. Common bug: people call `obj["Body"].read().decode().splitlines()` on a multi-GB log and OOM the box.

```python
import boto3
import io
from typing import Iterator

def s3_lines(bucket: str, key: str, chunk_size: int = 1 << 20) -> Iterator[str]:
    body = boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"]
    buf = b""
    for chunk in body.iter_chunks(chunk_size):
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            yield line.decode("utf-8", errors="replace")
    if buf:
        yield buf.decode("utf-8", errors="replace")
```

**Dense one-liner:**
```python
for line in io.TextIOWrapper(boto3.client("s3").get_object(Bucket=b, Key=k)["Body"]): ...
```

**Complexity:** O(n) bytes, O(1) memory.  **Gotcha:** `TextIOWrapper` over `StreamingBody` works but doesn't honour `iter_chunks` size — for very large objects use the explicit chunk loop.

---

### Q.004 STS AssumeRole with auto-refreshing credentials.

Long-running daemons that hold short-lived STS creds will start failing once they expire. Interviewers want to see `RefreshableCredentials`, not a manual `time.sleep(3500); reassume()` loop.

```python
import boto3
from botocore.session import Session as BotoSession
from botocore.credentials import RefreshableCredentials, AssumeRoleCredentialFetcher

def assumed_session(role_arn: str, name: str = "sre") -> boto3.Session:
    fetcher = AssumeRoleCredentialFetcher(
        client_creator=boto3.client,
        source_credentials=BotoSession().get_credentials(),
        role_arn=role_arn,
        extra_args={"RoleSessionName": name, "DurationSeconds": 3600},
        cache={},
    )
    creds = RefreshableCredentials.create_from_metadata(
        metadata=fetcher.fetch_credentials(),
        refresh_using=fetcher.fetch_credentials,
        method="sts-assume-role",
    )
    bs = BotoSession()
    bs._credentials = creds
    return boto3.Session(botocore_session=bs)
```

**Dense one-liner:** `RefreshableCredentials.create_from_metadata(..., refresh_using=fetcher.fetch_credentials, ...)`.

**Complexity:** N/A.  **Gotcha:** `cache={}` is in-memory; for multi-process use a file cache or you'll get N×STS calls.

---

### Q.005 Multipart upload a file with a custom part size and resumability.

Tests knowledge of `TransferConfig` vs raw multipart. The "trick" is that `upload_file` already does multipart — the real interview question is how to tune part size + parallelism for big files.

```python
import boto3
from boto3.s3.transfer import TransferConfig

def upload_large(local: str, bucket: str, key: str) -> None:
    cfg = TransferConfig(
        multipart_threshold=64 * 1024 * 1024,
        multipart_chunksize=64 * 1024 * 1024,
        max_concurrency=10,
        use_threads=True,
    )
    boto3.client("s3").upload_file(local, bucket, key, Config=cfg,
                                   ExtraArgs={"ServerSideEncryption": "AES256"})
```

**Dense one-liner:** `boto3.client("s3").upload_file(p, b, k, Config=TransferConfig(multipart_chunksize=64<<20, max_concurrency=10))`.

**Complexity:** O(n) bytes, parallel parts.  **Gotcha:** S3 max 10 000 parts; with 64 MB parts you cap at ~640 GB. For larger, use 128 MB+ parts.

---

### Q.006 Write a `boto3` retry-on-throttling decorator that respects `Retry-After`.

Hand-written backoff is the wrong answer — botocore already does it. Interviewers want to see you know about `botocore.config.Config(retries={"mode": "adaptive"})`. The wrapper below is for non-AWS calls.

```python
import time
import random
import functools
import botocore.exceptions
from typing import Callable, TypeVar, Any
T = TypeVar("T")

def retry_throttled(tries: int = 5, base: float = 0.2) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def deco(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrap(*a: Any, **kw: Any) -> T:
            for i in range(tries):
                try:
                    return fn(*a, **kw)
                except botocore.exceptions.ClientError as e:
                    code = e.response["Error"]["Code"]
                    if code not in {"Throttling", "ThrottlingException", "TooManyRequestsException", "RequestLimitExceeded"}:
                        raise
                    if i == tries - 1:
                        raise
                    time.sleep(base * (2 ** i) + random.random() * base)
            raise RuntimeError("unreachable")
        return wrap
    return deco
```

**Dense one-liner (built-in):** `boto3.client("s3", config=Config(retries={"max_attempts": 10, "mode": "adaptive"}))`.

**Complexity:** Worst-case `tries × call`.  **Gotcha:** Don't retry on `ValidationException` / `AccessDenied` — those are not transient.

---

### Q.007 Bulk-tag every EC2 instance in a region by tag-pair.

Tests batching: `create_tags` accepts up to 1000 resources at once. Doing one call per instance is the slow wrong answer.

```python
import boto3
from itertools import islice
from typing import Iterable, Iterator

def chunk(it: Iterable, n: int) -> Iterator[list]:
    it = iter(it)
    while batch := list(islice(it, n)):
        yield batch

def bulk_tag(region: str, tags: dict[str, str]) -> int:
    ec2 = boto3.client("ec2", region_name=region)
    ids = (i["InstanceId"]
           for page in ec2.get_paginator("describe_instances").paginate()
           for r in page["Reservations"]
           for i in r["Instances"])
    n = 0
    for batch in chunk(ids, 1000):
        ec2.create_tags(Resources=batch,
                        Tags=[{"Key": k, "Value": v} for k, v in tags.items()])
        n += len(batch)
    return n
```

**Dense one-liner:** chunk into 1000s, single `create_tags` per chunk.

**Complexity:** O(N / 1000) API calls.  **Gotcha:** `create_tags` is idempotent for identical (key,value); replacing a different value for the same key just overwrites.

---

### Q.008 Find every public S3 bucket in the account.

Real-world security task. Tests `get_bucket_acl`, `get_public_access_block`, `get_bucket_policy_status` knowledge.

```python
import json
import boto3
from typing import Iterator

def public_buckets() -> Iterator[tuple[str, str]]:
    s3 = boto3.client("s3")
    for b in s3.list_buckets()["Buckets"]:
        name = b["Name"]
        try:
            blk = s3.get_public_access_block(Bucket=name)["PublicAccessBlockConfiguration"]
            if all(blk.values()):
                continue
        except s3.exceptions.from_code("NoSuchPublicAccessBlockConfiguration"):
            pass
        try:
            if s3.get_bucket_policy_status(Bucket=name)["PolicyStatus"]["IsPublic"]:
                yield name, "policy"
                continue
        except s3.exceptions.from_code("NoSuchBucketPolicy"):
            pass
        for grant in s3.get_bucket_acl(Bucket=name)["Grants"]:
            uri = grant.get("Grantee", {}).get("URI", "")
            if "AllUsers" in uri or "AuthenticatedUsers" in uri:
                yield name, "acl"; break
```

**Dense one-liner:** check `PublicAccessBlock` first; then `BucketPolicyStatus.IsPublic`; then ACL grants for `AllUsers`/`AuthenticatedUsers`.

**Complexity:** O(B) buckets × 3 API calls.  **Gotcha:** Account-level `PublicAccessBlock` overrides per-bucket; check `s3control.get_public_access_block(AccountId=...)` first to short-circuit.

---

### Q.009 Send a message to SQS with a custom dedup ID and visibility timeout.

Tests FIFO vs Standard knowledge. FIFO requires `MessageGroupId`; standard ignores it.

```python
import json
import hashlib
import boto3

def send_dedup(queue_url: str, body: dict, group: str = "default") -> str:
    payload = json.dumps(body, sort_keys=True)
    dedup_id = hashlib.sha256(payload.encode()).hexdigest()
    return boto3.client("sqs").send_message(
        QueueUrl=queue_url,
        MessageBody=payload,
        MessageGroupId=group,
        MessageDeduplicationId=dedup_id,
    )["MessageId"]
```

**Dense one-liner:** `MessageDeduplicationId = sha256(body)` for content-based dedup.

**Complexity:** O(1).  **Gotcha:** Dedup window is **5 minutes** — re-sending the same content after 5 min creates a new message.

---

### Q.010 Long-poll an SQS queue and process messages in parallel, deleting on success.

Classic worker pattern. Interviewers look for `WaitTimeSeconds`, batch delete, and partial-failure handling.

```python
import json
import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

def consume(queue_url: str, handler: Callable[[dict], None], workers: int = 8) -> None:
    sqs = boto3.client("sqs")
    while True:
        resp = sqs.receive_message(
            QueueUrl=queue_url, MaxNumberOfMessages=10,
            WaitTimeSeconds=20, VisibilityTimeout=60,
        )
        msgs = resp.get("Messages", [])
        if not msgs:
            continue
        ok: list[dict] = []
        with ThreadPoolExecutor(workers) as ex:
            futs = {ex.submit(handler, json.loads(m["Body"])): m for m in msgs}
            for f in as_completed(futs):
                if not f.exception():
                    ok.append(futs[f])
        if ok:
            sqs.delete_message_batch(QueueUrl=queue_url, Entries=[
                {"Id": str(i), "ReceiptHandle": m["ReceiptHandle"]} for i, m in enumerate(ok)
            ])
```

**Dense one-liner:** long-poll (`WaitTimeSeconds=20`) + `delete_message_batch` only for successes.

**Complexity:** O(M) per poll.  **Gotcha:** If your handler takes > `VisibilityTimeout`, message becomes visible and gets re-processed. Use `change_message_visibility` heartbeat for long jobs.

---

### Q.011 Atomic DynamoDB counter increment with a conditional cap.

Tests `UpdateExpression` + `ConditionExpression`. Common bug: read-modify-write race instead of `ADD`.

```python
import boto3
from botocore.exceptions import ClientError

def inc_capped(table: str, pk: str, cap: int = 100) -> int | None:
    ddb = boto3.client("dynamodb")
    try:
        r = ddb.update_item(
            TableName=table,
            Key={"pk": {"S": pk}},
            UpdateExpression="ADD cnt :one",
            ConditionExpression="attribute_not_exists(cnt) OR cnt < :cap",
            ExpressionAttributeValues={":one": {"N": "1"}, ":cap": {"N": str(cap)}},
            ReturnValues="UPDATED_NEW",
        )
        return int(r["Attributes"]["cnt"]["N"])
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return None
        raise
```

**Dense one-liner:** `UpdateExpression="ADD cnt :1", ConditionExpression="cnt < :cap"`.

**Complexity:** O(1) DynamoDB op.  **Gotcha:** `ADD` only works on numeric / set attributes; on string you'd use `SET cnt = if_not_exists(cnt, :zero) + :one`.

---

### Q.012 DynamoDB GetItem vs Query vs Scan — pick code for each use case.

Tests whether you reach for `Scan`. Almost never the right answer in prod.

```python
import boto3
ddb = boto3.client("dynamodb")

# (a) Single item by PK+SK
def get_user_post(uid: str, post_id: str) -> dict:
    return ddb.get_item(TableName="posts",
                        Key={"uid": {"S": uid}, "post_id": {"S": post_id}}).get("Item", {})

# (b) All posts by one user, newest first
def user_posts(uid: str, limit: int = 20) -> list[dict]:
    return ddb.query(TableName="posts",
                     KeyConditionExpression="uid = :u",
                     ExpressionAttributeValues={":u": {"S": uid}},
                     ScanIndexForward=False, Limit=limit)["Items"]

# (c) Find all posts with `flagged=true` (no GSI) — last resort.
def flagged() -> list[dict]:
    items: list[dict] = []
    for page in ddb.get_paginator("scan").paginate(
        TableName="posts",
        FilterExpression="flagged = :t",
        ExpressionAttributeValues={":t": {"BOOL": True}},
    ):
        items += page["Items"]
    return items
```

**Dense rule:** GetItem when you have full key, Query when you have PK, Scan only with a GSI as proper PK or for one-off audits.

**Complexity:** Get O(1), Query O(matched), Scan O(table).  **Gotcha:** `FilterExpression` runs **after** the read; you still pay RCU for everything scanned.

---

### Q.013 Read a secret from Secrets Manager with caching to avoid throttling.

Real production pattern. Without cache, a hot path burns SM rate limits and hits unpredictable latency.

```python
import json
import time
import boto3
from typing import Any

class SecretCache:
    def __init__(self, ttl: int = 300) -> None:
        self.ttl = ttl
        self.sm = boto3.client("secretsmanager")
        self._cache: dict[str, tuple[float, Any]] = {}

    def get(self, name: str) -> Any:
        now = time.time()
        if name in self._cache:
            ts, val = self._cache[name]
            if now - ts < self.ttl:
                return val
        raw = self.sm.get_secret_value(SecretId=name)["SecretString"]
        try:
            val = json.loads(raw)
        except json.JSONDecodeError:
            val = raw
        self._cache[name] = (now, val)
        return val
```

**Dense one-liner:** wrap `get_secret_value` with `(name, ts)` TTL cache (300 s default).

**Complexity:** O(1) cached, O(SM call) on miss.  **Gotcha:** AWS publishes the official `aws-secretsmanager-caching-python` library — use it instead of rolling your own in prod.

---

### Q.014 Pre-signed S3 URL that expires in 15 minutes for a download.

Common interview ask. The trap: people use `generate_presigned_post` (for uploads) when they want a download.

```python
import boto3

def download_url(bucket: str, key: str, expires: int = 900) -> str:
    return boto3.client("s3").generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )

def upload_url(bucket: str, key: str, expires: int = 900) -> dict:
    return boto3.client("s3").generate_presigned_post(
        Bucket=bucket, Key=key, ExpiresIn=expires,
        Conditions=[["content-length-range", 0, 10 * 1024 * 1024]],
    )
```

**Dense one-liner:** `generate_presigned_url("get_object", Params={...}, ExpiresIn=900)`.

**Complexity:** O(1).  **Gotcha:** Max URL lifetime is **7 days** for SigV4 with credentials, but only as long as the **role/user** lives if from STS.

---

### Q.015 Use `botocore` to inject a custom User-Agent for traceability.

Useful for distinguishing scripts from console traffic in CloudTrail. Interviewers love this for ops hygiene.

```python
import boto3
from botocore.config import Config

def client(service: str, tag: str) -> Any:
    cfg = Config(user_agent_extra=f"sre-tool/{tag}")
    return boto3.client(service, config=cfg)

# CloudTrail: userAgent="aws-sdk-python/... sre-tool/fsre-20-bootstrap"
```

**Dense one-liner:** `Config(user_agent_extra="sre-tool/fsre-20")`.

**Complexity:** N/A.  **Gotcha:** Don't put PII / secrets in the UA — it goes in CloudTrail logs.

---

### Q.016 Write a paginator that yields a flat stream of items from any list-* API.

Generic helper that interviewers love because it's reusable across services.

```python
import boto3
from typing import Iterator, Any

def paginate(service: str, op: str, key: str, region: str | None = None, **kw: Any) -> Iterator[Any]:
    client = boto3.client(service, region_name=region)
    paginator = client.get_paginator(op)
    for page in paginator.paginate(**kw):
        yield from page.get(key, [])

# Usage:
# for obj in paginate("s3", "list_objects_v2", "Contents", Bucket="b"): ...
# for fn  in paginate("lambda", "list_functions", "Functions"): ...
```

**Dense one-liner:** `(item for page in client.get_paginator(op).paginate(**kw) for item in page[key])`.

**Complexity:** O(N) items, O(N/PageSize) calls.  **Gotcha:** Some APIs need `PaginationConfig={"PageSize": 100}` to avoid the default 50.

---

### Q.017 Detect IAM access-key rotation drift (any key > 90 days old).

Compliance-style script that's a real audit ask.

```python
import boto3
from datetime import datetime, timezone, timedelta
from typing import Iterator

def stale_keys(max_age_days: int = 90) -> Iterator[tuple[str, str, int]]:
    iam = boto3.client("iam")
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    for page in iam.get_paginator("list_users").paginate():
        for u in page["Users"]:
            for k in iam.list_access_keys(UserName=u["UserName"])["AccessKeyMetadata"]:
                if k["Status"] == "Active" and k["CreateDate"] < cutoff:
                    age = (datetime.now(timezone.utc) - k["CreateDate"]).days
                    yield u["UserName"], k["AccessKeyId"], age
```

**Dense one-liner:** filter `list_access_keys` by `CreateDate < now - 90d` and `Status == "Active"`.

**Complexity:** O(U × K).  **Gotcha:** `LastUsedDate` comes from `get_access_key_last_used`, not `list_access_keys`.

---

### Q.018 Stream CloudWatch Logs in real time using `start_live_tail`.

Newer (2023+) API replacing the polling loop. Interviewers up-to-date with AWS will ask.

```python
import boto3

def tail(group_arn: str) -> None:
    logs = boto3.client("logs")
    resp = logs.start_live_tail(logGroupIdentifiers=[group_arn])
    for ev in resp["responseStream"]:
        if "sessionUpdate" in ev:
            for r in ev["sessionUpdate"].get("sessionResults", []):
                print(r["timestamp"], r["message"])
```

**Dense one-liner:** `for ev in logs.start_live_tail(logGroupIdentifiers=[arn])["responseStream"]: ...`

**Complexity:** Streaming.  **Gotcha:** Live tail has a **3-hour session limit** and is rate-capped at 500 events/s per log group.

---

### Q.019 KMS — generate a data key, encrypt locally, store ciphertext + wrapped key.

Envelope encryption. Interviewers test whether you understand why we don't `kms.encrypt(plaintext)` on big data (slow, rate-limited).

```python
import os
import boto3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def encrypt_envelope(kms_key_id: str, plaintext: bytes) -> tuple[bytes, bytes]:
    kms = boto3.client("kms")
    dek = kms.generate_data_key(KeyId=kms_key_id, KeySpec="AES_256")
    nonce = os.urandom(12)
    ct = AESGCM(dek["Plaintext"]).encrypt(nonce, plaintext, None)
    return dek["CiphertextBlob"], nonce + ct  # store wrapped DEK + (nonce|ct)

def decrypt_envelope(wrapped_dek: bytes, blob: bytes) -> bytes:
    plaintext_dek = boto3.client("kms").decrypt(CiphertextBlob=wrapped_dek)["Plaintext"]
    nonce, ct = blob[:12], blob[12:]
    return AESGCM(plaintext_dek).decrypt(nonce, ct, None)
```

**Dense rule:** KMS protects the **DEK**, AES-GCM encrypts the **data**.

**Complexity:** O(n) bytes for AES, O(1) KMS calls.  **Gotcha:** Always wipe the plaintext DEK from memory after use (`del`, plus `bytearray` zeroisation if paranoid).

---

### Q.020 Lambda invoker that handles 256 KB payload limit by spilling to S3.

Real production pattern. Lambda's sync invoke caps at 6 MB request / 6 MB response (256 KB for `RequestResponse`-style limit historically; current limit is 6 MB sync, 256 KB async). The trick is graceful spill.

```python
import json
import uuid
import boto3

def invoke(fn_name: str, payload: dict, spill_bucket: str) -> dict:
    body = json.dumps(payload)
    if len(body) < 200_000:
        r = boto3.client("lambda").invoke(FunctionName=fn_name, Payload=body)
        return json.loads(r["Payload"].read())
    key = f"spill/{uuid.uuid4()}.json"
    boto3.client("s3").put_object(Bucket=spill_bucket, Key=key, Body=body)
    r = boto3.client("lambda").invoke(
        FunctionName=fn_name,
        Payload=json.dumps({"_spill": {"bucket": spill_bucket, "key": key}}),
    )
    return json.loads(r["Payload"].read())
```

**Dense rule:** if payload > threshold, put to S3, pass `{bucket, key}` to Lambda.

**Complexity:** N/A.  **Gotcha:** Clean up spilled S3 objects with a lifecycle policy or you'll leak.

---

### Q.021 SSM Parameter Store batch fetch with decryption.

Cleaner than N `get_parameter` calls. Interviewers look for `get_parameters` (batch of 10) and `get_parameters_by_path`.

```python
import boto3
from itertools import islice
from typing import Iterable, Iterator

def chunks(it: Iterable, n: int) -> Iterator[list]:
    it = iter(it)
    while batch := list(islice(it, n)):
        yield batch

def fetch_params(names: list[str]) -> dict[str, str]:
    ssm = boto3.client("ssm")
    out: dict[str, str] = {}
    for batch in chunks(names, 10):
        r = ssm.get_parameters(Names=batch, WithDecryption=True)
        out.update({p["Name"]: p["Value"] for p in r["Parameters"]})
    return out

def fetch_path(prefix: str) -> dict[str, str]:
    ssm = boto3.client("ssm")
    out: dict[str, str] = {}
    for page in ssm.get_paginator("get_parameters_by_path").paginate(
        Path=prefix, Recursive=True, WithDecryption=True,
    ):
        out.update({p["Name"]: p["Value"] for p in page["Parameters"]})
    return out
```

**Dense one-liner:** `get_parameters(Names=batch, WithDecryption=True)` in chunks of 10.

**Complexity:** O(N/10) calls.  **Gotcha:** `get_parameters` silently omits names that don't exist — check `InvalidParameters` in the response.

---

### Q.022 Handle EC2 spot interruption signal in a Python worker.

Tests IMDSv2 token usage and graceful drain.

```python
import time
import json
import urllib.request
import urllib.error
import threading

def imds_token() -> str:
    req = urllib.request.Request(
        "http://169.254.169.254/latest/api/token", method="PUT",
        headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
    )
    return urllib.request.urlopen(req, timeout=2).read().decode()

def watch_interruption(on_warn) -> None:
    token = imds_token()
    headers = {"X-aws-ec2-metadata-token": token}
    url = "http://169.254.169.254/latest/meta-data/spot/instance-action"
    while True:
        try:
            req = urllib.request.Request(url, headers=headers)
            data = json.loads(urllib.request.urlopen(req, timeout=2).read())
            on_warn(data)  # has `action` and `time`
            return
        except urllib.error.HTTPError as e:
            if e.code == 404:
                time.sleep(5); continue
            raise

threading.Thread(target=watch_interruption, args=(lambda d: print("DRAIN", d),), daemon=True).start()
```

**Dense rule:** poll `/spot/instance-action` (404 = no warning, 200 = drain in 2 min).

**Complexity:** O(1) per poll.  **Gotcha:** Poll interval should be < 5 s to leave usable drain time.

---

### Q.023 Tag-based EC2 selector that returns running instances by environment.

Tests `Filters` syntax — interviewers see candidates fetch all instances and filter in Python (slow, hits API limits).

```python
import boto3
from typing import Iterator

def running_in_env(env: str, region: str) -> Iterator[str]:
    ec2 = boto3.client("ec2", region_name=region)
    for page in ec2.get_paginator("describe_instances").paginate(
        Filters=[
            {"Name": "instance-state-name", "Values": ["running"]},
            {"Name": "tag:Environment", "Values": [env]},
        ],
    ):
        for r in page["Reservations"]:
            for i in r["Instances"]:
                yield i["InstanceId"]
```

**Dense one-liner:** push filters into the API: `Filters=[{"Name": "tag:Environment", "Values": [env]}]`.

**Complexity:** O(matching instances) over the wire.  **Gotcha:** `tag:Key` is case-sensitive; `Environment` ≠ `environment`.

---

### Q.024 Detect EKS cluster auth mode (aws-auth vs API entries).

Newer clusters can run dual-mode. Tests EKS API knowledge.

```python
import boto3

def auth_mode(cluster: str, region: str) -> str:
    eks = boto3.client("eks", region_name=region)
    c = eks.describe_cluster(name=cluster)["cluster"]
    return c.get("accessConfig", {}).get("authenticationMode", "CONFIG_MAP")
    # CONFIG_MAP | API | API_AND_CONFIG_MAP
```

**Dense one-liner:** `eks.describe_cluster(name=c)["cluster"]["accessConfig"]["authenticationMode"]`.

**Complexity:** O(1).  **Gotcha:** Old clusters have no `accessConfig` block — default to `CONFIG_MAP`.

---

### Q.025 List all running Lambda functions in an account with their memory + timeout.

```python
import boto3
import csv
import sys
from typing import Iterator

def lambdas(region: str) -> Iterator[dict]:
    lam = boto3.client("lambda", region_name=region)
    for page in lam.get_paginator("list_functions").paginate():
        yield from page["Functions"]

def report(region: str) -> None:
    w = csv.writer(sys.stdout)
    w.writerow(["FunctionName", "Runtime", "MemorySize", "Timeout", "LastModified"])
    for f in lambdas(region):
        w.writerow([f["FunctionName"], f["Runtime"], f["MemorySize"], f["Timeout"], f["LastModified"]])
```

**Dense one-liner:** `csv.writer(sys.stdout).writerows([...for f in paginator.paginate()...])`.

**Complexity:** O(F) functions.  **Gotcha:** `list_functions` returns config; for code size or env vars use `get_function_configuration`.

---

## Track A.2 — Kubernetes Python Client (Q.026–Q.040)

> Companies: Google, Amazon, Red Hat, Datadog, Snowflake, Stripe, Lyft, Airbnb. Focus: load-config patterns, watch/list, server-side apply, custom resources, exec/portforward, controllers, RBAC errors.

### Q.026 — Load kubeconfig in-cluster vs. out-of-cluster
**Companies:** Google, Red Hat, Datadog.

**Prose:** Production controllers run in-cluster (service-account token at `/var/run/secrets/...`); local debug uses `~/.kube/config`. Try in-cluster first, fall back, never both — silent context drift is a common P1.

```python
from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException

def load() -> client.CoreV1Api:
    try:
        config.load_incluster_config()
    except ConfigException:
        config.load_kube_config()
    return client.CoreV1Api()
```

**Dense one-liner:** `(config.load_incluster_config if os.getenv("KUBERNETES_SERVICE_HOST") else config.load_kube_config)()`.

**Complexity:** O(1).  **Gotcha:** `load_kube_config()` honours `$KUBECONFIG` and `current-context`; CI runners often inherit a stale context — always log `config.list_kube_config_contexts()[1]["name"]`.

---

### Q.027 — List pods across all namespaces with field/label selectors
**Companies:** Amazon, Datadog, Lyft.

**Prose:** Use `list_pod_for_all_namespaces` with `label_selector` and `field_selector` server-side; never filter client-side at scale (10k+ pods OOMs the controller).

```python
from kubernetes import client

def failing_pods(v1: client.CoreV1Api) -> list[str]:
    resp = v1.list_pod_for_all_namespaces(
        label_selector="app.kubernetes.io/managed-by=Helm",
        field_selector="status.phase!=Running",
    )
    return [f"{p.metadata.namespace}/{p.metadata.name}" for p in resp.items]
```

**Dense one-liner:** `[f"{p.metadata.namespace}/{p.metadata.name}" for p in v1.list_pod_for_all_namespaces(field_selector="status.phase!=Running").items]`.

**Complexity:** O(P) returned pods.  **Gotcha:** `field_selector` supports only a tiny whitelist (`metadata.name`, `metadata.namespace`, `status.phase`, `spec.nodeName`); arbitrary fields raise 400.

---

### Q.028 — Stream events with watch and resourceVersion
**Companies:** Red Hat, Google, Stripe.

**Prose:** `watch.Watch().stream(...)` returns a generator of `ADDED/MODIFIED/DELETED` events. Always capture `resource_version` so reconnects resume without missing/replaying — the bookmark pattern.

```python
from kubernetes import client, watch

def follow(v1: client.CoreV1Api, ns: str) -> None:
    rv = ""
    w = watch.Watch()
    while True:
        for ev in w.stream(v1.list_namespaced_pod, namespace=ns, resource_version=rv, timeout_seconds=300):
            rv = ev["object"].metadata.resource_version
            print(ev["type"], ev["object"].metadata.name)
```

**Dense one-liner:** `for ev in watch.Watch().stream(v1.list_namespaced_pod, namespace=ns): print(ev["type"], ev["object"].metadata.name)`.

**Complexity:** O(E) events.  **Gotcha:** apiserver expires watches after ~5 min; on 410 Gone you must relist (drop `rv`) — silent skip = lost reconciliation.

---

### Q.029 — Server-side apply (SSA) with field manager
**Companies:** Google, Red Hat.

**Prose:** SSA (`PATCH` with `Content-Type: application/apply-patch+yaml`) lets multiple controllers co-own a resource via `fieldManager` ownership. Replaces the brittle "get-modify-put" + resourceVersion conflict loop.

```python
from kubernetes import client
from kubernetes.client.rest import ApiException

def ssa_configmap(v1: client.CoreV1Api, ns: str, name: str, data: dict[str, str]) -> None:
    body = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": name}, "data": data}
    v1.patch_namespaced_config_map(
        name=name, namespace=ns, body=body,
        field_manager="interview-agent", force=True,
        _content_type="application/apply-patch+yaml",
    )
```

**Dense one-liner:** `v1.patch_namespaced_config_map(name, ns, body, field_manager="x", _content_type="application/apply-patch+yaml")`.

**Complexity:** O(1) network.  **Gotcha:** without `force=True`, conflicts with another field manager raise 409 — kubectl uses `--force-conflicts` for the same reason.

---

### Q.030 — Read pod logs (single + multi-container, follow)
**Companies:** Datadog, Splunk, Lyft.

**Prose:** `read_namespaced_pod_log` returns a string; pass `_preload_content=False` to get a streaming `urllib3.HTTPResponse` for `follow=True`. Always set `container=` for multi-container pods or you get a 400.

```python
from kubernetes import client

def tail(v1: client.CoreV1Api, ns: str, pod: str, container: str) -> None:
    resp = v1.read_namespaced_pod_log(
        name=pod, namespace=ns, container=container,
        follow=True, _preload_content=False, tail_lines=100,
    )
    for line in resp.stream(amt=None, decode_content=True):
        print(line.decode(), end="")
```

**Dense one-liner:** `print(v1.read_namespaced_pod_log(pod, ns, container=c, tail_lines=100))`.

**Complexity:** O(L) lines.  **Gotcha:** logs are only available while the container exists on a node; after eviction use `previous=True` for the last terminated instance only.

---

### Q.031 — Exec into a pod (websocket stream)
**Companies:** Red Hat, Google, Stripe.

**Prose:** `kubernetes.stream.stream` upgrades to a websocket. Returns interleaved stdout/stderr; capture both, set `_preload_content=False` for interactive sessions.

```python
from kubernetes import client
from kubernetes.stream import stream

def run(v1: client.CoreV1Api, ns: str, pod: str, cmd: list[str]) -> tuple[str, str]:
    resp = stream(
        v1.connect_get_namespaced_pod_exec, pod, ns,
        command=cmd, stderr=True, stdin=False, stdout=True, tty=False,
        _preload_content=False,
    )
    out, err = [], []
    while resp.is_open():
        resp.update(timeout=1)
        if resp.peek_stdout(): out.append(resp.read_stdout())
        if resp.peek_stderr(): err.append(resp.read_stderr())
    return "".join(out), "".join(err)
```

**Dense one-liner:** `stream(v1.connect_get_namespaced_pod_exec, pod, ns, command=["sh","-c",cmd], stderr=True, stdout=True)`.

**Complexity:** O(O) output bytes.  **Gotcha:** `command` must be a list (`["sh","-c","echo $X"]`), never a string — passing string runs `/string` literally.

---

### Q.032 — Port-forward from Python
**Companies:** Stripe, Datadog.

**Prose:** `portforward()` returns a multiplexed socket per port; wrap in `socket.socket`-compatible API. Useful for ephemeral admin tasks (e.g., scrape Prom in a private cluster) without a bastion.

```python
import socket
from kubernetes import client
from kubernetes.stream import portforward

def fetch_metrics(v1: client.CoreV1Api, ns: str, pod: str) -> bytes:
    pf = portforward(v1.connect_get_namespaced_pod_portforward, pod, ns, ports="9090")
    sock: socket.socket = pf.socket(9090)
    sock.sendall(b"GET /metrics HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
    chunks = []
    while data := sock.recv(4096):
        chunks.append(data)
    return b"".join(chunks)
```

**Dense one-liner:** `portforward(v1.connect_get_namespaced_pod_portforward, pod, ns, ports="9090").socket(9090)`.

**Complexity:** O(B) bytes.  **Gotcha:** port-forward keeps the apiserver socket open — under network blips you must reconnect; not suitable for long-lived prod traffic.

---

### Q.033 — Custom Resource (CRD) CRUD via dynamic client
**Companies:** Red Hat, Google, Snowflake.

**Prose:** `dynamic.DynamicClient` resolves GVRs at runtime — works for any CRD without generated stubs. Used by ArgoCD/Flux-style tooling.

```python
from kubernetes import client, config, dynamic

def get_apps() -> list[str]:
    config.load_kube_config()
    dyn = dynamic.DynamicClient(client.api_client.ApiClient())
    api = dyn.resources.get(api_version="argoproj.io/v1alpha1", kind="Application")
    return [a.metadata.name for a in api.get(namespace="argocd").items]
```

**Dense one-liner:** `dynamic.DynamicClient(ApiClient()).resources.get(api_version="argoproj.io/v1alpha1", kind="Application").get(namespace="argocd")`.

**Complexity:** O(R) resources.  **Gotcha:** `resources.get()` raises `ResourceNotFoundError` if the CRD isn't installed — wrap in try/except and surface a useful message, not a stacktrace.

---

### Q.034 — Create a Job and wait for completion
**Companies:** Amazon, Lyft, Stripe.

**Prose:** Submit a `batch/v1` Job, then poll `status.succeeded`/`status.failed`. Real controllers use a watch + informer instead of poll, but interviews accept poll with backoff.

```python
import time
from kubernetes import client

def run_job(batch: client.BatchV1Api, ns: str, body: dict, timeout: int = 600) -> bool:
    name = body["metadata"]["name"]
    batch.create_namespaced_job(namespace=ns, body=body)
    deadline = time.time() + timeout
    while time.time() < deadline:
        j = batch.read_namespaced_job_status(name=name, namespace=ns)
        if j.status.succeeded: return True
        if j.status.failed:    return False
        time.sleep(5)
    raise TimeoutError(name)
```

**Dense one-liner:** `batch.read_namespaced_job_status(name, ns).status.succeeded == 1`.

**Complexity:** O(T/5) polls.  **Gotcha:** a Job with `backoffLimit>0` may show `succeeded=None` while retrying — check `failed >= backoffLimit` for terminal failure.

---

### Q.035 — Build a minimal controller with informers (kopf or shared informer)
**Companies:** Red Hat, Google, Snowflake.

**Prose:** Production controllers use an informer (cached list+watch with delta queue), not raw watches. `kopf` is the Pythonic shortcut; under the hood it's the same list-watch-resync loop as client-go.

```python
import kopf

@kopf.on.create("example.com", "v1", "widgets")
def created(spec: dict, name: str, namespace: str, logger, **_) -> dict:
    logger.info(f"widget {namespace}/{name} created with spec={spec}")
    return {"status": {"phase": "Ready"}}
```

**Dense one-liner:** `@kopf.on.create("g","v","kind")` decorator handler.

**Complexity:** O(R) resync.  **Gotcha:** handlers must be **idempotent** — kopf re-invokes on operator restart and resync (default 10 min); side effects without a marker = duplicate work.

---

### Q.036 — Decode a Secret safely
**Companies:** Stripe, Datadog, Snowflake.

**Prose:** `data` values are base64; `stringData` is convenience-only on write. Never log decoded values; redact in error paths.

```python
import base64
from kubernetes import client

def get_secret(v1: client.CoreV1Api, ns: str, name: str, key: str) -> str:
    s = v1.read_namespaced_secret(name=name, namespace=ns)
    raw = s.data.get(key)
    if raw is None:
        raise KeyError(f"{key} not in secret {ns}/{name}")
    return base64.b64decode(raw).decode()
```

**Dense one-liner:** `base64.b64decode(v1.read_namespaced_secret(n, ns).data[k]).decode()`.

**Complexity:** O(B) bytes.  **Gotcha:** `data` is `None` (not `{}`) on an empty Secret — `s.data or {}` before `.get()`.

---

### Q.037 — Handle ApiException with status codes
**Companies:** Google, Red Hat, Amazon.

**Prose:** Every k8s call can raise `ApiException`; map `e.status` → action: 404 → create, 409 → conflict-retry, 410 → relist, 429 → backoff with jittered sleep, 5xx → exponential retry.

```python
import random, time
from kubernetes.client.rest import ApiException

def retry_get(fn, attempts: int = 5):
    for i in range(attempts):
        try:
            return fn()
        except ApiException as e:
            if e.status in (429, 500, 502, 503, 504):
                time.sleep(min(30, 2**i + random.random()))
                continue
            raise
    raise RuntimeError("exhausted retries")
```

**Dense one-liner:** `time.sleep(2**i + random.random()) if e.status in {429,500,502,503,504} else raise`.

**Complexity:** O(A) attempts.  **Gotcha:** apiserver returns `Retry-After` header on 429 — honour it instead of fixed backoff to avoid stampede.

---

### Q.038 — Drain a node (cordon + evict pods)
**Companies:** Lyft, Stripe, Airbnb.

**Prose:** `kubectl drain` is two API calls: `PATCH` node `spec.unschedulable=true`, then `POST` Eviction subresource per pod. Eviction respects PDBs; raw delete does not.

```python
from kubernetes import client

def drain(v1: client.CoreV1Api, node: str) -> None:
    v1.patch_node(node, {"spec": {"unschedulable": True}})
    pods = v1.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={node}").items
    for p in pods:
        body = client.V1Eviction(metadata=client.V1ObjectMeta(name=p.metadata.name, namespace=p.metadata.namespace))
        v1.create_namespaced_pod_eviction(name=p.metadata.name, namespace=p.metadata.namespace, body=body)
```

**Dense one-liner:** `v1.create_namespaced_pod_eviction(p.metadata.name, p.metadata.namespace, body=V1Eviction(...))`.

**Complexity:** O(P) pods on node.  **Gotcha:** Eviction returns 429 when a PDB would be violated — drain loop must retry, not skip; otherwise node sits half-drained forever.

---

### Q.039 — Resolve a Pod's IRSA / Pod Identity ServiceAccount
**Companies:** Amazon, Snowflake, Stripe.

**Prose:** From inside a pod, the projected SA token is at `/var/run/secrets/kubernetes.io/serviceaccount/token`; the SA's `eks.amazonaws.com/role-arn` annotation tells you the assumed role. Useful for diagnosing "AccessDenied: not authorized to perform sts:AssumeRoleWithWebIdentity".

```python
from kubernetes import client, config

def role_arn_for(ns: str, sa_name: str) -> str | None:
    config.load_kube_config()
    sa = client.CoreV1Api().read_namespaced_service_account(sa_name, ns)
    return (sa.metadata.annotations or {}).get("eks.amazonaws.com/role-arn")
```

**Dense one-liner:** `(sa.metadata.annotations or {}).get("eks.amazonaws.com/role-arn")`.

**Complexity:** O(1).  **Gotcha:** Pod Identity (newer) does **not** use this annotation — it uses a `PodIdentityAssociation` CR in EKS; absence of annotation ≠ no IAM.

---

### Q.040 — Diff two ConfigMaps across clusters (FSRE-20 pattern)
**Companies:** Amazon, Cisco, Stripe — and exactly the FSRE-20 cluster-compare task.

**Prose:** Load both ConfigMaps from two kubeconfig contexts, normalise YAML/JSON values, emit a unified diff. Caller decides drift policy.

```python
import difflib, json
from kubernetes import client, config

def cm_data(context: str, ns: str, name: str) -> dict[str, str]:
    config.load_kube_config(context=context)
    return client.CoreV1Api().read_namespaced_config_map(name, ns).data or {}

def diff_cm(ctx_a: str, ctx_b: str, ns: str, name: str) -> str:
    a = json.dumps(cm_data(ctx_a, ns, name), indent=2, sort_keys=True).splitlines()
    b = json.dumps(cm_data(ctx_b, ns, name), indent=2, sort_keys=True).splitlines()
    return "\n".join(difflib.unified_diff(a, b, fromfile=ctx_a, tofile=ctx_b, lineterm=""))
```

**Dense one-liner:** `difflib.unified_diff(json.dumps(a,sort_keys=True).split(), json.dumps(b,sort_keys=True).split())`.

**Complexity:** O(N) keys.  **Gotcha:** values like `kube-proxy`'s embedded YAML need a second-level YAML parse before diffing — string diff alone shows whitespace noise.

---

## Track A.3 — Concurrency, asyncio, GIL (Q.041–Q.060)

> Companies: Google, Meta, Stripe, Cloudflare, Datadog, Lyft, Uber. Focus: GIL semantics, threads vs. processes, asyncio fundamentals, structured concurrency, cancellation, semaphores, queues, race conditions.

### Q.041 — Explain the GIL: what it protects, what it doesn't
**Companies:** Google, Meta, Cloudflare.

**Prose:** The GIL serialises bytecode execution per interpreter — only one thread runs Python at a time. It protects CPython's refcount and dict mutations from torn writes, but it does **not** make your code thread-safe (compound operations like `d[k] += 1` are still racy across the bytecode boundary).

```python
import threading
counter = 0
def bump() -> None:
    global counter
    for _ in range(100_000):
        counter += 1  # NOT atomic: LOAD, ADD, STORE
ts = [threading.Thread(target=bump) for _ in range(8)]
for t in ts: t.start()
for t in ts: t.join()
print(counter)  # almost never 800_000
```

**Dense one-liner:** `with lock: counter += 1` (or use `itertools.count()` whose `__next__` is atomic).

**Complexity:** O(N) ops.  **Gotcha:** PEP 703 (free-threaded CPython 3.13t) removes the GIL — code that relied on "atomic-ish" dict ops will break; always use explicit locks.

---

### Q.042 — When to use threads vs. processes vs. asyncio
**Companies:** Stripe, Datadog, Uber.

**Prose:** Threads → I/O-bound with blocking libs (boto3, requests). Processes → CPU-bound (numpy-less hashing, parsing). asyncio → high-concurrency I/O with native async libs (aiohttp, asyncpg). Mixing: run blocking calls in `asyncio.to_thread()`.

```python
import asyncio, hashlib
from concurrent.futures import ProcessPoolExecutor

async def main(paths: list[str]) -> list[str]:
    loop = asyncio.get_running_loop()
    with ProcessPoolExecutor() as pool:
        return await asyncio.gather(*(loop.run_in_executor(pool, hash_file, p) for p in paths))

def hash_file(p: str) -> str:
    return hashlib.sha256(open(p, "rb").read()).hexdigest()
```

**Dense one-liner:** `await asyncio.to_thread(blocking_fn, *args)`.

**Complexity:** depends on workload.  **Gotcha:** ProcessPool pickles args/results — large numpy arrays serialise slowly; use shared memory (`multiprocessing.shared_memory`) for >100 MB payloads.

---

### Q.043 — `asyncio.gather` vs. `asyncio.TaskGroup` (3.11+)
**Companies:** Meta, Cloudflare, Stripe.

**Prose:** `gather` returns results or first exception (others keep running unless `return_exceptions=True`). `TaskGroup` is structured concurrency — on any failure all siblings are cancelled and an `ExceptionGroup` is raised. Prefer TaskGroup in new code.

```python
import asyncio

async def fetch(i: int) -> int:
    await asyncio.sleep(0.1)
    if i == 3: raise ValueError(i)
    return i

async def main() -> list[int]:
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(fetch(i)) for i in range(5)]
    return [t.result() for t in tasks]
```

**Dense one-liner:** `async with asyncio.TaskGroup() as tg: [tg.create_task(f(i)) for i in xs]`.

**Complexity:** O(N) tasks.  **Gotcha:** `gather(*xs)` without `return_exceptions=True` leaks pending tasks on failure — they keep running and log "task was destroyed but pending" warnings.

---

### Q.044 — Bound concurrency with `asyncio.Semaphore`
**Companies:** Stripe, Cloudflare, Datadog.

**Prose:** Unbounded `gather(*[fetch(u) for u in urls])` over 10k URLs opens 10k sockets and DOSes the target. Semaphore caps in-flight work; the canonical fan-out pattern.

```python
import asyncio, aiohttp

async def fetch(sem: asyncio.Semaphore, sess: aiohttp.ClientSession, url: str) -> int:
    async with sem, sess.get(url) as r:
        return r.status

async def crawl(urls: list[str], limit: int = 50) -> list[int]:
    sem = asyncio.Semaphore(limit)
    async with aiohttp.ClientSession() as sess:
        return await asyncio.gather(*(fetch(sem, sess, u) for u in urls))
```

**Dense one-liner:** `async with sem: await fn()`.

**Complexity:** O(N) requests, ≤limit concurrent.  **Gotcha:** Semaphore alone doesn't rate-limit (req/sec); for that use a token bucket — concurrency cap and rate limit are different controls.

---

### Q.045 — Cancel an async task safely
**Companies:** Meta, Google.

**Prose:** `task.cancel()` injects `CancelledError` at the next `await`. Handlers should re-raise after cleanup; swallowing `CancelledError` breaks structured concurrency and TaskGroups.

```python
import asyncio

async def worker() -> None:
    try:
        await asyncio.sleep(60)
    except asyncio.CancelledError:
        # cleanup (close conn, flush buffer)
        raise  # re-raise!

async def main() -> None:
    t = asyncio.create_task(worker())
    await asyncio.sleep(0.1)
    t.cancel()
    try: await t
    except asyncio.CancelledError: pass
```

**Dense one-liner:** `t.cancel(); await asyncio.gather(t, return_exceptions=True)`.

**Complexity:** O(1).  **Gotcha:** in 3.8–3.10 `asyncio.CancelledError` inherits from `Exception`; in 3.8+ it inherits from `BaseException` — bare `except Exception` no longer catches it (correct behaviour, but surprising during upgrades).

---

### Q.046 — `asyncio.timeout()` vs. `wait_for`
**Companies:** Stripe, Cloudflare.

**Prose:** `asyncio.timeout()` (3.11+) is a context manager that cancels the inner block on expiry; cleaner than `wait_for` and composable with TaskGroup. `wait_for` wraps a single awaitable.

```python
import asyncio

async def call() -> str:
    async with asyncio.timeout(2.0):
        return await slow_io()

async def slow_io() -> str:
    await asyncio.sleep(5)
    return "ok"
```

**Dense one-liner:** `async with asyncio.timeout(2.0): await x()`.

**Complexity:** O(1).  **Gotcha:** `timeout()` raises `TimeoutError` (not `asyncio.TimeoutError` from 3.11) — alias the same class but old `except asyncio.TimeoutError` still works.

---

### Q.047 — Producer/consumer with `asyncio.Queue`
**Companies:** Datadog, Lyft, Uber.

**Prose:** Queue decouples producers from consumers; use `task_done()`/`join()` to wait for drain. Bounded `maxsize` provides backpressure — without it a slow consumer OOMs the process.

```python
import asyncio

async def producer(q: asyncio.Queue[int], n: int) -> None:
    for i in range(n):
        await q.put(i)

async def consumer(q: asyncio.Queue[int]) -> None:
    while True:
        i = await q.get()
        try: print(i)
        finally: q.task_done()

async def main() -> None:
    q: asyncio.Queue[int] = asyncio.Queue(maxsize=100)
    cs = [asyncio.create_task(consumer(q)) for _ in range(4)]
    await producer(q, 1000)
    await q.join()
    for c in cs: c.cancel()
```

**Dense one-liner:** `await q.put(item); await q.get(); q.task_done()`.

**Complexity:** O(N) items.  **Gotcha:** consumers must be cancelled after `q.join()` or the event loop hangs forever waiting on `q.get()`.

---

### Q.048 — Race a primary against a hedge request (`asyncio.wait FIRST_COMPLETED`)
**Companies:** Google, Cloudflare.

**Prose:** Hedging fires a backup request after a delay; whichever returns first wins, the other is cancelled. Cuts p99 latency dramatically for fan-out reads.

```python
import asyncio

async def primary() -> str: await asyncio.sleep(1.0); return "p"
async def hedge()   -> str: await asyncio.sleep(0.3); return "h"

async def race(delay: float = 0.2) -> str:
    p = asyncio.create_task(primary())
    await asyncio.sleep(delay)
    h = asyncio.create_task(hedge())
    done, pending = await asyncio.wait({p, h}, return_when=asyncio.FIRST_COMPLETED)
    for t in pending: t.cancel()
    return next(iter(done)).result()
```

**Dense one-liner:** `done,pending = await asyncio.wait(tasks, return_when=FIRST_COMPLETED)`.

**Complexity:** O(1).  **Gotcha:** hedging amplifies write side-effects — only safe for **idempotent reads**; never hedge a `POST /charge`.

---

### Q.049 — `run_in_executor` and the default executor pitfall
**Companies:** Stripe, Datadog.

**Prose:** `loop.run_in_executor(None, fn, *args)` uses a default `ThreadPoolExecutor(min(32, os.cpu_count()+4))`. Saturating it blocks unrelated tasks (e.g., DNS, file I/O) — provide your own pool for heavy work.

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

heavy = ThreadPoolExecutor(max_workers=16)

async def do(x: int) -> int:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(heavy, blocking_op, x)

def blocking_op(x: int) -> int:
    import time; time.sleep(0.1); return x*2
```

**Dense one-liner:** `await loop.run_in_executor(my_pool, fn, *args)`.

**Complexity:** O(N/W) workers.  **Gotcha:** `asyncio.to_thread()` (3.9+) also uses the default executor — same saturation risk; pass explicit executor for hot paths.

---

### Q.050 — Detect blocking calls in an async program
**Companies:** Meta, Cloudflare.

**Prose:** A sync `time.sleep`, `requests.get`, or CPU loop in a coroutine stalls the entire loop. Enable `asyncio.get_event_loop().set_debug(True)` or `PYTHONASYNCIODEBUG=1` — slow callbacks (>100 ms) get logged with stacktrace.

```python
import asyncio, time

async def bad() -> None:
    time.sleep(0.5)  # WRONG, blocks the loop

async def main() -> None:
    asyncio.get_running_loop().set_debug(True)
    await bad()
asyncio.run(main())
```

**Dense one-liner:** `loop.set_debug(True); loop.slow_callback_duration = 0.05`.

**Complexity:** O(1).  **Gotcha:** debug mode adds overhead — enable in staging/load-test, not always-on prod.

---

### Q.051 — Thread-safe singleton with `threading.Lock`
**Companies:** Amazon, Stripe.

**Prose:** Double-checked locking is the canonical pattern; the `if instance is None` check inside the lock prevents the race where two threads both observe `None`.

```python
import threading

class Cfg:
    _inst: "Cfg | None" = None
    _lock = threading.Lock()

    @classmethod
    def get(cls) -> "Cfg":
        if cls._inst is None:
            with cls._lock:
                if cls._inst is None:
                    cls._inst = cls()
        return cls._inst
```

**Dense one-liner:** module-level `cfg = Cfg()` (import is already serialised).

**Complexity:** O(1).  **Gotcha:** module-level init is the simpler answer in Python — imports hold the import lock, so a top-level singleton is implicitly thread-safe; reach for DCL only if init is expensive and conditional.

---

### Q.052 — Bound a thread pool and surface failures
**Companies:** Datadog, Uber.

**Prose:** `concurrent.futures.ThreadPoolExecutor` returns Futures; iterate `as_completed` to surface exceptions promptly. Without `as_completed`, exceptions hide until you call `.result()` on each in submission order.

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch(u: str) -> int: ...

def crawl(urls: list[str]) -> list[int]:
    out: list[int] = []
    with ThreadPoolExecutor(max_workers=20) as ex:
        futs = {ex.submit(fetch, u): u for u in urls}
        for f in as_completed(futs):
            try: out.append(f.result())
            except Exception as e:
                print(f"{futs[f]}: {e}")
    return out
```

**Dense one-liner:** `for f in as_completed(futs): f.result()`.

**Complexity:** O(N).  **Gotcha:** `executor.map(fn, iter)` returns results in input order — first failure raises and **drops** subsequent results; use `submit`+`as_completed` for resilience.

---

### Q.053 — Avoid deadlocks: lock ordering and timeouts
**Companies:** Google, Stripe.

**Prose:** Always acquire multiple locks in a fixed global order; or use `lock.acquire(timeout=...)` and back off on failure. Detection > prevention is rarely worth it in app code.

```python
import threading
a, b = threading.Lock(), threading.Lock()

def safe(x: int) -> None:
    first, second = (a, b) if id(a) < id(b) else (b, a)
    with first, second:
        ...
```

**Dense one-liner:** `with min(locks,key=id), max(locks,key=id): ...`.

**Complexity:** O(L) locks.  **Gotcha:** `RLock` allows the same thread to re-enter, but does **not** prevent deadlocks across threads — re-entrancy ≠ safety.

---

### Q.054 — Async context manager and async generator
**Companies:** Cloudflare, Datadog.

**Prose:** `__aenter__`/`__aexit__` for resources (DB sessions, HTTP clients). `async def` + `yield` for streaming results. Both compose with `async for` / `async with`.

```python
import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def session(url: str):
    print("open", url)
    try: yield {"url": url}
    finally: print("close")

async def main() -> None:
    async with session("x") as s:
        print(s)
asyncio.run(main())
```

**Dense one-liner:** `@asynccontextmanager async def cm(): yield resource`.

**Complexity:** O(1).  **Gotcha:** an async generator that's GC'd while paused logs "an unhandled exception during asyncgen close" — call `aclose()` explicitly or use `async with aclosing(gen)`.

---

### Q.055 — `multiprocessing.Pool` with imap_unordered for streaming results
**Companies:** Lyft, Uber, Snowflake.

**Prose:** `imap_unordered` yields results as workers finish, not in input order — first slow item doesn't block the rest. Use `chunksize` to amortise IPC overhead for short tasks.

```python
from multiprocessing import Pool

def work(x: int) -> int:
    return x*x

if __name__ == "__main__":
    with Pool(processes=8) as p:
        for r in p.imap_unordered(work, range(1000), chunksize=50):
            print(r)
```

**Dense one-liner:** `for r in pool.imap_unordered(fn, xs, chunksize=50): ...`.

**Complexity:** O(N/W).  **Gotcha:** `if __name__ == "__main__"` guard is **mandatory** on macOS/Windows (spawn) or workers re-import the script and fork-bomb.

---

### Q.056 — Share state across processes (Manager vs. shared_memory)
**Companies:** Snowflake, Lyft.

**Prose:** `Manager().dict()` proxies via IPC — slow, but works for arbitrary objects. `multiprocessing.shared_memory.SharedMemory` (3.8+) is zero-copy for bytes/numpy — use for big arrays.

```python
from multiprocessing import shared_memory
import numpy as np

shm = shared_memory.SharedMemory(create=True, size=8*1_000_000)
arr = np.ndarray((1_000_000,), dtype=np.int64, buffer=shm.buf)
arr[:] = np.arange(1_000_000)
# pass shm.name to children; they attach with SharedMemory(name=...)
shm.close(); shm.unlink()
```

**Dense one-liner:** `np.ndarray(shape, dtype, buffer=shared_memory.SharedMemory(name=n).buf)`.

**Complexity:** O(1) attach.  **Gotcha:** forget to `unlink()` and `/dev/shm` leaks across runs — wrap in try/finally or use `resource_tracker`.

---

### Q.057 — `contextvars` for request-scoped state in async
**Companies:** Stripe, Datadog.

**Prose:** `threading.local` doesn't work across `await` (different task = same thread). `contextvars.ContextVar` is the async-aware replacement; each task gets its own copy. Used by structlog, OpenTelemetry.

```python
import asyncio, contextvars

request_id: contextvars.ContextVar[str] = contextvars.ContextVar("rid", default="-")

async def handler(rid: str) -> None:
    request_id.set(rid)
    await asyncio.sleep(0.1)
    print(request_id.get())  # the right rid

async def main() -> None:
    await asyncio.gather(handler("A"), handler("B"))
```

**Dense one-liner:** `var = ContextVar("x"); var.set(v); var.get()`.

**Complexity:** O(1).  **Gotcha:** spawning a thread doesn't copy the context — pass `contextvars.copy_context()` and call `ctx.run(fn)` inside the thread.

---

### Q.058 — Detect and prevent thundering-herd cache stampede
**Companies:** Cloudflare, Stripe, Meta.

**Prose:** When a hot key expires, N requests miss simultaneously and all hit origin. Fix: single-flight (one async task per key, others await the same future) or probabilistic early refresh.

```python
import asyncio
from typing import Awaitable, Callable

_inflight: dict[str, asyncio.Task] = {}

async def single_flight(key: str, fn: Callable[[], Awaitable[str]]) -> str:
    if key not in _inflight:
        _inflight[key] = asyncio.create_task(fn())
        _inflight[key].add_done_callback(lambda _: _inflight.pop(key, None))
    return await _inflight[key]
```

**Dense one-liner:** `_inflight.setdefault(key, asyncio.create_task(fn()))`.

**Complexity:** O(1) per request.  **Gotcha:** `setdefault` evaluates `create_task(fn())` eagerly even if key exists — wrap in `if/else` to avoid leaking pending tasks.

---

### Q.059 — Backpressure with `asyncio.Queue` + bounded producers
**Companies:** Datadog, Lyft.

**Prose:** Bounded queue + `await q.put(...)` is the simplest backpressure mechanism — slow consumers naturally throttle producers. Combine with metrics (`q.qsize()`) to alert before saturation.

```python
import asyncio

async def produce(q: asyncio.Queue[int]) -> None:
    for i in range(10_000):
        await q.put(i)  # blocks when full

async def main() -> None:
    q: asyncio.Queue[int] = asyncio.Queue(maxsize=100)
    asyncio.create_task(produce(q))
    while True:
        item = await q.get()
        await asyncio.sleep(0.01)  # slow consumer
        q.task_done()
```

**Dense one-liner:** `asyncio.Queue(maxsize=N)` then `await q.put(x)`.

**Complexity:** O(N).  **Gotcha:** `q.put_nowait()` raises `QueueFull` instead of blocking — easy to drop data silently if you don't catch it.

---

### Q.060 — `asyncio.run` vs. `loop.run_until_complete` and Python 3.12 deprecation
**Companies:** Google, Meta.

**Prose:** `asyncio.run(coro)` creates a new loop, runs to completion, closes it — the only correct entry point for new code. `get_event_loop()` is deprecated outside a running loop in 3.12+.

```python
import asyncio

async def main() -> int:
    return 42

if __name__ == "__main__":
    print(asyncio.run(main()))
```

**Dense one-liner:** `asyncio.run(main())`.

**Complexity:** O(1) bootstrap.  **Gotcha:** calling `asyncio.run` twice in tests creates/destroys loops repeatedly — use `pytest-asyncio` `event_loop` fixture or the `asyncio` test mode.

---

## Track A.4 — System Design in Python (Q.061–Q.080)

> Companies: Amazon, Stripe, Datadog, Cloudflare, Snowflake, Lyft, Airbnb, Atlassian. Focus: rate limiters, circuit breakers, retries, idempotency, queues, sharding, caches, leader election, distributed locks. Code is deliberately compact — interviewers want intent + tradeoffs.

### Q.061 — Token-bucket rate limiter (single-process)
**Companies:** Stripe, Cloudflare, Datadog.

**Prose:** Tokens refill at `rate/sec` up to `capacity`; each request consumes one. Token bucket allows controlled bursts; leaky bucket smooths to constant rate. State: last-refill timestamp + current tokens.

```python
import time, threading

class TokenBucket:
    def __init__(self, rate: float, capacity: int) -> None:
        self.rate, self.capacity = rate, capacity
        self.tokens: float = capacity
        self.ts = time.monotonic()
        self.lock = threading.Lock()

    def allow(self) -> bool:
        with self.lock:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.ts) * self.rate)
            self.ts = now
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False
```

**Dense one-liner:** `tokens = min(cap, tokens + (now-ts)*rate); allow = tokens >= 1`.

**Complexity:** O(1) per check.  **Gotcha:** use `time.monotonic()` not `time.time()` — wall clock can jump backward (NTP) and grant infinite tokens.

---

### Q.062 — Distributed rate limiter with Redis (atomic Lua)
**Companies:** Stripe, Cloudflare.

**Prose:** Per-process buckets don't scale across N replicas. Redis + Lua is the canonical fix — Lua runs atomically inside Redis, so refill+consume is race-free across all clients.

```python
import redis

LUA = """
local k=KEYS[1]; local rate=tonumber(ARGV[1]); local cap=tonumber(ARGV[2]); local now=tonumber(ARGV[3])
local b=redis.call('HMGET',k,'t','ts'); local t=tonumber(b[1]) or cap; local ts=tonumber(b[2]) or now
t=math.min(cap, t + (now-ts)*rate)
local ok=0; if t>=1 then t=t-1; ok=1 end
redis.call('HMSET',k,'t',t,'ts',now); redis.call('EXPIRE',k,60)
return ok
"""

class RedisRL:
    def __init__(self, r: redis.Redis, rate: float, cap: int) -> None:
        self.r, self.rate, self.cap = r, rate, cap
        self.sha = r.script_load(LUA)
    def allow(self, key: str) -> bool:
        import time
        return bool(self.r.evalsha(self.sha, 1, key, self.rate, self.cap, time.time()))
```

**Dense one-liner:** `r.evalsha(sha, 1, key, rate, cap, now)`.

**Complexity:** O(1) Redis call.  **Gotcha:** Redis Cluster requires all `KEYS[]` in the same hash slot — embed `{tenant}` hash tags in the key (`rl:{tenant}:user`) or your script fails on multi-node setups.

---

### Q.063 — Circuit breaker (closed/open/half-open)
**Companies:** Amazon, Stripe, Atlassian.

**Prose:** Closed → call passes; open → fail fast; half-open → allow N probe calls. Trip on N consecutive failures or error rate > X% over window. Prevents cascading failure.

```python
import time
from enum import Enum

class State(Enum): CLOSED=1; OPEN=2; HALF=3

class Breaker:
    def __init__(self, threshold: int = 5, cooldown: float = 30.0) -> None:
        self.fail = 0; self.state = State.CLOSED; self.opened_at = 0.0
        self.threshold, self.cooldown = threshold, cooldown
    def call(self, fn, *a, **k):
        if self.state is State.OPEN:
            if time.monotonic() - self.opened_at < self.cooldown:
                raise RuntimeError("circuit open")
            self.state = State.HALF
        try:
            r = fn(*a, **k); self.fail = 0; self.state = State.CLOSED; return r
        except Exception:
            self.fail += 1
            if self.fail >= self.threshold:
                self.state = State.OPEN; self.opened_at = time.monotonic()
            raise
```

**Dense one-liner:** `if fail>=N: state=OPEN; opened_at=now`.

**Complexity:** O(1).  **Gotcha:** half-open should allow exactly **one** probe; allowing many re-opens on a flapping dependency — use a semaphore of 1.

---

### Q.064 — Exponential backoff with full jitter
**Companies:** Amazon (canonical AWS pattern), Stripe.

**Prose:** Naïve `2**i` causes synchronised retries (thundering herd). "Full jitter": `sleep = random.uniform(0, min(cap, base*2**i))`. Decorrelated jitter is even smoother.

```python
import random, time

def retry(fn, attempts: int = 6, base: float = 0.1, cap: float = 30.0):
    for i in range(attempts):
        try: return fn()
        except Exception:
            if i == attempts - 1: raise
            time.sleep(random.uniform(0, min(cap, base * 2**i)))
```

**Dense one-liner:** `time.sleep(random.uniform(0, min(cap, base*2**i)))`.

**Complexity:** O(A) attempts.  **Gotcha:** retrying non-idempotent writes (POST without idempotency key) duplicates work — only retry on safe verbs or with a key.

---

### Q.065 — Idempotency key middleware
**Companies:** Stripe (literally invented this), Square.

**Prose:** Client sends `Idempotency-Key` header; server stores `(key → response)` for 24h. Replay returns cached response. Critical for retries on POST.

```python
import hashlib, json
from typing import Callable

cache: dict[str, bytes] = {}  # use Redis in prod

def idempotent(handler: Callable[[dict], bytes]):
    def wrap(req: dict) -> bytes:
        key = req["headers"].get("Idempotency-Key")
        if key:
            sig = hashlib.sha256((key + json.dumps(req["body"], sort_keys=True)).encode()).hexdigest()
            if sig in cache: return cache[sig]
            resp = handler(req); cache[sig] = resp; return resp
        return handler(req)
    return wrap
```

**Dense one-liner:** `cache.setdefault(sha256(key+body), handler(req))`.

**Complexity:** O(1) lookup.  **Gotcha:** must hash the **body** with the key — same key + different body = client bug; return 422, don't return the cached response.

---

### Q.066 — LRU cache with TTL
**Companies:** Cloudflare, Datadog, Snowflake.

**Prose:** `functools.lru_cache` has no TTL. Use `OrderedDict` + per-entry expiry, or `cachetools.TTLCache`. Move-to-end on access for LRU semantics.

```python
import time
from collections import OrderedDict

class TTLCache:
    def __init__(self, maxsize: int, ttl: float) -> None:
        self.maxsize, self.ttl = maxsize, ttl
        self.d: OrderedDict[str, tuple[float, object]] = OrderedDict()
    def get(self, k: str):
        if k not in self.d: return None
        ts, v = self.d[k]
        if time.monotonic() - ts > self.ttl:
            del self.d[k]; return None
        self.d.move_to_end(k); return v
    def set(self, k: str, v: object) -> None:
        self.d[k] = (time.monotonic(), v); self.d.move_to_end(k)
        if len(self.d) > self.maxsize: self.d.popitem(last=False)
```

**Dense one-liner:** `OrderedDict.popitem(last=False)` evicts LRU.

**Complexity:** O(1) get/set.  **Gotcha:** `lru_cache` keys on positional args — passing the same value as kwarg vs. arg gives a cache miss; `cache_info()` to debug.

---

### Q.067 — Consistent hashing for shard placement
**Companies:** Cloudflare, Snowflake, Lyft.

**Prose:** Map keys to a hash ring of virtual nodes; adding/removing a node moves only `K/N` keys, not all. Used by every CDN, every distributed cache.

```python
import bisect, hashlib

class Ring:
    def __init__(self, nodes: list[str], vnodes: int = 100) -> None:
        self.ring: list[tuple[int, str]] = []
        for n in nodes:
            for i in range(vnodes):
                h = int(hashlib.md5(f"{n}#{i}".encode()).hexdigest(), 16)
                self.ring.append((h, n))
        self.ring.sort()
    def get(self, key: str) -> str:
        h = int(hashlib.md5(key.encode()).hexdigest(), 16)
        i = bisect.bisect(self.ring, (h,))
        return self.ring[i % len(self.ring)][1]
```

**Dense one-liner:** `ring[bisect(ring, (hash(key),)) % len(ring)]`.

**Complexity:** O(log V) lookup, V = vnodes.  **Gotcha:** too few vnodes → uneven load (one node gets 40%); 100–500 vnodes per physical node is typical.

---

### Q.068 — Bloom filter for "definitely not in set"
**Companies:** Snowflake, Cloudflare, Datadog.

**Prose:** k hash functions, m-bit array. False positives possible, false negatives never. Use to skip expensive lookups (e.g., DB hit for unknown user).

```python
import hashlib, math

class Bloom:
    def __init__(self, n: int, p: float = 0.01) -> None:
        self.m = int(-n * math.log(p) / (math.log(2)**2))
        self.k = max(1, int(self.m / n * math.log(2)))
        self.bits = bytearray((self.m + 7) // 8)
    def _hashes(self, x: str):
        h = hashlib.sha256(x.encode()).digest()
        h1, h2 = int.from_bytes(h[:8],"big"), int.from_bytes(h[8:16],"big")
        return ((h1 + i*h2) % self.m for i in range(self.k))
    def add(self, x: str) -> None:
        for b in self._hashes(x): self.bits[b//8] |= (1 << (b%8))
    def __contains__(self, x: str) -> bool:
        return all(self.bits[b//8] & (1 << (b%8)) for b in self._hashes(x))
```

**Dense one-liner:** double-hash trick `(h1 + i*h2) % m`.

**Complexity:** O(k) per op.  **Gotcha:** can't delete from a standard Bloom — use Counting Bloom (4-bit counters) if you need removal.

---

### Q.069 — Sliding window log rate limiter
**Companies:** Stripe, Cloudflare.

**Prose:** Store request timestamps in a deque; drop entries older than window; count = current rate. More accurate than fixed window (no boundary spikes) but O(N) memory per key.

```python
import time
from collections import deque

class SlidingWindow:
    def __init__(self, limit: int, window: float) -> None:
        self.limit, self.window = limit, window
        self.events: deque[float] = deque()
    def allow(self) -> bool:
        now = time.monotonic(); cutoff = now - self.window
        while self.events and self.events[0] < cutoff:
            self.events.popleft()
        if len(self.events) < self.limit:
            self.events.append(now); return True
        return False
```

**Dense one-liner:** `while q and q[0]<now-window: q.popleft(); q.append(now) if len(q)<limit else False`.

**Complexity:** amortised O(1).  **Gotcha:** unbounded memory under abuse — cap deque size or evict idle keys.

---

### Q.070 — Distributed lock with Redis (Redlock-lite caveats)
**Companies:** Stripe, Atlassian.

**Prose:** `SET key value NX PX ttl` is the primitive: atomic acquire with timeout. Release with Lua to check ownership before delete. Don't use for correctness-critical locks (see Kleppmann's critique) — use a real coordinator (etcd, Zookeeper).

```python
import redis, uuid

REL = "if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end"

def acquire(r: redis.Redis, key: str, ttl_ms: int = 30_000) -> str | None:
    tok = str(uuid.uuid4())
    return tok if r.set(key, tok, nx=True, px=ttl_ms) else None

def release(r: redis.Redis, key: str, tok: str) -> bool:
    return bool(r.eval(REL, 1, key, tok))
```

**Dense one-liner:** `r.set(key, uuid, nx=True, px=ttl_ms)`.

**Complexity:** O(1).  **Gotcha:** TTL means the lock can expire while you still hold it (stop-the-world GC, network pause) — design the protected operation to be **idempotent** and short.

---

### Q.071 — Outbox pattern for transactional event publishing
**Companies:** Stripe, Atlassian, Snowflake.

**Prose:** Write business row + event row in one DB transaction; a separate poller publishes events to Kafka/SQS, marks them sent. Solves dual-write atomicity (DB + queue).

```python
import psycopg

def create_order(conn: psycopg.Connection, order: dict) -> None:
    with conn.transaction():
        conn.execute("INSERT INTO orders(...) VALUES(...)", [...])
        conn.execute(
            "INSERT INTO outbox(topic, payload) VALUES(%s, %s::jsonb)",
            ["order.created", order],
        )

def publish_loop(conn: psycopg.Connection, kafka) -> None:
    rows = conn.execute("SELECT id, topic, payload FROM outbox WHERE sent_at IS NULL LIMIT 100").fetchall()
    for r in rows:
        kafka.send(r["topic"], r["payload"])
        conn.execute("UPDATE outbox SET sent_at=now() WHERE id=%s", [r["id"]])
```

**Dense one-liner:** business INSERT + outbox INSERT in one transaction.

**Complexity:** O(B) batch.  **Gotcha:** publisher must be **at-least-once** — consumers must dedupe by `event_id`; "exactly once" is a marketing term outside Kafka transactions.

---

### Q.072 — Leader election with a database lease
**Companies:** Stripe, Datadog.

**Prose:** Single row `(role, holder, expires_at)`; candidate wins by `UPDATE ... WHERE expires_at < now()`. Renews every `ttl/3`. Simpler than Raft for "one cron at a time".

```python
import time, socket

def try_lead(conn, role: str, ttl: int = 30) -> bool:
    me = f"{socket.gethostname()}-{time.time()}"
    cur = conn.execute(
        "UPDATE leases SET holder=%s, expires_at=now()+interval '%s sec' "
        "WHERE role=%s AND (holder=%s OR expires_at < now()) RETURNING holder",
        [me, ttl, role, me],
    )
    return cur.fetchone() is not None
```

**Dense one-liner:** `UPDATE ... WHERE expires_at<now() RETURNING holder`.

**Complexity:** O(1).  **Gotcha:** clock skew across nodes breaks `now()` comparisons — use the **DB server's** clock (one source) by reading `now()` server-side, never client time.

---

### Q.073 — Saga pattern for distributed transactions
**Companies:** Stripe, Snowflake, Atlassian.

**Prose:** Replace 2PC with a series of local transactions + compensating actions. Orchestrator coordinates; choreography lets services react to events. Each step is committed; rollback = compensate.

```python
from typing import Callable

def saga(steps: list[tuple[Callable, Callable]]) -> None:
    done: list[Callable] = []
    try:
        for forward, compensate in steps:
            forward(); done.append(compensate)
    except Exception:
        for c in reversed(done):
            try: c()
            except Exception as ce: print(f"compensation failed: {ce}")
        raise
```

**Dense one-liner:** `try: [f() for f,_ in steps] except: [c() for _,c in reversed(done)]`.

**Complexity:** O(N) steps.  **Gotcha:** compensations must be **idempotent and commutative** with new forward steps — design the data model so a refund can run before, after, or twice without breaking invariants.

---

### Q.074 — Event-driven retry with DLQ
**Companies:** Amazon (SQS DLQ pattern), Stripe.

**Prose:** Consumer retries N times with backoff; on exhaustion, push to dead-letter queue with original message + error context. Operator drains DLQ manually or with a tool.

```python
def consume(msg: dict, max_attempts: int = 5) -> None:
    attempts = msg.get("attempts", 0)
    try:
        process(msg["body"])
    except Exception as e:
        if attempts + 1 >= max_attempts:
            dlq.send({**msg, "error": str(e), "attempts": attempts + 1})
        else:
            queue.send({**msg, "attempts": attempts + 1}, delay=2**attempts)
```

**Dense one-liner:** `dlq.send(msg) if attempts>=max else queue.send(msg, delay=2**attempts)`.

**Complexity:** O(1) per msg.  **Gotcha:** DLQ that nobody monitors = silent data loss — alert on `DLQ depth > 0` always, not on growth rate.

---

### Q.075 — Idempotent UPSERT (Postgres `ON CONFLICT`)
**Companies:** Stripe, Snowflake.

**Prose:** `INSERT ... ON CONFLICT (key) DO UPDATE` is atomic and idempotent. Far safer than SELECT-then-INSERT-or-UPDATE which races under concurrency.

```python
def upsert_user(conn, user_id: str, email: str) -> None:
    conn.execute(
        "INSERT INTO users(id, email, updated_at) VALUES(%s,%s,now()) "
        "ON CONFLICT (id) DO UPDATE SET email=EXCLUDED.email, updated_at=now()",
        [user_id, email],
    )
```

**Dense one-liner:** `INSERT ... ON CONFLICT (id) DO UPDATE SET ... EXCLUDED.col`.

**Complexity:** O(1) per row.  **Gotcha:** `ON CONFLICT` requires a **unique constraint** on the conflict target — without it the planner can't choose the upsert path; you get a runtime error, not a fallback.

---

### Q.076 — Backpressure-aware HTTP client (aiohttp + bounded session)
**Companies:** Cloudflare, Datadog.

**Prose:** Combine `TCPConnector(limit=N, limit_per_host=M)` with `Semaphore(K)` for app-level cap. Set `total`/`connect`/`sock_read` timeouts explicitly — defaults are forever.

```python
import aiohttp, asyncio

async def get(sess: aiohttp.ClientSession, url: str) -> int:
    async with sess.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
        return r.status

async def main(urls: list[str]) -> list[int]:
    conn = aiohttp.TCPConnector(limit=200, limit_per_host=20)
    async with aiohttp.ClientSession(connector=conn) as sess:
        return await asyncio.gather(*(get(sess, u) for u in urls))
```

**Dense one-liner:** `aiohttp.TCPConnector(limit=N, limit_per_host=M)`.

**Complexity:** O(N) requests.  **Gotcha:** `ClientSession` is **expensive** to create — share one per process; per-request session leaks file descriptors.

---

### Q.077 — Health check endpoint: liveness vs. readiness
**Companies:** Google, Amazon, Cisco.

**Prose:** Liveness: am I deadlocked? (restart me). Readiness: can I serve traffic? (depends on deps — DB, cache). Conflating them causes restart storms when an upstream dies.

```python
from typing import Callable

deps: dict[str, Callable[[], bool]] = {}

def liveness() -> tuple[int, dict]:
    return 200, {"status": "alive"}

def readiness() -> tuple[int, dict]:
    failures = {n: not c() for n, c in deps.items()}
    bad = [n for n, f in failures.items() if f]
    return (503, {"not_ready": bad}) if bad else (200, {"status": "ready"})
```

**Dense one-liner:** liveness = process up; readiness = deps check.

**Complexity:** O(D) deps.  **Gotcha:** liveness probe that hits the DB causes a cluster-wide restart when the DB blips — keep liveness **purely local**.

---

### Q.078 — Graceful shutdown (SIGTERM handling)
**Companies:** Stripe, Datadog, Cloudflare.

**Prose:** On SIGTERM: stop accepting new work, drain in-flight requests, close pools, exit. Kubernetes sends SIGTERM then waits `terminationGracePeriodSeconds` (default 30s) before SIGKILL.

```python
import asyncio, signal

stopping = asyncio.Event()

async def serve() -> None:
    while not stopping.is_set():
        await handle_one()
    await drain()

async def main() -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stopping.set)
    await serve()
```

**Dense one-liner:** `loop.add_signal_handler(SIGTERM, stop_event.set)`.

**Complexity:** O(1).  **Gotcha:** preStop hook + `terminationGracePeriodSeconds` must exceed your worst-case drain — otherwise SIGKILL truncates in-flight work.

---

### Q.079 — Feature flag evaluation (deterministic bucketing)
**Companies:** LaunchDarkly-pattern, Stripe, Atlassian.

**Prose:** Hash `(flag_key + user_id) → [0,100)`; compare to rollout %. Same user always gets the same bucket — no DB lookup, no jitter on re-evaluation.

```python
import hashlib

def in_rollout(flag: str, user_id: str, percent: float) -> bool:
    h = hashlib.sha1(f"{flag}:{user_id}".encode()).digest()
    bucket = int.from_bytes(h[:4], "big") / 2**32 * 100
    return bucket < percent
```

**Dense one-liner:** `int(sha1(f"{flag}:{uid}").hexdigest()[:8],16)/0xFFFFFFFF*100 < pct`.

**Complexity:** O(1).  **Gotcha:** changing the hash salt/algorithm reshuffles every user — for a stable rollout, never touch the bucketing function.

---

### Q.080 — Multi-region active/active write conflict resolution
**Companies:** Snowflake, Cloudflare, Atlassian.

**Prose:** Three options: (1) Last-write-wins by timestamp (data loss). (2) CRDTs — automatic merge for sets/counters. (3) Application-level merge with version vectors. Choose by data semantics, not engineering preference.

```python
from dataclasses import dataclass, field

@dataclass
class GCounter:  # grow-only counter CRDT
    counts: dict[str, int] = field(default_factory=dict)
    def inc(self, node: str) -> None: self.counts[node] = self.counts.get(node, 0) + 1
    def value(self) -> int: return sum(self.counts.values())
    def merge(self, other: "GCounter") -> "GCounter":
        return GCounter({n: max(self.counts.get(n,0), other.counts.get(n,0))
                         for n in set(self.counts) | set(other.counts)})
```

**Dense one-liner:** `merge = {k: max(a.get(k,0), b.get(k,0)) for k in a|b}`.

**Complexity:** O(N) nodes.  **Gotcha:** CRDTs don't fix **business logic** conflicts (two regions both reserve the last seat) — for those, route writes to one region per partition (geo-partitioning).

---

## Track A.5 — Networking in Python (Q.081–Q.092)

> Companies: Cloudflare, Cisco, Datadog, Stripe, Meta. Focus: sockets, TLS, DNS, HTTP, retries, connection pooling, timeouts, websockets, raw protocols.

### Q.081 — TCP echo server with `socketserver.ThreadingTCPServer`
**Companies:** Cisco, Cloudflare.

**Prose:** Stdlib gives a working concurrent server in ~10 lines. Use for tooling/tests; production uses asyncio or a real framework.

```python
import socketserver

class Echo(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        while data := self.request.recv(4096):
            self.request.sendall(data)

with socketserver.ThreadingTCPServer(("0.0.0.0", 9000), Echo) as s:
    s.serve_forever()
```

**Dense one-liner:** `ThreadingTCPServer(addr, Handler).serve_forever()`.

**Complexity:** O(N) connections.  **Gotcha:** thread-per-connection caps at a few thousand on Linux; for >10k use asyncio (`asyncio.start_server`).

---

### Q.082 — Async TCP server with `asyncio.start_server`
**Companies:** Cloudflare, Meta.

**Prose:** Single-thread event loop handles tens of thousands of connections. Each accepted connection is a coroutine — natural backpressure via the loop.

```python
import asyncio

async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(4096):
            writer.write(data); await writer.drain()
    finally:
        writer.close(); await writer.wait_closed()

async def main() -> None:
    srv = await asyncio.start_server(handle, "0.0.0.0", 9000)
    async with srv: await srv.serve_forever()
asyncio.run(main())
```

**Dense one-liner:** `await asyncio.start_server(handle, host, port)`.

**Complexity:** O(N) connections, single thread.  **Gotcha:** `writer.write()` is buffered — always `await writer.drain()` before next write under load, or memory grows unbounded.

---

### Q.083 — TLS client with cert verification and SNI
**Companies:** Cloudflare, Cisco.

**Prose:** `ssl.create_default_context()` enables verification + system trust store. Pass `server_hostname=` for SNI; without it, multi-tenant TLS endpoints serve the wrong cert.

```python
import socket, ssl

def fetch(host: str, port: int = 443) -> bytes:
    ctx = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=5) as s:
        with ctx.wrap_socket(s, server_hostname=host) as tls:
            tls.sendall(f"GET / HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode())
            return b"".join(iter(lambda: tls.recv(4096), b""))
```

**Dense one-liner:** `ssl.create_default_context().wrap_socket(sock, server_hostname=host)`.

**Complexity:** O(B) bytes.  **Gotcha:** `ssl.PROTOCOL_TLS` is deprecated; `create_default_context()` picks safe defaults — never roll your own context unless you're pinning ciphers for compliance.

---

### Q.084 — DNS resolution: sync, async, and caching gotchas
**Companies:** Cloudflare, Meta, Datadog.

**Prose:** `socket.getaddrinfo` is blocking — in asyncio use `loop.getaddrinfo()` or `aiodns`. Python doesn't cache DNS; the OS/glibc usually does, but containers often don't (musl/Alpine). Long-lived connections survive TTL changes — restart on DNS flip if needed.

```python
import asyncio

async def resolve(host: str) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, None)
    return list({i[4][0] for i in infos})
```

**Dense one-liner:** `await loop.getaddrinfo(host, None)`.

**Complexity:** O(R) records.  **Gotcha:** `getaddrinfo` returns IPv6 first on dual-stack hosts; if your egress lacks v6, every connect tries v6 first and times out — pass `family=socket.AF_INET` to force v4.

---

### Q.085 — `requests` connection pooling and `Session`
**Companies:** Stripe, Datadog.

**Prose:** `requests.get()` opens+closes a connection every call. `Session` reuses a urllib3 pool — 10x faster for hot paths. Mount `HTTPAdapter` to tune `pool_maxsize`, `pool_connections`, `max_retries`.

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

s = requests.Session()
retry = Retry(total=3, backoff_factor=0.5, status_forcelist=(429,500,502,503,504))
s.mount("https://", HTTPAdapter(pool_connections=20, pool_maxsize=100, max_retries=retry))

r = s.get("https://api.example.com/x", timeout=(3, 10))
```

**Dense one-liner:** `Session(); s.mount("https://", HTTPAdapter(max_retries=Retry(...)))`.

**Complexity:** O(R) requests.  **Gotcha:** missing `timeout=` makes `requests` block **forever** on a stalled connection — always pass `(connect, read)` tuple.

---

### Q.086 — `httpx` async client (HTTP/2)
**Companies:** Cloudflare, Stripe.

**Prose:** `httpx` is the modern async-capable client (sync API too); supports HTTP/2 with `h2`. Drop-in mostly-compatible with `requests` API.

```python
import httpx, asyncio

async def fetch(urls: list[str]) -> list[int]:
    async with httpx.AsyncClient(http2=True, timeout=10) as c:
        rs = await asyncio.gather(*(c.get(u) for u in urls))
        return [r.status_code for r in rs]
```

**Dense one-liner:** `async with httpx.AsyncClient(http2=True) as c: await c.get(u)`.

**Complexity:** O(N) requests.  **Gotcha:** httpx defaults to **5s** connect timeout but **None** (forever) for read in older versions — always set `timeout=httpx.Timeout(...)` explicitly.

---

### Q.087 — Detect a stalled TCP connection (TCP keepalive)
**Companies:** Cisco, Cloudflare.

**Prose:** Without keepalive a half-open socket (peer rebooted, NAT dropped state) hangs forever. Set `SO_KEEPALIVE` + per-socket `TCP_KEEPIDLE/INTVL/CNT` — defaults are 2 hours, way too long.

```python
import socket

def keepalive(sock: socket.socket, idle: int = 30, intvl: int = 10, cnt: int = 3) -> None:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    if hasattr(socket, "TCP_KEEPIDLE"):  # Linux
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, idle)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, intvl)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, cnt)
```

**Dense one-liner:** `sock.setsockopt(SOL_SOCKET, SO_KEEPALIVE, 1)`.

**Complexity:** O(1).  **Gotcha:** macOS uses `TCP_KEEPALIVE` (singular, idle only); Windows has different consts entirely — gate on `hasattr`.

---

### Q.088 — Websocket client with reconnect + heartbeat
**Companies:** Cloudflare, Meta, Stripe.

**Prose:** Long-lived websockets need: reconnect with backoff, ping/pong heartbeat, message-level acks. `websockets` library handles ping; you handle reconnect.

```python
import asyncio, websockets

async def listen(url: str) -> None:
    backoff = 1
    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                backoff = 1
                async for msg in ws: print(msg)
        except Exception as e:
            print(f"reconnect in {backoff}s: {e}")
            await asyncio.sleep(backoff); backoff = min(60, backoff * 2)
```

**Dense one-liner:** `async with websockets.connect(url, ping_interval=20): async for m in ws: ...`.

**Complexity:** O(M) messages.  **Gotcha:** `ping_interval=None` disables heartbeat — silent half-open connections persist for hours; never disable in prod.

---

### Q.089 — HTTP server with structured logging and request ID
**Companies:** Stripe, Datadog.

**Prose:** Generate/propagate `X-Request-ID`, log it on every line for that request. Use `contextvars` so handlers don't have to thread it through.

```python
import asyncio, contextvars, uuid
from aiohttp import web

req_id: contextvars.ContextVar[str] = contextvars.ContextVar("rid", default="-")

@web.middleware
async def with_id(request: web.Request, handler) -> web.Response:
    rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    req_id.set(rid)
    resp = await handler(request)
    resp.headers["X-Request-ID"] = rid
    return resp
```

**Dense one-liner:** `req_id.set(request.headers.get("X-Request-ID", uuid.uuid4().hex))`.

**Complexity:** O(1).  **Gotcha:** if upstream is untrusted (public internet), **don't** echo client-supplied IDs blindly — strip or namespace, else log injection.

---

### Q.090 — Parse a raw HTTP response with `http.client`
**Companies:** Cisco, Cloudflare.

**Prose:** Useful for low-level debugging or custom transports. `HTTPResponse` parses headers + chunked encoding; you control the socket.

```python
import http.client

c = http.client.HTTPSConnection("example.com", timeout=5)
c.request("GET", "/", headers={"User-Agent": "demo"})
r = c.getresponse()
print(r.status, r.reason, r.headers["content-type"])
print(r.read(200))
c.close()
```

**Dense one-liner:** `http.client.HTTPSConnection(host).request("GET","/")`.

**Complexity:** O(B) bytes.  **Gotcha:** must `r.read()` (or close conn) before next request on same connection — pipelining is broken in stdlib; one in-flight at a time.

---

### Q.091 — Simulate packet loss / latency in tests (`socket` proxy)
**Companies:** Cisco, Cloudflare.

**Prose:** Build a tiny TCP proxy that injects delay or drops every Nth byte. Cheaper than `tc qdisc netem` for unit-test fault injection.

```python
import asyncio, random

async def pipe(reader, writer, drop: float, delay: float) -> None:
    while data := await reader.read(4096):
        if random.random() < drop: continue
        await asyncio.sleep(delay)
        writer.write(data); await writer.drain()
    writer.close()

async def proxy(lhost: int, rhost: str, rport: int, drop=0.01, delay=0.05) -> None:
    async def handle(r, w):
        rr, rw = await asyncio.open_connection(rhost, rport)
        await asyncio.gather(pipe(r, rw, drop, delay), pipe(rr, w, drop, delay))
    srv = await asyncio.start_server(handle, "127.0.0.1", lhost)
    async with srv: await srv.serve_forever()
```

**Dense one-liner:** `asyncio.gather(pipe(client→remote), pipe(remote→client))`.

**Complexity:** O(B).  **Gotcha:** dropping bytes mid-stream corrupts TCP semantics — for realistic loss simulation drop **whole connections** or use kernel netem.

---

### Q.092 — Detect MTU/PMTU issues from Python
**Companies:** Cisco, Cloudflare.

**Prose:** Black-hole PMTUD (firewall drops ICMP "frag needed") manifests as connections that hang on large payloads but work for small ones. Test with `IP_MTU_DISCOVER=IP_PMTUDISC_DO` and varying packet sizes.

```python
import socket

def probe_mtu(host: str, size: int = 1500) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if hasattr(socket, "IP_MTU_DISCOVER"):
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MTU_DISCOVER, 2)  # PMTUDISC_DO = DF bit
    try:
        s.sendto(b"x" * (size - 28), (host, 33434))
        return True
    except OSError as e:
        return False  # EMSGSIZE = path can't carry it
    finally: s.close()
```

**Dense one-liner:** `s.setsockopt(IPPROTO_IP, IP_MTU_DISCOVER, IP_PMTUDISC_DO)`.

**Complexity:** O(1).  **Gotcha:** Linux-only sockopt; on macOS use `IP_DONTFRAG`. UDP probe doesn't prove TCP path identical (different ECMP hash) — but usually good enough.

---

## Track A.6 — File I/O & Serialization (Q.093–Q.104)

> Companies: Snowflake, Stripe, Datadog, Cloudflare, Databricks. Focus: streaming reads, atomic writes, JSON/YAML/MsgPack/Parquet, pickle dangers, large-file handling, encoding traps.

### Q.093 — Stream a large file line-by-line (no full-load)
**Companies:** Snowflake, Datadog.

**Prose:** `for line in open(p)` is iterator-based and constant-memory. Never `.readlines()` for big logs — 50 GB log = 50 GB RAM.

```python
def grep(path: str, needle: str) -> int:
    n = 0
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if needle in line: n += 1
    return n
```

**Dense one-liner:** `sum(1 for line in open(p) if needle in line)`.

**Complexity:** O(L) lines, O(1) memory.  **Gotcha:** files without trailing newline still yield the last line; binary files (no newlines) yield one giant "line" — assert it's text first.

---

### Q.094 — Atomic file write (rename trick)
**Companies:** Stripe, Datadog.

**Prose:** Write to `path.tmp`, fsync, then `os.replace(tmp, path)` — replace is atomic on POSIX. Prevents partial files on crash.

```python
import os, tempfile

def atomic_write(path: str, data: bytes) -> None:
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=d)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        os.unlink(tmp); raise
```

**Dense one-liner:** `os.replace(tmp, final)` after `fsync`.

**Complexity:** O(B).  **Gotcha:** also `fsync` the **directory** (`os.open(dir,O_RDONLY); os.fsync(fd)`) for guaranteed durability of the rename — most code skips this and gets away with it.

---

### Q.095 — JSON streaming with `ijson`
**Companies:** Snowflake, Databricks.

**Prose:** `json.load` reads whole file. `ijson` is event-based — process arrays of millions of objects in constant memory.

```python
import ijson

def total_amount(path: str) -> float:
    total = 0.0
    with open(path, "rb") as f:
        for amt in ijson.items(f, "transactions.item.amount"):
            total += float(amt)
    return total
```

**Dense one-liner:** `sum(ijson.items(f, "items.item.amount"))`.

**Complexity:** O(N) records, O(1) RAM.  **Gotcha:** `ijson.items` requires the JSONPath-like prefix to match exactly — typo = silent zero results, not error.

---

### Q.096 — JSON encode for non-trivial types (datetime, Decimal, dataclass)
**Companies:** Stripe, Datadog.

**Prose:** Custom `default=` on `json.dumps`, or use a `JSONEncoder` subclass. Decimal as float loses precision — emit as string for money.

```python
import json, dataclasses, datetime
from decimal import Decimal

class Enc(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime): return o.isoformat()
        if isinstance(o, Decimal):           return str(o)
        if dataclasses.is_dataclass(o):      return dataclasses.asdict(o)
        return super().default(o)

print(json.dumps({"t": datetime.datetime.utcnow(), "amt": Decimal("19.99")}, cls=Enc))
```

**Dense one-liner:** `json.dumps(obj, default=str)` (lazy mode).

**Complexity:** O(N).  **Gotcha:** `default=str` serialises **everything** unknown via `str()` — works for datetimes, breaks silently for sets (`"{1, 2}"` not a JSON array).

---

### Q.097 — YAML safely (`safe_load`, never `load`)
**Companies:** Red Hat, Cisco, Stripe.

**Prose:** `yaml.load` can construct arbitrary Python objects → RCE on untrusted input. Always `yaml.safe_load`. Use `ruamel.yaml` if you need round-trip preservation of comments.

```python
import yaml

def parse(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)
```

**Dense one-liner:** `yaml.safe_load(open(p))`.

**Complexity:** O(N).  **Gotcha:** `safe_load` returns `None` for an empty file (not `{}`) — `cfg = yaml.safe_load(f) or {}` defensively.

---

### Q.098 — Pickle dangers and safer alternatives
**Companies:** Snowflake, Datadog.

**Prose:** `pickle.loads(untrusted)` = arbitrary code execution. Use only for trusted, internal data. For interop choose JSON (text), MsgPack/CBOR (compact binary), or Protobuf (schema'd).

```python
import pickle, hmac, hashlib

KEY = b"shared-secret"

def sign(data: bytes) -> bytes:
    return hmac.new(KEY, data, hashlib.sha256).digest() + data

def verify_load(blob: bytes) -> object:
    sig, data = blob[:32], blob[32:]
    if not hmac.compare_digest(sig, hmac.new(KEY, data, hashlib.sha256).digest()):
        raise ValueError("bad signature")
    return pickle.loads(data)
```

**Dense one-liner:** never `pickle.loads(untrusted)`; always HMAC-verify first.

**Complexity:** O(N).  **Gotcha:** even with HMAC, pickle lets you load classes that may not exist in the consumer — version skew = `ImportError` at deserialize time.

---

### Q.099 — MsgPack for compact binary IPC
**Companies:** Cloudflare, Datadog.

**Prose:** ~30% smaller than JSON, ~5x faster encode/decode, schema-less. Native types include bin (raw bytes) which JSON lacks.

```python
import msgpack

def roundtrip(obj: object) -> object:
    return msgpack.unpackb(msgpack.packb(obj, use_bin_type=True), raw=False)
```

**Dense one-liner:** `msgpack.unpackb(msgpack.packb(x, use_bin_type=True), raw=False)`.

**Complexity:** O(N).  **Gotcha:** legacy `raw=True` returns bytes for strings — bites you when keys come back as `b"key"` instead of `"key"`; pin `raw=False`.

---

### Q.100 — Read CSV with type coercion (csv vs. pandas)
**Companies:** Snowflake, Databricks, Stripe.

**Prose:** `csv.DictReader` is stdlib, streaming, no types — everything is string. `pandas.read_csv` infers types but loads to memory; use `chunksize=` for streaming.

```python
import csv

def parse(path: str) -> list[dict]:
    out: list[dict] = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            out.append({**row, "amount": float(row["amount"]), "qty": int(row["qty"])})
    return out
```

**Dense one-liner:** `[{**r,"amount":float(r["amount"])} for r in csv.DictReader(open(p))]`.

**Complexity:** O(R) rows.  **Gotcha:** `csv` module needs `newline=""` on the open — without it, embedded newlines in quoted fields break parsing on Windows.

---

### Q.101 — Parquet for columnar analytics (pyarrow)
**Companies:** Snowflake, Databricks, Datadog.

**Prose:** Columnar format with compression and predicate pushdown — orders of magnitude faster for analytical queries than CSV/JSON. Use `pyarrow.parquet` for writes; engines like DuckDB/Polars read directly.

```python
import pyarrow as pa, pyarrow.parquet as pq

def write(rows: list[dict], path: str) -> None:
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path, compression="zstd")

def read_filtered(path: str, min_amount: float):
    return pq.read_table(path, filters=[("amount", ">=", min_amount)])
```

**Dense one-liner:** `pq.write_table(pa.Table.from_pylist(rows), path, compression="zstd")`.

**Complexity:** O(N) write, O(matched) read.  **Gotcha:** Parquet's "schema evolution" is limited — adding a column is fine, renaming/retyping breaks readers; treat schemas as append-only.

---

### Q.102 — Encoding traps: bytes, str, BOM, mojibake
**Companies:** Stripe, Datadog.

**Prose:** Python 3 `str` is unicode; `bytes` is raw. UTF-8 with BOM (`\ufeff`) sneaks in from Windows tools — strip with `encoding="utf-8-sig"`. Never assume default encoding (varies by OS).

```python
def safe_read(path: str) -> str:
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()
```

**Dense one-liner:** `open(p, encoding="utf-8-sig", errors="replace")`.

**Complexity:** O(B).  **Gotcha:** `errors="replace"` hides corruption with `\ufffd` — for data integrity use `errors="strict"` and let it raise.

---

### Q.103 — Memory-mapped files for fast random access
**Companies:** Snowflake, Cloudflare.

**Prose:** `mmap` gives the OS a chance to page in only what you read; ideal for huge files with random access (indexed lookups). Read-only mmap shares pages across processes.

```python
import mmap

def at(path: str, offset: int, length: int) -> bytes:
    with open(path, "rb") as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
            return m[offset:offset+length]
```

**Dense one-liner:** `mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)`.

**Complexity:** O(1) seek.  **Gotcha:** size limit on 32-bit Python; growing the file under an open mmap is undefined — close mmap before resize.

---

### Q.104 — Tail a file (follow rotation, like `tail -F`)
**Companies:** Datadog, Splunk.

**Prose:** Reopen on inode change, seek to end on first open, `time.sleep` between reads. Foundation of every log shipper.

```python
import os, time

def tail(path: str):
    inode = None; pos = 0
    while True:
        try: st = os.stat(path)
        except FileNotFoundError: time.sleep(0.5); continue
        if st.st_ino != inode:
            inode, pos = st.st_ino, 0  # rotation
            f = open(path, "r"); f.seek(0, os.SEEK_END); pos = f.tell()
        f.seek(pos)
        if line := f.readline():
            pos = f.tell(); yield line
        else:
            time.sleep(0.2)
```

**Dense one-liner:** detect rotation via `os.stat(p).st_ino` change.

**Complexity:** O(L).  **Gotcha:** if the writer **truncates** (logrotate `copytruncate`) the inode is the same but size shrinks — also handle `st.st_size < pos` → reset to 0.

---

## Track A.7 — Logging, Metrics, Tracing (Q.105–Q.114)

> Companies: Datadog, Splunk, Honeycomb, Stripe, Cisco. Focus: structured logs, log levels, sampling, Prometheus metrics, OpenTelemetry, exemplars, cardinality control.

### Q.105 — Configure stdlib logging for JSON output
**Companies:** Datadog, Splunk, Stripe.

**Prose:** Stdlib `logging` is fine; just swap the `Formatter` for one that emits JSON. Avoids pulling in heavy dependencies and integrates with every log shipper.

```python
import json, logging, sys, time

class JsonFmt(logging.Formatter):
    def format(self, r: logging.LogRecord) -> str:
        d = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(r.created)),
             "lvl": r.levelname, "msg": r.getMessage(), "logger": r.name}
        if r.exc_info: d["exc"] = self.formatException(r.exc_info)
        return json.dumps(d)

h = logging.StreamHandler(sys.stdout); h.setFormatter(JsonFmt())
logging.basicConfig(level=logging.INFO, handlers=[h])
logging.info("hello", extra={"user": "x"})
```

**Dense one-liner:** subclass `logging.Formatter`, return `json.dumps(record_dict)`.

**Complexity:** O(1) per record.  **Gotcha:** `logging.basicConfig` is a **no-op** if any handler is already attached (e.g., by a library that called `getLogger().addHandler` at import) — call `logging.getLogger().handlers.clear()` first if needed.

---

### Q.106 — Per-request structured fields with `LoggerAdapter` / contextvars
**Companies:** Stripe, Datadog.

**Prose:** Threading `request_id` through every log call is tedious. `LoggerAdapter` injects fixed extras; combine with `contextvars` for async-safe per-request state.

```python
import contextvars, logging

req_id: contextvars.ContextVar[str] = contextvars.ContextVar("rid", default="-")

class CtxFilter(logging.Filter):
    def filter(self, r: logging.LogRecord) -> bool:
        r.request_id = req_id.get(); return True

logging.getLogger().addFilter(CtxFilter())
```

**Dense one-liner:** `Filter` injects `record.attr = ctxvar.get()` on every log.

**Complexity:** O(1).  **Gotcha:** custom attributes only appear in JSON formatters that read them — default `Formatter('%(message)s')` silently drops `request_id`.

---

### Q.107 — Avoid expensive log formatting on disabled levels
**Companies:** Cloudflare, Stripe.

**Prose:** `logger.debug(f"x={expensive()}")` evaluates `expensive()` even if DEBUG is off. Use lazy `%` formatting or guard with `isEnabledFor(DEBUG)`.

```python
import logging
log = logging.getLogger(__name__)

def hot_path(items: list) -> None:
    log.debug("processing %d items: %s", len(items), items)  # lazy
    if log.isEnabledFor(logging.DEBUG):
        log.debug("dump: %s", expensive_dump(items))
```

**Dense one-liner:** `log.debug("x=%s", val)` — never f-string.

**Complexity:** O(1) when disabled.  **Gotcha:** structured loggers (structlog, loguru) eagerly evaluate kwargs — same trap, different surface.

---

### Q.108 — Sample logs to control volume
**Companies:** Datadog, Cloudflare.

**Prose:** At >1k req/s, full logging breaks budgets. Sample by deterministic hash of trace_id (so a request is fully captured or fully dropped, never half).

```python
import hashlib, logging

def sampled(trace_id: str, rate: float = 0.01) -> bool:
    h = int(hashlib.sha1(trace_id.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return h < rate

if sampled(trace_id, 0.05):
    logging.info("...", extra={"trace_id": trace_id})
```

**Dense one-liner:** `int(sha1(tid)[:8],16)/0xFFFFFFFF < rate`.

**Complexity:** O(1).  **Gotcha:** **always** log errors regardless of sampling — sample success, never sample failures, or you lose the rare bug.

---

### Q.109 — Prometheus metrics with `prometheus_client`
**Companies:** Datadog, Cisco, Stripe.

**Prose:** Counters monotonically increase; Gauges go up/down; Histograms bucket observations. Expose `/metrics`; scrape interval × cardinality drives storage cost.

```python
from prometheus_client import Counter, Histogram, start_http_server
import time, random

REQS = Counter("http_requests_total", "Total requests", ["method", "status"])
LAT = Histogram("http_request_duration_seconds", "Latency", ["method"],
                buckets=(0.005,0.01,0.025,0.05,0.1,0.25,0.5,1,2.5,5))

def handle(method: str) -> None:
    with LAT.labels(method).time():
        time.sleep(random.random()*0.1)
    REQS.labels(method, "200").inc()

start_http_server(8000)
while True: handle("GET")
```

**Dense one-liner:** `with HIST.labels(...).time(): work(); CNT.labels(...).inc()`.

**Complexity:** O(1).  **Gotcha:** label cardinality explosion — `user_id` as label = millions of series = Prom OOM. Keep labels low-cardinality (method, status, route).

---

### Q.110 — Histogram buckets: choose them deliberately
**Companies:** Datadog, Stripe.

**Prose:** Default buckets target web latency (5ms–10s). For batch jobs (sec–min) or DB queries (µs–ms) you must override or quantiles are useless. Bucket boundaries are forever — changing them resets history.

```python
from prometheus_client import Histogram
DB = Histogram("db_query_seconds", "DB", ["op"],
               buckets=(.0005,.001,.002,.005,.01,.02,.05,.1,.25,.5,1))
```

**Dense one-liner:** `Histogram(name, doc, labels, buckets=(...))`.

**Complexity:** O(B) buckets per series.  **Gotcha:** `Summary` calculates client-side quantiles — can't aggregate across instances; almost always prefer Histogram.

---

### Q.111 — OpenTelemetry tracing (auto + manual spans)
**Companies:** Honeycomb, Datadog, Stripe.

**Prose:** OTel SDK with OTLP exporter is the vendor-neutral standard. Auto-instrumentation patches popular libraries; manual `start_as_current_span` for business spans.

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("create_order") as span:
    span.set_attribute("order.id", "123")
    span.set_attribute("order.amount", 99.95)
```

**Dense one-liner:** `with tracer.start_as_current_span("op"): ...`.

**Complexity:** O(S) spans.  **Gotcha:** `BatchSpanProcessor` drops spans on process exit if not flushed — call `provider.shutdown()` in `atexit` or you lose the last batch.

---

### Q.112 — Propagate trace context across HTTP/gRPC
**Companies:** Honeycomb, Datadog.

**Prose:** W3C Trace Context (`traceparent` header) is the standard. OTel propagators inject/extract automatically; for raw HTTP you do it yourself.

```python
from opentelemetry.propagate import inject, extract
from opentelemetry import trace

# client side
headers: dict[str, str] = {}
inject(headers)  # adds traceparent

# server side
ctx = extract(headers)
with trace.get_tracer(__name__).start_as_current_span("handle", context=ctx):
    ...
```

**Dense one-liner:** `inject(headers)` client-side, `extract(headers)` server-side.

**Complexity:** O(1).  **Gotcha:** older systems use B3 (`x-b3-traceid`) or Jaeger headers — configure a `CompositePropagator` if you bridge a heterogeneous fleet.

---

### Q.113 — Exemplars: linking metrics to traces
**Companies:** Honeycomb, Grafana.

**Prose:** Exemplars attach a sample trace_id to a Histogram bucket — letting you click from a latency spike straight to a slow trace. Requires Prom 2.26+ and OTel exemplar support.

```python
from prometheus_client import Histogram
from opentelemetry import trace

H = Histogram("op_seconds", "op latency")

def op() -> None:
    with H.time():
        sp = trace.get_current_span().get_span_context()
        # prometheus_client exemplar API
        H.observe(0.42, exemplar={"trace_id": format(sp.trace_id, "032x")})
```

**Dense one-liner:** `H.observe(v, exemplar={"trace_id": tid})`.

**Complexity:** O(1).  **Gotcha:** exemplars are sampled (one per bucket per scrape) — don't expect every observation to be queryable; pair with span sampling strategy.

---

### Q.114 — Detect and prevent metric cardinality explosion
**Companies:** Datadog, Cisco, Stripe.

**Prose:** Cardinality = product of label value counts. `path` raw URL with IDs is the classic foot-gun. Normalise (`/users/:id`), bucket continuous values, and **alert on series count per metric**.

```python
import re

def normalise(path: str) -> str:
    path = re.sub(r"/\d+", "/:id", path)
    path = re.sub(r"/[0-9a-f]{8,}", "/:hex", path)
    return path
```

**Dense one-liner:** `re.sub(r"/\d+","/:id", path)` before label.

**Complexity:** O(L).  **Gotcha:** Datadog/NewRelic charge per **distinct tag value** — cardinality control is a billing issue, not just a perf one.

---

# Track B — Thematic Python Mastery (Q.115–Q.248)

> Track A was SRE/infra-first. Track B is canonical Python craft an interviewer expects of any senior engineer: testing, performance, types, decorators, generators, OOP, functional, strings/regex, data structures (with ~10 algos integrated), and Python-specific gotchas. ~10 algorithm-style questions appear in Section B.8 (data structures); ~50 more live in Track C appendix.

## Track B.8 — Testing (Q.115–Q.130)

> Companies: Stripe, Atlassian, Datadog, Google, Meta, Snowflake. Focus: pytest fixtures, parametrize, mocking, fakes vs. mocks, property tests, async tests, coverage, contract testing.

### Q.115 — pytest fixtures: scope, finalisation, autouse
**Companies:** Stripe, Datadog.

**Prose:** Fixtures replace setUp/tearDown. Scopes: function (default), class, module, session. Use `yield` for teardown after the yielded value is consumed.

```python
import pytest, psycopg

@pytest.fixture(scope="session")
def db():
    conn = psycopg.connect("dbname=test")
    yield conn
    conn.close()

@pytest.fixture
def clean_table(db):
    db.execute("TRUNCATE users")
    yield
```

**Dense one-liner:** `@pytest.fixture(scope="session"); yield resource; cleanup`.

**Complexity:** O(1) per test.  **Gotcha:** `autouse=True` fixtures run for **every** test in scope — easy to slow the entire suite by attaching expensive setup unintentionally.

---

### Q.116 — Parametrize for table-driven tests
**Companies:** Google, Stripe.

**Prose:** `@pytest.mark.parametrize` runs one test function over many inputs, each as a separate test case (good failure isolation, clear names).

```python
import pytest

@pytest.mark.parametrize("a,b,exp", [
    (1, 2, 3),
    (-1, 1, 0),
    (0, 0, 0),
])
def test_add(a, b, exp):
    assert a + b == exp
```

**Dense one-liner:** `@pytest.mark.parametrize("a,b,exp", [...])`.

**Complexity:** O(N) cases.  **Gotcha:** for ID readability use `ids=lambda v: ...` or `pytest.param(..., id="name")` — default IDs (`test_add[1-2-3]`) become unreadable for complex tuples.

---

### Q.117 — Mock vs. fake vs. stub
**Companies:** Atlassian, Stripe.

**Prose:** Stub returns canned values. Mock asserts how it was called. Fake is a simplified working implementation (in-memory DB). Prefer fakes — mocks couple tests to implementation.

```python
class FakeKV:
    def __init__(self): self.d: dict[str, str] = {}
    def get(self, k: str) -> str | None: return self.d.get(k)
    def set(self, k: str, v: str) -> None: self.d[k] = v

def test_with_fake():
    kv = FakeKV(); kv.set("a", "1")
    assert kv.get("a") == "1"
```

**Dense one-liner:** small in-memory class implementing the protocol.

**Complexity:** trivial.  **Gotcha:** "mock everything" tests pass even when the real interface changes — fakes catch contract drift; mocks don't.

---

### Q.118 — `unittest.mock.patch` and where-to-patch rule
**Companies:** Stripe, Snowflake.

**Prose:** Patch the **name where it's looked up**, not where it's defined. `from x import y` → patch `module_under_test.y`, not `x.y`.

```python
# code.py
from time import time
def now() -> float: return time()

# test_code.py
from unittest.mock import patch

def test_now():
    with patch("code.time", return_value=42):
        from code import now
        assert now() == 42
```

**Dense one-liner:** `patch("module_under_test.imported_name")`, not its source.

**Complexity:** O(1).  **Gotcha:** `patch.object(cls, "method")` is safer than string paths — refactors that rename modules don't break tests silently.

---

### Q.119 — Property-based testing with Hypothesis
**Companies:** Stripe, Datadog, Atlassian.

**Prose:** Generate hundreds of random inputs that satisfy a strategy; shrink failures to minimal counter-examples. Catches edge cases hand-written tests miss.

```python
from hypothesis import given, strategies as st

def reverse(s: str) -> str: return s[::-1]

@given(st.text())
def test_reverse_idempotent(s):
    assert reverse(reverse(s)) == s
```

**Dense one-liner:** `@given(st.text())` then assert invariant.

**Complexity:** O(K) examples.  **Gotcha:** non-deterministic strategies + `@settings(deadline=...)` matter for CI — flaky test = bad strategy, not bad code.

---

### Q.120 — Async tests with `pytest-asyncio`
**Companies:** Cloudflare, Stripe.

**Prose:** Mark coroutine tests `@pytest.mark.asyncio` (or set `asyncio_mode = "auto"` in `pytest.ini`). Each test gets its own event loop.

```python
import asyncio, pytest

@pytest.mark.asyncio
async def test_sleep():
    await asyncio.sleep(0)
    assert True
```

**Dense one-liner:** `@pytest.mark.asyncio async def test_x(): ...`.

**Complexity:** O(1) per test.  **Gotcha:** sharing fixtures across event loops (session-scoped DB pool + function-scoped loop) raises `RuntimeError: attached to a different loop` — pin loop scope to match.

---

### Q.121 — Coverage with branch coverage + missing-line reports
**Companies:** Google, Stripe.

**Prose:** `coverage.py` with `branch=True` catches untaken `if/else` legs. Line coverage alone hides dead branches.

```bash
coverage run --branch -m pytest
coverage report -m --skip-covered
coverage html
```

**Dense one-liner:** `coverage run --branch -m pytest && coverage report -m`.

**Complexity:** runtime overhead ~5–10%.  **Gotcha:** subprocess code (multiprocessing workers) not captured unless you set `COVERAGE_PROCESS_START` and call `coverage.process_startup()`.

---

### Q.122 — Snapshot testing (syrupy)
**Companies:** Atlassian, Stripe.

**Prose:** Assert output matches a stored snapshot; review diffs in PRs. Great for serialised structures (JSON, YAML, rendered HTML) where assertions per-key would be verbose.

```python
def test_render(snapshot):
    output = render({"name": "ada"})
    assert output == snapshot
```

**Dense one-liner:** `assert obj == snapshot`.

**Complexity:** O(N).  **Gotcha:** snapshots can rot — running with `--snapshot-update` blindly accepts diffs; require human review in PRs.

---

### Q.123 — Contract testing (Pact)
**Companies:** Atlassian, Stripe, Snowflake.

**Prose:** Consumer publishes the interactions it expects; provider verifies it can fulfil them. Catches API drift between teams without full E2E tests.

```python
# consumer test (pseudo)
from pact import Consumer, Provider
pact = Consumer("OrderSvc").has_pact_with(Provider("PaymentSvc"))
(pact.given("a valid card").upon_receiving("a charge")
     .with_request("post", "/charge", body={"amount": 100})
     .will_respond_with(200, body={"id": "ch_x"}))
```

**Dense one-liner:** consumer drives the contract, provider verifies it.

**Complexity:** O(I) interactions.  **Gotcha:** without a broker (Pactflow), pact files drift — you need CI to fail provider builds when consumer pacts change.

---

### Q.124 — Testcontainers for real-dep integration tests
**Companies:** Stripe, Snowflake.

**Prose:** Spin up real Postgres/Kafka/Redis in Docker for each test session. Slower than mocks but catches SQL dialect bugs, driver quirks, real concurrency.

```python
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def pg():
    with PostgresContainer("postgres:16") as p:
        yield p.get_connection_url()
```

**Dense one-liner:** `with PostgresContainer("postgres:16") as p: ...`.

**Complexity:** seconds per session.  **Gotcha:** CI runners need Docker-in-Docker or socket mount — locked-down runners (some Cisco internal) require alternative (real shared DB).

---

### Q.125 — Freeze time in tests (`freezegun`)
**Companies:** Stripe, Datadog.

**Prose:** Code that depends on `datetime.now()` is hard to test. `freeze_time` patches both `datetime` and `time.time` globally for the block.

```python
from freezegun import freeze_time
import datetime

@freeze_time("2026-01-01")
def test_year():
    assert datetime.date.today().year == 2026
```

**Dense one-liner:** `@freeze_time("2026-01-01") def test_x(): ...`.

**Complexity:** O(1).  **Gotcha:** `freezegun` doesn't patch C-extension `time` calls (e.g., inside numpy) — they still see wall clock.

---

### Q.126 — Mocking HTTP with `responses` / `respx`
**Companies:** Stripe, Datadog.

**Prose:** Don't hit real APIs in tests. `responses` (sync, requests) and `respx` (async, httpx) intercept at the HTTP layer with assertion on URL/headers/body.

```python
import responses, requests

@responses.activate
def test_fetch():
    responses.get("https://api.example.com/x", json={"ok": True})
    r = requests.get("https://api.example.com/x")
    assert r.json() == {"ok": True}
```

**Dense one-liner:** `responses.get(url, json={...})` then call code under test.

**Complexity:** O(N) mocks.  **Gotcha:** `responses` raises on unmocked URLs only if `assert_all_requests_are_fired=True` — set it; otherwise silent passthrough hides real network calls in CI.

---

### Q.127 — Test doubles for time-based code (clocks)
**Companies:** Google, Stripe.

**Prose:** Inject a `Clock` interface; production uses `time.monotonic`, tests use a fake that you advance manually. Pure, no global state, no monkey-patching.

```python
from typing import Protocol

class Clock(Protocol):
    def now(self) -> float: ...

class FakeClock:
    def __init__(self): self.t = 0.0
    def now(self) -> float: return self.t
    def advance(self, dt: float) -> None: self.t += dt
```

**Dense one-liner:** inject `Clock` protocol, fake with mutable `t`.

**Complexity:** trivial.  **Gotcha:** still must inject the clock everywhere — half-converted code (some uses `time.time()` directly) defeats the test.

---

### Q.128 — Test for race conditions with `pytest-repeat` + asserts
**Companies:** Cloudflare, Stripe.

**Prose:** Race bugs are non-deterministic; running the same test 100x with `--count=100` flushes most out. Add invariant asserts inside loops, not just at the end.

```python
# pytest -p no:randomly --count=100 test_race.py
import threading

def test_no_race():
    counter = [0]; lock = threading.Lock()
    def bump():
        for _ in range(1000):
            with lock: counter[0] += 1
    ts = [threading.Thread(target=bump) for _ in range(10)]
    for t in ts: t.start()
    for t in ts: t.join()
    assert counter[0] == 10_000
```

**Dense one-liner:** `pytest --count=100` with `pytest-repeat`.

**Complexity:** linear in repeats.  **Gotcha:** "pass once = pass always" is a lie for concurrent code; flake rate ≠ 0% means a real bug.

---

### Q.129 — Golden output / approval tests
**Companies:** Atlassian, Stripe.

**Prose:** Capture stdout / generated file once, store, diff on each run. Great for CLIs and code generators. Differs from snapshots in that the asset is the value (file content), not a pickled python object.

```python
def test_cli_output(tmp_path, capsys):
    main(["--name", "ada"])
    captured = capsys.readouterr()
    expected = (tmp_path.parent / "golden/hello-ada.txt").read_text()
    assert captured.out == expected
```

**Dense one-liner:** `assert captured.out == golden_file.read_text()`.

**Complexity:** O(L) lines.  **Gotcha:** trailing whitespace + line endings (CRLF on Windows checkouts) cause spurious diffs — normalise both sides.

---

### Q.130 — Mutation testing (mutmut, cosmic-ray)
**Companies:** Google, Atlassian.

**Prose:** Mutate the code (flip `<` to `<=`, etc.); if tests still pass, the test suite is weak. Quantifies test quality beyond coverage %.

```bash
mutmut run --paths-to-mutate=src/
mutmut results
```

**Dense one-liner:** `mutmut run` then review surviving mutants.

**Complexity:** O(M × T) — slow, run nightly.  **Gotcha:** mutation testing on slow test suites is impractical — pair with fast subset; don't gate PRs on it.

---

## Track B.9 — Performance & Profiling (Q.131–Q.145)

> Companies: Google, Meta, Cloudflare, Datadog, Snowflake. Focus: cProfile, py-spy, memory_profiler, tracemalloc, big-O in real code, micro-optimisations that matter, numpy/cython, PEP 659 specialising adaptive interpreter.

### Q.131 — Profile CPU with `cProfile` and read pstats
**Companies:** Google, Datadog.

**Prose:** Stdlib profiler — deterministic, slowdown ~2x. Sort by cumulative time to find inclusive hot spots; tottime for self-time leaves.

```python
import cProfile, pstats

def slow():
    return sum(i*i for i in range(1_000_000))

p = cProfile.Profile(); p.enable(); slow(); p.disable()
pstats.Stats(p).sort_stats("cumulative").print_stats(15)
```

**Dense one-liner:** `cProfile.run("fn()", "out.prof")` then `pstats.Stats("out.prof")`.

**Complexity:** O(C) calls.  **Gotcha:** cProfile under-counts native calls (numpy, lxml) — they show as a single C call; switch to py-spy for whole-program view.

---

### Q.132 — Sampling profiler `py-spy` (no code changes)
**Companies:** Stripe, Datadog.

**Prose:** Statistical sampler that attaches to a running PID — no code change, low overhead, works in production. Output as flame graph or top-style live view.

```bash
py-spy record -o flame.svg --pid 12345 --duration 30
py-spy top --pid 12345
```

**Dense one-liner:** `py-spy record -o flame.svg --pid $PID`.

**Complexity:** ~5% overhead.  **Gotcha:** needs `ptrace` permission — in containers requires `--cap-add=SYS_PTRACE` or running as root in the same PID namespace.

---

### Q.133 — Memory profiling: `tracemalloc` (stdlib)
**Companies:** Snowflake, Datadog.

**Prose:** Snapshots Python allocations with file:line attribution. Diff two snapshots to find leaks. No external dep.

```python
import tracemalloc

tracemalloc.start()
snap1 = tracemalloc.take_snapshot()
big = [bytes(1024) for _ in range(10_000)]  # leak
snap2 = tracemalloc.take_snapshot()
for stat in snap2.compare_to(snap1, "lineno")[:5]:
    print(stat)
```

**Dense one-liner:** `snap2.compare_to(snap1, "lineno")`.

**Complexity:** ~10–20% overhead.  **Gotcha:** doesn't see C-extension allocations (numpy arrays show as small object headers) — pair with `psutil.Process().memory_info().rss` for total.

---

### Q.134 — Find memory leaks with `objgraph`
**Companies:** Snowflake, Cloudflare.

**Prose:** Visualises object reference chains; finds why objects aren't garbage-collected (usually a global registry, closure, or cycle).

```python
import objgraph
objgraph.show_growth(limit=10)         # top growers between calls
objgraph.show_backrefs([leaky_obj], max_depth=5, filename="refs.png")
```

**Dense one-liner:** `objgraph.show_backrefs([obj], filename="refs.png")`.

**Complexity:** O(R) refs.  **Gotcha:** generates large PNGs for hub objects (modules, dicts) — narrow with `too_many=10` or filter chain.

---

### Q.135 — Big-O of common Python operations
**Companies:** Google, Meta, Amazon.

**Prose:** Memorise: `list` index O(1), append O(1) amortised, insert(0) O(N); `dict/set` get/put O(1) average, O(N) worst; `in` on list O(N), on set O(1); `str` concat in loop O(N²) — use `"".join`.

```python
# WRONG: O(N^2)
s = ""
for x in xs: s += x

# RIGHT: O(N)
s = "".join(xs)
```

**Dense one-liner:** `"".join(iterable)` for string concat.

**Complexity:** see prose.  **Gotcha:** `collections.deque` gives O(1) `appendleft`/`popleft`; `list.pop(0)` is O(N) — wrong choice tanks throughput.

---

### Q.136 — `dict` insertion order and Python 3.7+ guarantees
**Companies:** Stripe, Atlassian.

**Prose:** Since 3.7 dicts preserve insertion order (language spec, not just impl). `OrderedDict` still useful for `move_to_end`, equality semantics, and `popitem(last=False)`.

```python
d = {"a": 1, "b": 2, "c": 3}
list(d.keys())  # ['a','b','c']

from collections import OrderedDict
o = OrderedDict([("a",1),("b",2)])
o.move_to_end("a")  # {'b':2, 'a':1}
```

**Dense one-liner:** plain dict preserves order; OrderedDict for ordering ops.

**Complexity:** O(1).  **Gotcha:** equality differs — `{"a":1,"b":2} == {"b":2,"a":1}` is True; `OrderedDict([...]) == OrderedDict([reversed])` is False.

---

### Q.137 — Use `__slots__` to cut per-instance memory
**Companies:** Snowflake, Meta.

**Prose:** `__slots__` replaces per-instance `__dict__` with a fixed array — 40–60% memory saving for high-volume objects (millions of records).

```python
class Point:
    __slots__ = ("x", "y")
    def __init__(self, x: float, y: float):
        self.x, self.y = x, y
```

**Dense one-liner:** `__slots__ = ("a","b")` at class level.

**Complexity:** O(1).  **Gotcha:** breaks weakref unless you add `"__weakref__"` to slots; multiple-inheritance with slots is fragile.

---

### Q.138 — `dataclass(slots=True, frozen=True)` for immutable records
**Companies:** Stripe, Datadog.

**Prose:** `@dataclass(slots=True)` (3.10+) gives slots without manual list. `frozen=True` blocks mutation post-init — hashable, safe to use as dict key.

```python
from dataclasses import dataclass

@dataclass(slots=True, frozen=True)
class Coord:
    lat: float
    lon: float
```

**Dense one-liner:** `@dataclass(slots=True, frozen=True)`.

**Complexity:** O(1).  **Gotcha:** `frozen=True` raises on `setattr` — to "modify" use `dataclasses.replace(coord, lat=...)`, which returns a new instance.

---

### Q.139 — Why list comprehensions beat manual loops
**Companies:** Google, Meta.

**Prose:** Comprehensions are bytecode-optimised: append happens in C without `LOAD_METHOD`/`CALL_METHOD` per iteration. ~30–50% faster than explicit `.append`.

```python
# slower
out = []
for x in xs:
    if x > 0: out.append(x*2)

# faster
out = [x*2 for x in xs if x > 0]
```

**Dense one-liner:** `[expr for x in xs if cond]`.

**Complexity:** same O, smaller constant.  **Gotcha:** comprehensions over generators inside f-strings can be hard to read — clarity > tiny perf wins.

---

### Q.140 — Generator vs. list when memory matters
**Companies:** Snowflake, Datadog.

**Prose:** `[x for x in big]` materialises all; `(x for x in big)` is lazy. Use generators in pipelines that consume once; list when you'll iterate twice.

```python
def lines(path: str):
    with open(path) as f:
        yield from (l.strip() for l in f)

count = sum(1 for l in lines("huge.log") if "ERROR" in l)
```

**Dense one-liner:** `sum(1 for x in stream if cond)`.

**Complexity:** O(1) memory.  **Gotcha:** generators are single-use — `g = (...); list(g); list(g)` second call returns `[]` silently.

---

### Q.141 — `numpy` vs. pure Python for numeric workloads
**Companies:** Snowflake, Meta.

**Prose:** Vectorised numpy ops run in C — 10–100x faster than Python loops on large arrays. Avoid `np.array(...).tolist()` round-trips.

```python
import numpy as np
a = np.arange(1_000_000)
print(np.sum(a*a))   # microseconds
print(sum(i*i for i in range(1_000_000)))  # ~50 ms
```

**Dense one-liner:** `np.sum(a*a)` — vectorised.

**Complexity:** O(N) but small constant.  **Gotcha:** numpy default int is platform-specific (int64 on 64-bit Linux, int32 on Windows) — pin `dtype=np.int64` for cross-platform reproducibility.

---

### Q.142 — `functools.lru_cache` for memoization
**Companies:** Google, Stripe.

**Prose:** Cache pure-function results by args. `maxsize=None` for unbounded; explicit size to bound memory. Use `cache_info()` to diagnose hit rate.

```python
from functools import lru_cache

@lru_cache(maxsize=10_000)
def fib(n: int) -> int:
    return n if n < 2 else fib(n-1) + fib(n-2)
```

**Dense one-liner:** `@lru_cache(maxsize=N) def f(...)`.

**Complexity:** O(1) per cache hit.  **Gotcha:** args must be **hashable** — list/dict args raise; convert to tuple/frozenset first.

---

### Q.143 — Avoid `+=` on bytes/str in loops
**Companies:** Datadog, Cloudflare.

**Prose:** `bytes` and `str` are immutable; `+=` builds a new object each iter — O(N²). Use `bytearray` or `io.BytesIO`/`StringIO` for accumulation.

```python
import io

def build(parts: list[bytes]) -> bytes:
    buf = io.BytesIO()
    for p in parts: buf.write(p)
    return buf.getvalue()
```

**Dense one-liner:** `b"".join(parts)` for bytes; `"".join(parts)` for str.

**Complexity:** O(N) with join, O(N²) with `+=`.  **Gotcha:** CPython 3 sometimes optimises `s += x` in-place when refcount is 1 — never rely on it; PyPy doesn't.

---

### Q.144 — Detect quadratic surprises with `timeit` parameter sweep
**Companies:** Google, Meta.

**Prose:** Run a microbenchmark across input sizes (10, 100, 1k, 10k); plot. If time grows faster than linear, you have hidden O(N²).

```python
import timeit
for n in (1000, 10_000, 100_000):
    t = timeit.timeit(f"x in lst", setup=f"lst=list(range({n})); x=-1", number=100)
    print(n, t)
```

**Dense one-liner:** `timeit.timeit("op", setup="...", number=N)` across sizes.

**Complexity:** N/A.  **Gotcha:** `in` on `list` is O(N); switch to `set` and the same code becomes O(1) — measure, don't assume.

---

### Q.145 — Cython / mypyc / Rust extensions for hot loops
**Companies:** Snowflake, Meta, Cloudflare.

**Prose:** When pure Python isn't fast enough and numpy doesn't fit: Cython for incremental typing, mypyc for compiling type-annotated Python, PyO3/maturin for Rust. 5–50x typical.

```python
# example.pyx (cython)
def sum_squares(int n) -> int:
    cdef int i, total = 0
    for i in range(n): total += i*i
    return total
```

**Dense one-liner:** add C types in Cython, compile to `.so`.

**Complexity:** small constant.  **Gotcha:** building wheels for every (OS, arch, Python version) tuple is real work — use `cibuildwheel` or accept platform restrictions.

---

## Track B.10 — Type Hints & Static Analysis (Q.146–Q.157)

> Companies: Stripe, Meta, Dropbox, Microsoft. Focus: PEP 484/612/695, generics, Protocols, TypedDict, Literal, NewType, Self, mypy strict mode.

### Q.146 — Generic functions with TypeVar
**Companies:** Meta, Stripe.

**Prose:** `TypeVar` lets a function preserve the input type in the output — checker enforces it without runtime cost.

```python
from typing import TypeVar, Iterable

T = TypeVar("T")

def first(it: Iterable[T]) -> T | None:
    for x in it: return x
    return None
```

**Dense one-liner:** `T = TypeVar("T")` then use in signatures.

**Complexity:** O(1).  **Gotcha:** PEP 695 (3.12+) lets you write `def first[T](it: Iterable[T]) -> T | None:` — older code is verbose; new code should use the new syntax.

---

### Q.147 — Protocol for structural typing (duck typing with checks)
**Companies:** Meta, Dropbox.

**Prose:** `Protocol` defines an interface by shape, no inheritance. Static checker accepts any class with matching methods — Pythonic and explicit.

```python
from typing import Protocol

class Closeable(Protocol):
    def close(self) -> None: ...

def shutdown(x: Closeable) -> None: x.close()
```

**Dense one-liner:** `class P(Protocol): def m(self) -> T: ...`.

**Complexity:** O(1).  **Gotcha:** `@runtime_checkable` Protocols use `hasattr` at runtime — slow and incomplete (doesn't check signatures); use only for `isinstance` guards.

---

### Q.148 — TypedDict for structured dict shapes
**Companies:** Meta, Stripe.

**Prose:** Type a dict with known keys (e.g., JSON config). `total=False` for optional keys; `Required`/`NotRequired` per-field (3.11+).

```python
from typing import TypedDict, NotRequired

class User(TypedDict):
    id: str
    name: str
    email: NotRequired[str]
```

**Dense one-liner:** `class T(TypedDict): k: type`.

**Complexity:** O(1).  **Gotcha:** TypedDict is **erased at runtime** — no validation; combine with pydantic if you need actual checks.

---

### Q.149 — `Literal` and `Final` for narrowing
**Companies:** Meta, Microsoft.

**Prose:** `Literal["GET", "POST"]` constrains string args at type-check time. `Final` marks a constant — reassignment is a type error.

```python
from typing import Literal, Final

PORT: Final[int] = 8080

def request(method: Literal["GET", "POST", "PUT", "DELETE"]) -> None: ...
request("GET")        # ok
request("PATCH")      # mypy error
```

**Dense one-liner:** `Literal["a","b"]` for enums-as-strings.

**Complexity:** O(1).  **Gotcha:** `Final` is **not enforced at runtime** — pure type-checker hint; intentional mutation still works.

---

### Q.150 — `NewType` for nominal aliases
**Companies:** Stripe, Meta.

**Prose:** `UserId = NewType("UserId", str)` creates a distinct type at check time — prevents passing `OrderId` where `UserId` expected. Zero runtime cost.

```python
from typing import NewType

UserId = NewType("UserId", str)
OrderId = NewType("OrderId", str)

def get_user(uid: UserId) -> dict: ...
get_user(OrderId("o_1"))  # mypy error
```

**Dense one-liner:** `Foo = NewType("Foo", str)`.

**Complexity:** O(1).  **Gotcha:** at runtime `UserId("x") is "x"` is True — they're indistinguishable; type-only protection.

---

### Q.151 — Generic classes
**Companies:** Meta, Dropbox.

**Prose:** Parameterise a class on a type variable. Useful for containers, repositories, result wrappers.

```python
from typing import Generic, TypeVar

T = TypeVar("T")

class Repo(Generic[T]):
    def __init__(self): self.items: list[T] = []
    def add(self, x: T) -> None: self.items.append(x)
```

**Dense one-liner:** `class C(Generic[T]): ...`.

**Complexity:** O(1).  **Gotcha:** in 3.12+ use `class Repo[T]:` directly — old `Generic[T]` still works but is deprecated style.

---

### Q.152 — `ParamSpec` for typed decorators
**Companies:** Meta, Stripe.

**Prose:** PEP 612 `ParamSpec` lets a decorator preserve the wrapped function's signature in type checks.

```python
from typing import ParamSpec, TypeVar, Callable
from functools import wraps

P = ParamSpec("P"); R = TypeVar("R")

def log(fn: Callable[P, R]) -> Callable[P, R]:
    @wraps(fn)
    def w(*a: P.args, **k: P.kwargs) -> R:
        print(fn.__name__); return fn(*a, **k)
    return w
```

**Dense one-liner:** `Callable[P, R]` with `ParamSpec("P")`.

**Complexity:** O(1).  **Gotcha:** without `ParamSpec` (e.g., `Callable[..., R]`) the checker loses arg types — every wrapped call accepts anything.

---

### Q.153 — `Self` type for fluent APIs (3.11+)
**Companies:** Meta, Stripe.

**Prose:** `Self` returns the actual subclass type from a method — fluent builders preserve `Subclass` rather than collapsing to base.

```python
from typing import Self

class Builder:
    def __init__(self): self.parts: list[str] = []
    def add(self, p: str) -> Self:
        self.parts.append(p); return self
```

**Dense one-liner:** `def m(self) -> Self: ...; return self`.

**Complexity:** O(1).  **Gotcha:** before 3.11 you wrote `T = TypeVar("T", bound="Builder"); def add(self: T) -> T:` — uglier but works on older Pythons.

---

### Q.154 — Run mypy in strict mode
**Companies:** Stripe, Meta.

**Prose:** `--strict` flips on all checks: no `Any`, no untyped defs, warn-return-any, etc. New code should pass strict; legacy adopts incrementally.

```ini
# pyproject.toml
[tool.mypy]
strict = true
files = "src"
```

**Dense one-liner:** `mypy --strict src/`.

**Complexity:** seconds.  **Gotcha:** third-party libs without stubs → `Any` everywhere; `ignore_missing_imports = true` per-module is the safety valve.

---

### Q.155 — pyright vs. mypy
**Companies:** Microsoft, Meta.

**Prose:** Pyright (Microsoft, Pylance backend) is faster and stricter on type narrowing; mypy is the reference impl from Guido. Both implement PEP 484; behaviour diverges on edge cases.

```bash
mypy src/
pyright src/
```

**Dense one-liner:** run both in CI for max coverage.

**Complexity:** seconds.  **Gotcha:** they disagree often enough that "passes both" is a real engineering target — pick one as the gate, the other as advisory.

---

### Q.156 — `cast` and `assert isinstance` for narrowing
**Companies:** Stripe, Dropbox.

**Prose:** `typing.cast(T, x)` lies to the checker (no runtime check). `assert isinstance(x, T)` narrows for the rest of the block and runs at runtime — safer.

```python
from typing import cast

def needs_str(x: object) -> int:
    assert isinstance(x, str)  # narrows to str below
    return len(x)
```

**Dense one-liner:** `assert isinstance(x, T)` to narrow.

**Complexity:** O(1).  **Gotcha:** `cast` is invisible at runtime — wrong cast = AttributeError far from the cast site, hard to debug.

---

### Q.157 — `@overload` for multiple signatures
**Companies:** Meta, Stripe.

**Prose:** Some functions return different types based on args (e.g., `get(key)` vs `get(key, default)`). `@overload` declares each signature; one implementation handles all.

```python
from typing import overload

@overload
def get(k: str) -> str | None: ...
@overload
def get(k: str, default: str) -> str: ...
def get(k: str, default: str | None = None) -> str | None:
    return _store.get(k, default)
```

**Dense one-liner:** stack `@overload` defs above real impl.

**Complexity:** O(1).  **Gotcha:** `@overload` defs have **no body** (only `...`); the real impl is the last def — runtime ignores the overloads entirely.

---

## Track B.11 — Decorators (Q.158–Q.167)

> Companies: Stripe, Google, Meta, Atlassian. Focus: function & class decorators, `wraps`, parameterised decorators, stacking, side effects, common patterns.

### Q.158 — Basic decorator with `functools.wraps`
**Companies:** Stripe, Google.

**Prose:** Always `@wraps(fn)` to preserve `__name__`, `__doc__`, `__wrapped__` — debuggers, docs, and introspection break otherwise.

```python
from functools import wraps

def trace(fn):
    @wraps(fn)
    def w(*a, **k):
        print(f"-> {fn.__name__}")
        return fn(*a, **k)
    return w
```

**Dense one-liner:** `@wraps(fn)` on every wrapper.

**Complexity:** O(1).  **Gotcha:** without `wraps`, every wrapped function reports its name as `w` — Sphinx docs and Sentry traces become useless.

---

### Q.159 — Parameterised decorator
**Companies:** Stripe, Atlassian.

**Prose:** Decorator factory: outer fn takes args, returns the actual decorator. Three nested layers — confusing the first time, idiomatic forever after.

```python
from functools import wraps

def retry(n: int):
    def deco(fn):
        @wraps(fn)
        def w(*a, **k):
            for i in range(n):
                try: return fn(*a, **k)
                except Exception:
                    if i == n-1: raise
        return w
    return deco

@retry(3)
def call(): ...
```

**Dense one-liner:** `def factory(arg): def deco(fn): def w(*a,**k): ... return w; return deco; return deco`.

**Complexity:** O(1).  **Gotcha:** decorator with optional args (`@retry` vs `@retry(3)`) needs a sniff — check first arg type or expose two names.

---

### Q.160 — Class as decorator (stateful)
**Companies:** Meta, Stripe.

**Prose:** A class with `__call__` can decorate. Useful when you need state (call count, cache, registry) and the class metaphor is cleaner than closures.

```python
class CountCalls:
    def __init__(self, fn):
        self.fn = fn; self.count = 0
    def __call__(self, *a, **k):
        self.count += 1
        return self.fn(*a, **k)

@CountCalls
def hello(): print("hi")
```

**Dense one-liner:** class with `__call__` as decorator.

**Complexity:** O(1).  **Gotcha:** instance methods get the class as decorator — `self` is the CountCalls, not the original class; descriptors get tricky.

---

### Q.161 — Decorating async functions
**Companies:** Cloudflare, Stripe.

**Prose:** Wrapper must be `async def` and `await fn(...)` — wrapping async with sync silently returns coroutines instead of values.

```python
from functools import wraps
import asyncio

def atrace(fn):
    @wraps(fn)
    async def w(*a, **k):
        print(f"-> {fn.__name__}")
        return await fn(*a, **k)
    return w
```

**Dense one-liner:** `async def w(*a,**k): return await fn(*a,**k)`.

**Complexity:** O(1).  **Gotcha:** if you want a decorator that handles both sync and async functions, sniff with `inspect.iscoroutinefunction(fn)` and branch — single wrapper can't do both naturally.

---

### Q.162 — `functools.cache` vs. `functools.lru_cache`
**Companies:** Google, Stripe.

**Prose:** `cache` (3.9+) = `lru_cache(maxsize=None)` — unbounded. Use only when keys are bounded; otherwise memory leak.

```python
from functools import cache

@cache
def fact(n: int) -> int:
    return 1 if n <= 1 else n * fact(n-1)
```

**Dense one-liner:** `@cache def f(...): ...`.

**Complexity:** O(1) per cached call.  **Gotcha:** instance methods + `cache` = leak — the `self` ref keeps the instance alive forever; use `weakref` cache or per-instance memoization.

---

### Q.163 — `contextlib.contextmanager` for resource decorators
**Companies:** Stripe, Datadog.

**Prose:** Quick way to build a `with`-statement context from a generator. `yield` once = setup before, teardown after.

```python
from contextlib import contextmanager
import time

@contextmanager
def timed(label: str):
    t0 = time.monotonic()
    try: yield
    finally: print(f"{label}: {time.monotonic()-t0:.3f}s")

with timed("op"):
    do_work()
```

**Dense one-liner:** `@contextmanager def cm(): setup; yield; teardown`.

**Complexity:** O(1).  **Gotcha:** if exception happens inside the `with`, it raises **at the `yield`** — wrap in try/finally to ensure teardown.

---

### Q.164 — `singledispatch` for function overloading by type
**Companies:** Stripe, Meta.

**Prose:** `@functools.singledispatch` dispatches on the type of the first argument — Pythonic alternative to `if isinstance(...)` chains.

```python
from functools import singledispatch

@singledispatch
def render(x): raise NotImplementedError

@render.register
def _(x: int): return f"int={x}"

@render.register
def _(x: list): return f"list of {len(x)}"
```

**Dense one-liner:** `@singledispatch` + `@fn.register` per type.

**Complexity:** O(1) dispatch.  **Gotcha:** dispatch is on the **first arg only**; for multi-arg dispatch use `multipledispatch` lib or rethink design.

---

### Q.165 — `cached_property` for one-shot computed attributes
**Companies:** Stripe, Datadog.

**Prose:** Compute once, store on the instance, return cached on subsequent access. Stdlib since 3.8.

```python
from functools import cached_property

class Doc:
    def __init__(self, text: str): self.text = text
    @cached_property
    def word_count(self) -> int:
        return len(self.text.split())
```

**Dense one-liner:** `@cached_property def attr(self) -> T: ...`.

**Complexity:** O(1) on subsequent reads.  **Gotcha:** stores on `__dict__` — incompatible with `__slots__` unless slots include the attr name.

---

### Q.166 — Stacking decorators: order matters
**Companies:** Google, Atlassian.

**Prose:** Decorators apply bottom-up: `@A @B def f` = `A(B(f))`. Outer wrapper sees inner's wrapped result. Affects what each decorator measures (e.g., timing inside auth check vs. outside).

```python
@cache       # outer
@retry(3)    # inner
def fetch(url): ...
# == cache(retry(3)(fetch))
```

**Dense one-liner:** bottom-up: closest to def runs first.

**Complexity:** O(D) decorators.  **Gotcha:** swap order and behaviour silently changes — `@retry(3) @cache` retries cache misses; `@cache @retry(3)` caches the retry result (including failures).

---

### Q.167 — Common decorator pitfall: shared mutable state
**Companies:** Stripe, Meta.

**Prose:** Closing over a mutable default in the decorator (e.g., a shared cache dict) leaks across all decorated functions. Always create state per-decoration.

```python
def cache_results(fn):
    store: dict = {}            # per-fn, fresh on each decoration — good
    def w(*a):
        if a not in store: store[a] = fn(*a)
        return store[a]
    return w
```

**Dense one-liner:** state inside the decorator factory, not at module level.

**Complexity:** O(1).  **Gotcha:** module-level shared dict means decorating two functions with similar arg shapes contaminates results; subtle bug.

---

## Track B.12 — Generators & Iterators (Q.168–Q.175)

> Companies: Google, Snowflake, Datadog. Focus: yield, send, generator pipelines, itertools, `__iter__`/`__next__`, infinite iterables.

### Q.168 — Generator basics: `yield` and lazy evaluation
**Companies:** Google, Snowflake.

**Prose:** `yield` pauses the function, returns the value, resumes on next iteration. Constant memory, perfect for streaming.

```python
def squares(n: int):
    for i in range(n): yield i*i

print(list(squares(5)))  # [0,1,4,9,16]
```

**Dense one-liner:** `def gen(): yield x` is a generator factory.

**Complexity:** O(1) memory.  **Gotcha:** calling the generator function returns a generator **object**; nothing runs until you iterate — easy to mistake for sync execution.

---

### Q.169 — `yield from` for delegation
**Companies:** Google, Stripe.

**Prose:** `yield from sub_gen()` is shorthand for `for x in sub_gen(): yield x` — and also forwards `send`/`throw`/return value. Crucial for composing generators.

```python
def chain(*its):
    for it in its:
        yield from it

list(chain([1,2], [3,4]))  # [1,2,3,4]
```

**Dense one-liner:** `yield from iterable`.

**Complexity:** O(N).  **Gotcha:** `yield from gen` propagates `StopIteration.value` as the result — useful but obscure; lots of code never sees this.

---

### Q.170 — Generator pipeline (UNIX-style)
**Companies:** Snowflake, Datadog.

**Prose:** Chain generators like UNIX pipes: each stage transforms a stream. Constant memory, composable, reads top-down.

```python
def lines(path):
    with open(path) as f: yield from f

def errors(lines):
    for l in lines:
        if "ERROR" in l: yield l

def count(stream):
    return sum(1 for _ in stream)

print(count(errors(lines("app.log"))))
```

**Dense one-liner:** `count(errors(lines(path)))`.

**Complexity:** O(N) with O(1) memory.  **Gotcha:** open file inside the outer generator — `with` exits before iteration finishes if the generator is GC'd; use `contextlib.closing` or hold the file open externally.

---

### Q.171 — `send()`: two-way generator communication
**Companies:** Cloudflare, Stripe.

**Prose:** `gen.send(x)` resumes the generator with `x` as the result of `yield`. Foundation of asyncio's coroutine machinery (pre-async/await).

```python
def echo():
    while True:
        x = yield
        print(f"got {x}")

g = echo(); next(g); g.send("hi"); g.send("bye")
```

**Dense one-liner:** `x = yield; gen.send(value)` to feed in.

**Complexity:** O(1).  **Gotcha:** must call `next(g)` (or `g.send(None)`) once to advance to first `yield` — otherwise `send` raises `TypeError`.

---

### Q.172 — Custom iterator with `__iter__`/`__next__`
**Companies:** Google, Meta.

**Prose:** Pre-generator pattern, still useful for stateful iterators or when you need both iter protocol and other methods.

```python
class Counter:
    def __init__(self, n): self.n = n; self.i = 0
    def __iter__(self): return self
    def __next__(self):
        if self.i >= self.n: raise StopIteration
        self.i += 1; return self.i
```

**Dense one-liner:** `__iter__` returns self; `__next__` raises `StopIteration` to end.

**Complexity:** O(1).  **Gotcha:** if `__iter__` returns a fresh iterator (not self), the object is iterable multiple times; if it returns self, it's single-use — pick deliberately.

---

### Q.173 — `itertools` essentials
**Companies:** Google, Meta, Stripe.

**Prose:** `chain`, `islice`, `groupby`, `combinations`, `product`, `accumulate`. Stdlib gold — replaces hand-rolled loops with C-speed iterators.

```python
from itertools import chain, islice, groupby, accumulate

list(chain([1,2], [3,4]))                      # [1,2,3,4]
list(islice(range(100), 5, 10))                # [5,6,7,8,9]
[(k, list(g)) for k, g in groupby("aaabbc")]   # [('a',['a','a','a']),...]
list(accumulate([1,2,3,4]))                    # [1,3,6,10]
```

**Dense one-liner:** memorise: `chain, islice, groupby, accumulate, combinations, product`.

**Complexity:** O(N).  **Gotcha:** `groupby` only groups **adjacent** equal keys — sort first if you want global grouping.

---

### Q.174 — Infinite iterators (`count`, `cycle`, `repeat`) + `islice`
**Companies:** Stripe, Cloudflare.

**Prose:** Combine an infinite iterator with `islice` to pluck a finite window — declarative pagination, retry generation, etc.

```python
from itertools import count, cycle, islice

list(islice(count(10, 2), 5))     # [10,12,14,16,18]
list(islice(cycle("ab"), 5))      # ['a','b','a','b','a']
```

**Dense one-liner:** `islice(infinite_iter, n)`.

**Complexity:** O(N) requested.  **Gotcha:** never `list(infinite_iter)` — instant hang.

---

### Q.175 — Generator-based coroutines vs. async/await
**Companies:** Google, Cloudflare.

**Prose:** Pre-3.5 async used `@asyncio.coroutine` + `yield from`. Modern code uses `async def` + `await`. Conceptually similar (suspend/resume) but `async def` enforces stricter semantics and is the only future-proof choice.

```python
# old (deprecated)
import asyncio
@asyncio.coroutine
def old(): yield from asyncio.sleep(1)

# modern
async def new(): await asyncio.sleep(1)
```

**Dense one-liner:** modern: `async def` + `await`; never use `@asyncio.coroutine`.

**Complexity:** O(1).  **Gotcha:** `@asyncio.coroutine` removed in 3.11 — code that still imports it crashes outright on upgrade.

---

## Track B.13 — Object-Oriented Python (Q.176–Q.190)

> Companies: Stripe, Atlassian, Meta, Snowflake. Focus: dataclasses, ABCs, MRO, descriptors, metaclasses, __init_subclass__, mixins, multiple inheritance, classmethod/staticmethod, dunder methods.

### Q.176 — Dataclass essentials and field options
**Companies:** Stripe, Atlassian.

**Prose:** `@dataclass` auto-generates `__init__`/`__repr__`/`__eq__`. `field(default_factory=list)` for mutable defaults; `init=False` for computed.

```python
from dataclasses import dataclass, field

@dataclass
class Order:
    id: str
    items: list[str] = field(default_factory=list)
    total: float = 0.0
```

**Dense one-liner:** `field(default_factory=list)` for mutable defaults.

**Complexity:** O(1).  **Gotcha:** `items: list = []` (no `field`) is the classic shared-state-across-instances bug; `@dataclass` raises at class creation time, but only if you remember `field`.

---

### Q.177 — Abstract base classes (`abc.ABC`)
**Companies:** Stripe, Snowflake.

**Prose:** `ABC` + `@abstractmethod` enforce subclass implementation at instantiation time. Better than docstring "you must override".

```python
from abc import ABC, abstractmethod

class Storage(ABC):
    @abstractmethod
    def save(self, key: str, value: bytes) -> None: ...

class S3(Storage):
    def save(self, key: str, value: bytes) -> None: ...
```

**Dense one-liner:** `class C(ABC): @abstractmethod def m(self): ...`.

**Complexity:** O(1).  **Gotcha:** `ABC` only checks at instantiation; you can still subclass an abstract class with missing methods — raises only on `Subclass()`.

---

### Q.178 — Method Resolution Order (MRO) and C3 linearisation
**Companies:** Meta, Google.

**Prose:** Multiple inheritance traversal order via C3. `Cls.__mro__` shows the chain. `super()` follows MRO, not the declared parent.

```python
class A: ...
class B(A): ...
class C(A): ...
class D(B, C): ...
print(D.__mro__)  # D, B, C, A, object
```

**Dense one-liner:** `Cls.__mro__` shows the lookup chain.

**Complexity:** O(N) classes.  **Gotcha:** diamond inheritance with `__init__` and inconsistent `super()` calls causes silent skip — every class in the chain must call `super().__init__(*a, **k)`.

---

### Q.179 — Cooperative multiple inheritance with `super()`
**Companies:** Meta, Snowflake.

**Prose:** `super()` is **not** "the parent" — it's the next class in MRO. Cooperative classes pass `**kwargs` through so siblings receive their args.

```python
class Base:
    def __init__(self, **kw): print("Base", kw)

class Logging:
    def __init__(self, **kw): print("Logging"); super().__init__(**kw)

class Service(Logging, Base):
    def __init__(self, name, **kw): self.name = name; super().__init__(**kw)
```

**Dense one-liner:** every `__init__` calls `super().__init__(**kw)`.

**Complexity:** O(M) MRO.  **Gotcha:** miss one `super()` call and the rest of the MRO is silently skipped — bug appears in unrelated subclass.

---

### Q.180 — Descriptors: how `@property` works
**Companies:** Meta, Stripe.

**Prose:** A descriptor is any object with `__get__`/`__set__`/`__delete__`. `property` is one. Custom descriptors implement validation, lazy attrs, ORM fields.

```python
class Positive:
    def __set_name__(self, owner, name): self.name = "_" + name
    def __get__(self, obj, objtype=None): return getattr(obj, self.name)
    def __set__(self, obj, value):
        if value < 0: raise ValueError
        setattr(obj, self.name, value)

class Item:
    qty = Positive()
```

**Dense one-liner:** descriptor = object with `__get__`/`__set__`.

**Complexity:** O(1).  **Gotcha:** descriptors must live on the **class**, not instance; assigning to `self.qty = Positive()` makes it just an attribute, not a descriptor.

---

### Q.181 — `__slots__` revisited: subclass behaviour
**Companies:** Meta, Snowflake.

**Prose:** Subclass without slots regains `__dict__` — defeats memory savings. All classes in chain need slots. Empty slots in subclass = no new fields but inherits slot discipline.

```python
class A:
    __slots__ = ("x",)

class B(A):
    __slots__ = ()  # still slotted; no new attrs

class C(A):
    pass            # has __dict__ again — leaks
```

**Dense one-liner:** child must declare `__slots__ = ()` to stay slot-only.

**Complexity:** O(1).  **Gotcha:** linters often miss this; an audit script that asserts `not hasattr(inst, "__dict__")` is the only reliable check.

---

### Q.182 — Class methods, static methods, instance methods
**Companies:** Atlassian, Stripe.

**Prose:** `@classmethod` gets `cls`, used for alternative constructors and registries. `@staticmethod` is just a function namespaced under the class. Instance methods get `self`.

```python
class User:
    def __init__(self, name): self.name = name
    @classmethod
    def from_dict(cls, d): return cls(d["name"])
    @staticmethod
    def is_valid_name(n): return n.isalpha()
```

**Dense one-liner:** `@classmethod def from_x(cls, ...): return cls(...)` for alt constructors.

**Complexity:** O(1).  **Gotcha:** `@staticmethod` and module-level function are nearly equivalent — prefer module function unless namespacing helps discoverability.

---

### Q.183 — Dunder methods worth knowing
**Companies:** Google, Meta.

**Prose:** `__repr__` (debug), `__str__` (user), `__eq__`+`__hash__` (containers), `__lt__` (sorting), `__enter__`/`__exit__` (with), `__call__`, `__len__`, `__getitem__`, `__contains__`.

```python
class Box:
    def __init__(self, items): self.items = items
    def __len__(self): return len(self.items)
    def __contains__(self, x): return x in self.items
    def __repr__(self): return f"Box({self.items!r})"
```

**Dense one-liner:** implement protocols, get language integration.

**Complexity:** O(1).  **Gotcha:** define `__eq__` without `__hash__` and the object becomes unhashable (`__hash__` set to None) — set `__hash__` explicitly if you want it in a dict/set.

---

### Q.184 — `__init_subclass__` for plugin registration
**Companies:** Stripe, Meta.

**Prose:** Hook called when a class is **defined**, not instantiated. Cleaner alternative to metaclasses for plugin/registry patterns.

```python
class Handler:
    handlers: dict[str, type] = {}
    def __init_subclass__(cls, *, name: str, **kw):
        super().__init_subclass__(**kw)
        Handler.handlers[name] = cls

class JsonHandler(Handler, name="json"): ...
```

**Dense one-liner:** `def __init_subclass__(cls, *, name, **kw): registry[name] = cls`.

**Complexity:** O(1) per subclass.  **Gotcha:** subclass kwargs need explicit handling — passing unknown kwargs to `super().__init_subclass__` raises.

---

### Q.185 — Metaclasses: when (rarely) appropriate
**Companies:** Meta, Snowflake.

**Prose:** Metaclass is a class whose instances are classes. Almost always overkill; `__init_subclass__` or class decorators suffice. Real uses: ORMs (SQLAlchemy declarative), ABCs.

```python
class UpperAttrs(type):
    def __new__(mcs, name, bases, ns):
        upper = {k.upper() if not k.startswith("_") else k: v for k, v in ns.items()}
        return super().__new__(mcs, name, bases, upper)

class C(metaclass=UpperAttrs):
    x = 1  # becomes C.X
```

**Dense one-liner:** `class C(metaclass=Meta): ...`.

**Complexity:** O(N) attrs.  **Gotcha:** mixing classes with different metaclasses raises `TypeError: metaclass conflict` — multiple inheritance becomes painful.

---

### Q.186 — Mixins for cross-cutting behaviour
**Companies:** Atlassian, Stripe.

**Prose:** A mixin is a small class providing one feature, mixed in via multiple inheritance. Keep them stateless or with tiny state, named with `Mixin` suffix.

```python
class JsonMixin:
    def to_json(self) -> str:
        import json
        return json.dumps(self.__dict__)

class User(JsonMixin):
    def __init__(self, n): self.name = n

print(User("ada").to_json())
```

**Dense one-liner:** `class C(MixinA, MixinB, Base): ...`.

**Complexity:** O(1).  **Gotcha:** mixin order matters in MRO — put mixins **before** the base class, else their methods get shadowed.

---

### Q.187 — Composition over inheritance — and when not
**Companies:** Stripe, Atlassian.

**Prose:** Inheritance couples subclass to parent's evolution; composition delegates. Default to composition; reach for inheritance only for genuine "is-a" with stable hierarchy.

```python
class Logger:
    def log(self, msg): print(msg)

class Service:
    def __init__(self, logger: Logger): self.log = logger.log
```

**Dense one-liner:** `__init__(self, dep)` then `self.dep.method()`.

**Complexity:** O(1).  **Gotcha:** "favour composition" is a guideline, not a law — for true polymorphism (Storage → S3, GCS) inheritance/Protocol is clearer.

---

### Q.188 — `Enum` for closed sets of values
**Companies:** Stripe, Atlassian.

**Prose:** `Enum` gives type-safe constants with iteration, comparison, and reverse lookup. `StrEnum`/`IntEnum` (3.11+) for serialisation interop.

```python
from enum import Enum, auto

class Status(Enum):
    PENDING = auto()
    ACTIVE = auto()
    CLOSED = auto()

print(Status.ACTIVE.name, Status.ACTIVE.value)
print(Status["ACTIVE"], Status(2))
```

**Dense one-liner:** `class E(Enum): A = auto()`.

**Complexity:** O(1).  **Gotcha:** `IntEnum` compares equal to ints — easy interop but breaks "no magic numbers" hygiene; prefer `Enum` unless you need int compatibility.

---

### Q.189 — `__post_init__` for dataclass derived fields
**Companies:** Stripe, Snowflake.

**Prose:** Compute fields after `__init__` runs. Use `field(init=False)` for the derived attr.

```python
from dataclasses import dataclass, field

@dataclass
class Order:
    items: list[float]
    total: float = field(init=False)
    def __post_init__(self):
        self.total = sum(self.items)
```

**Dense one-liner:** `@dataclass` + `__post_init__` for derived state.

**Complexity:** O(N).  **Gotcha:** `frozen=True` + `__post_init__` can't `self.x = ...` — must `object.__setattr__(self, "x", ...)`; ugly but documented.

---

### Q.190 — Equality and hashability rules
**Companies:** Google, Meta.

**Prose:** `__eq__` defined → `__hash__` set to None unless you also define `__hash__`. Mutable objects shouldn't be hashable. Frozen dataclasses get both for free.

```python
@dataclass(frozen=True)
class Coord:
    x: int
    y: int

s = {Coord(1,2), Coord(1,2)}  # one element
```

**Dense one-liner:** `@dataclass(frozen=True)` for hashable record.

**Complexity:** O(1).  **Gotcha:** `eq=True, frozen=False` (the default) makes `__hash__ = None` — you can't put it in a set; flip to `frozen=True` or write your own `__hash__`.

---

## Track B.14 — Functional Python (Q.191–Q.198)

> Companies: Meta, Stripe, Snowflake. Focus: map/filter/reduce, partial, lambda gotchas, immutability, comprehensions vs map.

### Q.191 — `map`/`filter` vs. comprehensions
**Companies:** Google, Meta.

**Prose:** Comprehensions are usually clearer and at least as fast. `map`/`filter` shine when the function already exists by name.

```python
xs = [1,2,3,4]
squares = [x*x for x in xs]
positives = list(filter(None, [0,1,0,2]))   # truthy
upper = list(map(str.upper, ["a","b"]))
```

**Dense one-liner:** prefer comprehensions; use `map(f, xs)` only with named `f`.

**Complexity:** O(N).  **Gotcha:** `map`/`filter` return iterators in Py3 — `len(map(...))` is a TypeError; wrap in `list` or iterate.

---

### Q.192 — `functools.reduce`
**Companies:** Snowflake, Meta.

**Prose:** Folds an iterable into a single value with a binary op. Often replaceable by `sum`, `math.prod`, or a loop — but unbeatable for custom merges.

```python
from functools import reduce
import operator
print(reduce(operator.mul, [1,2,3,4], 1))  # 24
```

**Dense one-liner:** `reduce(fn, iterable, initial)`.

**Complexity:** O(N).  **Gotcha:** without an initial value, empty iterable raises `TypeError` — always pass initial.

---

### Q.193 — `partial` for argument binding
**Companies:** Stripe, Meta.

**Prose:** Pre-bind arguments to produce a new callable. Useful for callbacks, retry/timeout wrappers, currying-light.

```python
from functools import partial

def power(base, exp): return base ** exp
square = partial(power, exp=2)
print(square(5))  # 25
```

**Dense one-liner:** `partial(fn, **fixed_kwargs)`.

**Complexity:** O(1).  **Gotcha:** positional pre-binding consumes **leftmost** args first — `partial(fn, 1)` fixes the first param, often surprising; use kwargs for clarity.

---

### Q.194 — Lambda closure pitfall (loop variable capture)
**Companies:** Google, Meta, Stripe.

**Prose:** `[lambda: i for i in range(3)]` returns three lambdas all returning 2 — they close over `i`, not its value at creation. Fix: default arg `lambda i=i: i`.

```python
fns = [lambda i=i: i for i in range(3)]
print([f() for f in fns])  # [0,1,2]
```

**Dense one-liner:** `lambda x=x: ...` to capture by value.

**Complexity:** O(N).  **Gotcha:** classic interview trap; same applies to nested functions, not just lambdas.

---

### Q.195 — Immutability: tuples, frozenset, frozen dataclass
**Companies:** Meta, Stripe.

**Prose:** Immutable types are hashable, thread-safe-by-default, and cheap to share. Use them for records, keys, set members.

```python
from dataclasses import dataclass

t = (1, 2, 3)
fs = frozenset([1,2])
@dataclass(frozen=True)
class P: x: int; y: int
```

**Dense one-liner:** prefer immutable for shared/keyed data.

**Complexity:** O(1).  **Gotcha:** tuple of mutable elements (`([1,2], 3)`) is **not** hashable — immutability doesn't propagate.

---

### Q.196 — Pure functions and side effects
**Companies:** Stripe, Meta.

**Prose:** Pure = same input → same output, no I/O, no mutation. Easier to test, parallelise, cache. Push side effects to the edges (functional core, imperative shell).

```python
def total(prices: list[float], tax: float) -> float:
    return sum(p * (1 + tax) for p in prices)  # pure

def save(order, repo):
    repo.insert(order)  # impure (I/O)
```

**Dense one-liner:** pure core + thin imperative shell.

**Complexity:** N/A.  **Gotcha:** "pure-ish" functions that read globals (env vars, config singletons) silently break determinism.

---

### Q.197 — `operator` module (named function objects)
**Companies:** Meta, Snowflake.

**Prose:** `operator.attrgetter`, `itemgetter`, `methodcaller` are faster than equivalent lambdas (C-implemented) and read better.

```python
from operator import itemgetter, attrgetter

rows = [{"name": "b", "n": 2}, {"name": "a", "n": 1}]
print(sorted(rows, key=itemgetter("name")))
```

**Dense one-liner:** `sorted(xs, key=itemgetter("k"))`.

**Complexity:** O(N log N) sort.  **Gotcha:** `itemgetter("a","b")` returns a tuple — useful for multi-key sort, but result isn't a single value; downstream code must unpack.

---

### Q.198 — `toolz` / `more-itertools` for functional composition
**Companies:** Stripe, Snowflake.

**Prose:** Third-party libs add `pipe`, `compose`, `chunked`, `partition_all`, `unique` — common operations missing from stdlib `itertools`.

```python
from more_itertools import chunked
list(chunked(range(10), 3))  # [[0,1,2],[3,4,5],[6,7,8],[9]]
```

**Dense one-liner:** `chunked(iter, n)` for batch processing.

**Complexity:** O(N).  **Gotcha:** `chunked` returns lists; for very large items use `ichunked` (iterators of iterators) to avoid materialising each chunk.

---

## Track B.15 — Strings, Regex, Encoding (Q.199–Q.210)

> Companies: Google, Stripe, Cloudflare. Focus: f-strings, format spec, regex (re vs. re2), unicode normalisation, str methods, parsing.

### Q.199 — f-string format mini-language
**Companies:** Google, Stripe.

**Prose:** `f"{x:>10.2f}"` = right-align width 10, 2 decimals. `{x!r}` for repr. `{x:%Y-%m-%d}` for datetime. `{x=}` (3.8+) for self-documenting debug.

```python
x, pi = 42, 3.14159
print(f"{x:>5}")         # "   42"
print(f"{pi:.3f}")       # "3.142"
print(f"{pi=}")          # "pi=3.14159"
```

**Dense one-liner:** `f"{val:fmt}"`, `{val=}` for debug.

**Complexity:** O(1).  **Gotcha:** `{val=}` includes the variable name **literally** as written — `{a.b=}` prints `a.b=value`.

---

### Q.200 — Regex basics (`re.match` vs. `search` vs. `fullmatch`)
**Companies:** Google, Cloudflare.

**Prose:** `match` anchors at start; `search` scans whole string; `fullmatch` requires whole-string match. Mixing them up is the #1 regex bug.

```python
import re
re.match(r"abc", "abcdef")     # match
re.match(r"def", "abcdef")     # None
re.search(r"def", "abcdef")    # match
re.fullmatch(r"abc", "abcdef") # None
```

**Dense one-liner:** start-anchor → match; anywhere → search; full → fullmatch.

**Complexity:** O(N).  **Gotcha:** `re.match` is **not** the same as `re.search(r"^...")` when `re.MULTILINE` — `^` matches each line; `match` only at index 0.

---

### Q.201 — Compile regex once for hot loops
**Companies:** Cloudflare, Datadog.

**Prose:** `re.compile` caches the parsed pattern; reuse the compiled object. `re` module already caches the last 512 patterns, but explicit is faster and clearer.

```python
import re
PAT = re.compile(r"\b(ERROR|WARN)\b")
def grep(lines):
    return [l for l in lines if PAT.search(l)]
```

**Dense one-liner:** `PAT = re.compile(...)` at module level.

**Complexity:** O(N).  **Gotcha:** `re.compile` flags must be passed at compile (`re.IGNORECASE`); re-passing at `search` raises in some scenarios.

---

### Q.202 — Catastrophic backtracking and `re2`
**Companies:** Cloudflare, Stripe.

**Prose:** Patterns like `(a+)+b` on `"aaaa…"` blow up exponentially. Stdlib `re` is backtracking. Google's `re2` lib (and `regex` lib's atomic groups) avoid it — use for untrusted input.

```python
# ReDoS-safe alternative
import regex
regex.match(r"(?>a+)+b", "aaaa")  # atomic group
```

**Dense one-liner:** atomic group `(?>...)` or use re2 for untrusted input.

**Complexity:** O(N) with re2; O(2^N) worst case with re.  **Gotcha:** WAFs often rely on regex — bad pattern = ReDoS = full server lockup.

---

### Q.203 — Named capture groups + `re.Pattern.groupdict`
**Companies:** Stripe, Datadog.

**Prose:** `(?P<name>...)` captures by name; `m.groupdict()` returns a dict. Far more maintainable than positional groups.

```python
import re
m = re.match(r"(?P<user>\w+)@(?P<host>[\w.]+)", "ada@example.com")
print(m.groupdict())   # {'user': 'ada', 'host': 'example.com'}
```

**Dense one-liner:** `re.match(r"(?P<x>...)", s).groupdict()`.

**Complexity:** O(N).  **Gotcha:** group names must be valid Python identifiers — hyphens not allowed; dashes in names = `error: bad character`.

---

### Q.204 — String methods that beat regex
**Companies:** Google, Snowflake.

**Prose:** `str.startswith`, `endswith`, `split`, `replace`, `partition` are 10x faster than equivalent regex and clearer. Reach for regex only when you need patterns.

```python
"https://example.com/path".startswith(("http://", "https://"))
"a,b,c".split(",")
"key=value".partition("=")  # ('key','=','value')
```

**Dense one-liner:** plain `str` methods first, regex only if needed.

**Complexity:** O(N).  **Gotcha:** `str.split` with no arg splits on any whitespace (incl. multiple spaces); `str.split(" ")` splits on single space and yields empty strings — different semantics.

---

### Q.205 — Unicode normalisation (NFC/NFD)
**Companies:** Stripe, Google.

**Prose:** `"é"` can be one codepoint (NFC) or two (NFD). Equal visually, unequal as strings. Normalise before compare/hash for user-facing input.

```python
import unicodedata
a = "café"; b = "cafe\u0301"
print(a == b)                                          # False
print(unicodedata.normalize("NFC", a) == unicodedata.normalize("NFC", b))  # True
```

**Dense one-liner:** `unicodedata.normalize("NFC", s)`.

**Complexity:** O(N).  **Gotcha:** identifiers, filenames, and DB lookups all need normalised input — silent dupes otherwise (one user signs up twice with "the same" email).

---

### Q.206 — Encoding/decoding bytes ↔ str
**Companies:** Cloudflare, Stripe.

**Prose:** `bytes.decode("utf-8")` → str. `str.encode("utf-8")` → bytes. Default encoding is UTF-8 in Py3 but always pass explicitly. Handle errors with `errors="strict"|"replace"|"ignore"`.

```python
b = b"caf\xc3\xa9"
print(b.decode("utf-8"))            # "café"
print(b.decode("latin-1"))          # "cafÃ©" — wrong but no error
```

**Dense one-liner:** always pass `encoding=` explicitly.

**Complexity:** O(N).  **Gotcha:** mixing utf-8 and latin-1 silently produces "mojibake" — use `chardet` to detect on import only, then commit to UTF-8 internally.

---

### Q.207 — Format dates: `strftime` / `isoformat` / `fromisoformat`
**Companies:** Stripe, Datadog.

**Prose:** `datetime.now(tz=UTC).isoformat()` for canonical machine format. `strftime` for custom display. `fromisoformat` (3.11+) parses RFC 3339 reliably.

```python
import datetime as dt
now = dt.datetime.now(dt.UTC)
print(now.isoformat())                              # "2026-...+00:00"
print(now.strftime("%Y-%m-%d %H:%M:%S %Z"))
print(dt.datetime.fromisoformat("2026-01-01T00:00:00+00:00"))
```

**Dense one-liner:** `datetime.now(UTC).isoformat()` for logs/APIs.

**Complexity:** O(1).  **Gotcha:** naive datetime (no tzinfo) is the source of every prod time bug; always attach `tz=UTC` at construction.

---

### Q.208 — Parse structured logs / NDJSON
**Companies:** Datadog, Snowflake.

**Prose:** Newline-delimited JSON: one record per line. Parse with stream pattern; handle malformed lines (ship them to a quarantine).

```python
import json

def ndjson(path):
    with open(path) as f:
        for n, line in enumerate(f, 1):
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                print(f"line {n}: {e}")
```

**Dense one-liner:** loop lines, `json.loads(line)` per line, try/except.

**Complexity:** O(N) lines.  **Gotcha:** trailing newline in file produces one empty line — `if not line.strip(): continue`.

---

### Q.209 — Templating: `string.Template` vs. f-strings vs. Jinja
**Companies:** Stripe, Atlassian.

**Prose:** f-strings: code in templates, internal use only. `string.Template` (`$var`) for safe user-supplied templates. Jinja2 for full templating with logic and autoescape.

```python
from string import Template
t = Template("Hello, $name!")
print(t.safe_substitute(name="ada"))
```

**Dense one-liner:** never f-string with untrusted format strings.

**Complexity:** O(N).  **Gotcha:** `f"{user_input}"` is fine, but `eval(f"...{user_input}...")` is RCE — never `eval` formatted strings.

---

### Q.210 — Avoid `eval`/`exec`/`compile` on untrusted input
**Companies:** Stripe, Cloudflare.

**Prose:** `eval(s)` runs arbitrary code. For "safe arithmetic" use `ast.literal_eval` (only literals: numbers, strings, lists, dicts, tuples, booleans, None).

```python
import ast
print(ast.literal_eval("[1, 2, {'a': 3}]"))   # safe
# print(eval("__import__('os').system('rm -rf /')"))  # NEVER
```

**Dense one-liner:** `ast.literal_eval` for safe parsing of literals.

**Complexity:** O(N).  **Gotcha:** `ast.literal_eval` still raises on complex expressions (`1+1` works, `range(3)` doesn't) — by design; never patch around it.

---

## Track B.16 — Data Structures & Integrated Algorithms (Q.211–Q.235)

> Companies: Google, Meta, Amazon, Stripe. Focus: stdlib data structures + ~10 algorithms an SRE-track candidate must still solve crisply (heap, tree, graph, sliding window, two-pointer). Larger algo set lives in Track C appendix.

### Q.211 — `collections.deque` for O(1) ends
**Companies:** Google, Meta.

**Prose:** Deque supports O(1) `appendleft`/`popleft` — list does not. Use for queues, sliding windows, BFS frontiers.

```python
from collections import deque
q = deque(maxlen=3)
for x in [1,2,3,4]: q.append(x)
print(q)  # deque([2,3,4], maxlen=3)
```

**Dense one-liner:** `deque(maxlen=N)` for fixed-size sliding window.

**Complexity:** O(1) ends.  **Gotcha:** `deque[i]` is O(N) random access — wrong DS if you need indexing.

---

### Q.212 — `heapq` for min-heap (top-K, scheduler)
**Companies:** Google, Meta, Amazon.

**Prose:** Stdlib min-heap on a list. `heappush`/`heappop` O(log N). For max-heap, push negated values. `nlargest`/`nsmallest` for top-K.

```python
import heapq
def top_k(xs, k):
    return heapq.nlargest(k, xs)
```

**Dense one-liner:** `heapq.nlargest(k, xs)`.

**Complexity:** O(N log K).  **Gotcha:** `heapq.nlargest(k, xs)` outperforms `sorted(xs)[-k:]` for k << N — but `sorted` is faster when k ≈ N.

---

### Q.213 — `Counter` for frequency tables
**Companies:** Google, Stripe.

**Prose:** `Counter` is a dict subclass; `most_common(n)` returns top-N. Arithmetic on Counters (`+`, `-`, `&`, `|`) is occasionally magical.

```python
from collections import Counter
c = Counter("mississippi")
print(c.most_common(2))  # [('i',4), ('s',4)]
```

**Dense one-liner:** `Counter(iter).most_common(N)`.

**Complexity:** O(N) build, O(N log N) most_common.  **Gotcha:** `Counter.subtract` keeps zero/negative counts; `Counter(a) - Counter(b)` drops them — different semantics.

---

### Q.214 — `defaultdict` for grouping
**Companies:** Google, Meta.

**Prose:** Avoids the `if key not in d: d[key] = []` boilerplate. Pass a factory (`list`, `int`, `set`).

```python
from collections import defaultdict
d = defaultdict(list)
for k, v in [("a",1),("a",2),("b",3)]:
    d[k].append(v)
```

**Dense one-liner:** `defaultdict(list)` for group-by.

**Complexity:** O(N).  **Gotcha:** accessing a missing key **creates** it — printing a defaultdict can mutate it (key inserted with empty value); use `dict(d)` for read-only views.

---

### Q.215 — `bisect` for sorted insertion
**Companies:** Google, Stripe.

**Prose:** `bisect.insort` keeps a list sorted in O(log N) search + O(N) insert. For pure search use `bisect_left`/`bisect_right`. With `key=` (3.10+).

```python
import bisect
xs = [1,3,5,7]
bisect.insort(xs, 4)  # [1,3,4,5,7]
print(bisect.bisect_left(xs, 5))  # 3
```

**Dense one-liner:** `bisect.insort(sorted_list, x)`.

**Complexity:** O(log N) search, O(N) insert.  **Gotcha:** `bisect_left` vs `bisect_right` matters for duplicates — pick deliberately or you get off-by-one.

---

### Q.216 — Two-pointer technique
**Companies:** Google, Meta, Amazon.

**Prose:** Linear-time pattern for sorted arrays: pair sums, palindrome check, container-with-most-water. O(N) instead of O(N²) brute force.

```python
def two_sum_sorted(xs: list[int], target: int) -> tuple[int,int] | None:
    i, j = 0, len(xs)-1
    while i < j:
        s = xs[i] + xs[j]
        if s == target: return (i, j)
        if s < target: i += 1
        else: j -= 1
    return None
```

**Dense one-liner:** sorted + `i,j = 0, len-1`; move based on sum vs. target.

**Complexity:** O(N).  **Gotcha:** requires sorted input — sort cost is O(N log N), so two-pointer "wins" only if data is already sorted or you need many queries.

---

### Q.217 — Sliding window (variable size)
**Companies:** Meta, Amazon, Google.

**Prose:** Maintain window `[l, r]`; expand `r`, shrink `l` on invariant violation. O(N) for "longest substring with K distinct chars" type problems.

```python
def longest_unique(s: str) -> int:
    seen: dict[str,int] = {}; l = 0; best = 0
    for r, c in enumerate(s):
        if c in seen and seen[c] >= l:
            l = seen[c] + 1
        seen[c] = r
        best = max(best, r - l + 1)
    return best
```

**Dense one-liner:** `for r,c in enumerate(s): l = max(l, seen.get(c,-1)+1)`.

**Complexity:** O(N).  **Gotcha:** the "shrink l" condition must be `seen[c] >= l` (within current window), not just `c in seen`.

---

### Q.218 — BFS shortest path on unweighted graph
**Companies:** Meta, Amazon, Google.

**Prose:** Queue + visited set. First time a node is dequeued = shortest path in edges.

```python
from collections import deque

def bfs(adj: dict[int,list[int]], start: int, end: int) -> int:
    q = deque([(start, 0)]); seen = {start}
    while q:
        node, d = q.popleft()
        if node == end: return d
        for nb in adj[node]:
            if nb not in seen:
                seen.add(nb); q.append((nb, d+1))
    return -1
```

**Dense one-liner:** `deque + visited set + (node, distance)` tuple.

**Complexity:** O(V + E).  **Gotcha:** mark visited on **enqueue**, not dequeue — otherwise duplicates get enqueued and complexity blows up.

---

### Q.219 — DFS iterative with explicit stack
**Companies:** Meta, Google.

**Prose:** Recursion hits Python's 1000-frame limit on deep graphs. Iterative DFS uses explicit stack — same logic, no recursion limit.

```python
def dfs(adj: dict[int,list[int]], start: int) -> list[int]:
    stack = [start]; seen = set(); order = []
    while stack:
        node = stack.pop()
        if node in seen: continue
        seen.add(node); order.append(node)
        stack.extend(adj[node])
    return order
```

**Dense one-liner:** `stack=[start]; while stack: node=stack.pop()`.

**Complexity:** O(V + E).  **Gotcha:** `sys.setrecursionlimit(10**6)` is a band-aid — also need OS stack size (`resource.setrlimit(RLIMIT_STACK, ...)`); iterative is safer.

---

### Q.220 — Topological sort (Kahn's algo)
**Companies:** Meta, Amazon, Google.

**Prose:** For DAG ordering (build deps, course prerequisites). Repeatedly remove zero-in-degree nodes.

```python
from collections import deque, defaultdict

def topo(deps: list[tuple[str,str]]) -> list[str]:
    g: dict = defaultdict(list); indeg: dict = defaultdict(int); nodes = set()
    for a, b in deps:
        g[a].append(b); indeg[b] += 1; nodes.update([a,b])
    q = deque([n for n in nodes if indeg[n] == 0])
    out: list[str] = []
    while q:
        n = q.popleft(); out.append(n)
        for m in g[n]:
            indeg[m] -= 1
            if indeg[m] == 0: q.append(m)
    return out if len(out) == len(nodes) else []  # cycle if shorter
```

**Dense one-liner:** Kahn's: queue zero-indeg, decrement neighbours, repeat.

**Complexity:** O(V + E).  **Gotcha:** if final list shorter than node count → cycle exists; never return partial topo without flagging it.

---

### Q.221 — Union-Find (DSU) with path compression
**Companies:** Meta, Google, Amazon.

**Prose:** Near-O(1) `find` and `union`. Used for connectivity, MST (Kruskal), grouping problems.

```python
class DSU:
    def __init__(self, n: int):
        self.p = list(range(n)); self.r = [0]*n
    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]  # path compression
            x = self.p[x]
        return x
    def union(self, a: int, b: int) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb: return False
        if self.r[ra] < self.r[rb]: ra, rb = rb, ra
        self.p[rb] = ra
        if self.r[ra] == self.r[rb]: self.r[ra] += 1
        return True
```

**Dense one-liner:** `find` with iterative compression + `union` by rank.

**Complexity:** ~O(α(N)) ≈ O(1).  **Gotcha:** without path compression OR rank, worst case is O(N) per op — both heuristics matter; one without the other still works but loses the guarantee.

---

### Q.222 — Binary search on answer
**Companies:** Google, Meta, Amazon.

**Prose:** Many "minimum X such that f(X) holds" problems are O(N log V) via binary search on the answer space. Predicate must be monotonic.

```python
def min_capacity(weights: list[int], days: int) -> int:
    def can_ship(cap: int) -> bool:
        d, cur = 1, 0
        for w in weights:
            if cur + w > cap: d += 1; cur = w
            else: cur += w
        return d <= days
    lo, hi = max(weights), sum(weights)
    while lo < hi:
        mid = (lo + hi) // 2
        if can_ship(mid): hi = mid
        else: lo = mid + 1
    return lo
```

**Dense one-liner:** `while lo < hi: mid=(lo+hi)//2; (hi=mid) if pred(mid) else (lo=mid+1)`.

**Complexity:** O(N log V).  **Gotcha:** wrong half-update (`lo = mid` instead of `lo = mid + 1`) causes infinite loop; always test the lower-bound case.

---

### Q.223 — Trie for prefix queries
**Companies:** Google, Meta.

**Prose:** Tree with one node per character; supports O(L) prefix lookup independent of dict size. Used for autocomplete, IP routing tables, spellcheck.

```python
class Trie:
    def __init__(self): self.root: dict = {}
    def insert(self, w: str) -> None:
        node = self.root
        for c in w: node = node.setdefault(c, {})
        node["$"] = True
    def starts_with(self, p: str) -> bool:
        node = self.root
        for c in p:
            if c not in node: return False
            node = node[c]
        return True
```

**Dense one-liner:** nested dict with `$` end marker.

**Complexity:** O(L) per op.  **Gotcha:** memory-heavy for sparse alphabets — for IP/routing use a compressed trie (radix tree) instead.

---

### Q.224 — DP: 1D bottom-up (climbing stairs / coin change)
**Companies:** Google, Meta, Amazon.

**Prose:** Define `dp[i]`, recurrence in terms of smaller `dp[j]`. Bottom-up loop. Coin change min: `dp[a] = min(dp[a-c]+1 for c in coins)`.

```python
def coin_change(coins: list[int], amount: int) -> int:
    INF = amount + 1
    dp = [0] + [INF] * amount
    for a in range(1, amount + 1):
        dp[a] = min((dp[a-c] for c in coins if c <= a), default=INF) + 1
    return dp[amount] if dp[amount] < INF else -1
```

**Dense one-liner:** `dp[a] = min(dp[a-c] for c in coins if c<=a) + 1`.

**Complexity:** O(amount × coins).  **Gotcha:** `default=INF` on `min` for the no-valid-coin case; without it, empty generator raises `ValueError`.

---

### Q.225 — DP: 2D grid (unique paths / edit distance)
**Companies:** Google, Meta.

**Prose:** Edit distance Levenshtein: `dp[i][j] = min(insert, delete, replace)`. Quintessential 2D DP.

```python
def edit_distance(a: str, b: str) -> int:
    n, m = len(a), len(b)
    dp = [[0]*(m+1) for _ in range(n+1)]
    for i in range(n+1): dp[i][0] = i
    for j in range(m+1): dp[0][j] = j
    for i in range(1, n+1):
        for j in range(1, m+1):
            if a[i-1] == b[j-1]: dp[i][j] = dp[i-1][j-1]
            else: dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])
    return dp[n][m]
```

**Dense one-liner:** `dp[i][j] = dp[i-1][j-1] if same else 1+min(3 neighbours)`.

**Complexity:** O(N×M).  **Gotcha:** can be optimised to O(min(N,M)) memory using two rows — interview bonus point.

---

### Q.226 — In-order traversal of BST (iterative)
**Companies:** Google, Meta.

**Prose:** Yields keys in sorted order. Iterative version avoids recursion limit.

```python
class Node:
    def __init__(self, v, l=None, r=None): self.v, self.l, self.r = v, l, r

def inorder(root):
    stack: list = []; node = root; out = []
    while stack or node:
        while node:
            stack.append(node); node = node.l
        node = stack.pop(); out.append(node.v); node = node.r
    return out
```

**Dense one-liner:** push lefts, pop, visit, go right.

**Complexity:** O(N).  **Gotcha:** mistake `node = node.l` order before `stack.pop` — produces wrong order; always go all the way left first.

---

### Q.227 — LRU cache from scratch (OrderedDict-free)
**Companies:** Meta, Stripe, Amazon.

**Prose:** Doubly-linked list + dict. `get`/`put` O(1). Common interview question; OrderedDict is the easy answer, manual DLL is the rigorous one.

```python
class LRU:
    class N:
        __slots__ = ("k","v","p","n")
        def __init__(self,k,v): self.k=k; self.v=v; self.p=None; self.n=None
    def __init__(self, cap: int):
        self.cap = cap; self.m: dict = {}
        self.h = self.N(0,0); self.t = self.N(0,0)
        self.h.n = self.t; self.t.p = self.h
    def _add(self, n):
        n.p = self.h; n.n = self.h.n; self.h.n.p = n; self.h.n = n
    def _rem(self, n):
        n.p.n = n.n; n.n.p = n.p
    def get(self, k):
        if k not in self.m: return -1
        n = self.m[k]; self._rem(n); self._add(n); return n.v
    def put(self, k, v):
        if k in self.m: self._rem(self.m[k])
        n = self.N(k,v); self._add(n); self.m[k] = n
        if len(self.m) > self.cap:
            lru = self.t.p; self._rem(lru); del self.m[lru.k]
```

**Dense one-liner:** dict + DLL; head=MRU, tail=LRU.

**Complexity:** O(1) get/put.  **Gotcha:** sentinel head/tail nodes simplify edge cases — null checks at boundaries are where DLL bugs hide.

---

### Q.228 — Detect cycle in linked list (Floyd's)
**Companies:** Meta, Amazon, Google.

**Prose:** Slow + fast pointers. If they meet, cycle exists. To find cycle start: reset one to head, advance both by 1.

```python
class Node:
    def __init__(self, v, n=None): self.v=v; self.n=n

def has_cycle(head) -> bool:
    slow = fast = head
    while fast and fast.n:
        slow = slow.n; fast = fast.n.n
        if slow is fast: return True
    return False
```

**Dense one-liner:** tortoise + hare; meet ⇒ cycle.

**Complexity:** O(N), O(1) memory.  **Gotcha:** `fast and fast.n` order matters — `fast.n.n` AttributeErrors if `fast.n is None` and not guarded.

---

### Q.229 — Merge K sorted lists with heapq
**Companies:** Amazon, Google, Meta.

**Prose:** Push (val, idx, node) into heap; pop smallest, push next from same list. O(N log K).

```python
import heapq
class Node:
    def __init__(self, v, n=None): self.v=v; self.n=n

def merge_k(lists: list) -> list:
    h = [(node.v, i, node) for i, node in enumerate(lists) if node]
    heapq.heapify(h)
    out: list = []
    while h:
        v, i, node = heapq.heappop(h)
        out.append(v)
        if node.n: heapq.heappush(h, (node.n.v, i, node.n))
    return out
```

**Dense one-liner:** heap of `(val, list_idx, node)`; pop, advance, push.

**Complexity:** O(N log K).  **Gotcha:** the `i` (list index) breaks ties when values are equal — without it, heap compares Node objects and crashes with TypeError.

---

### Q.230 — Median of a stream (two heaps)
**Companies:** Meta, Amazon.

**Prose:** Max-heap for lower half, min-heap for upper half. Balance sizes; median = top(s).

```python
import heapq

class Median:
    def __init__(self): self.lo: list = []; self.hi: list = []  # lo = max-heap (negated)
    def add(self, x: int) -> None:
        heapq.heappush(self.lo, -heapq.heappushpop(self.hi, x))
        if len(self.lo) > len(self.hi):
            heapq.heappush(self.hi, -heapq.heappop(self.lo))
    def median(self) -> float:
        if len(self.hi) > len(self.lo): return self.hi[0]
        return (self.hi[0] - self.lo[0]) / 2
```

**Dense one-liner:** max-heap (negated) + min-heap; balance + read tops.

**Complexity:** O(log N) add, O(1) median.  **Gotcha:** Python's heapq is min-only; max-heap = negate on push and pop; forget the negation = wrong median.

---

### Q.231 — Number of islands (grid DFS/BFS)
**Companies:** Amazon, Meta, Google.

**Prose:** Grid of '1'/'0'; count connected components. DFS each unvisited land cell, sink it to '0'.

```python
def num_islands(grid: list[list[str]]) -> int:
    if not grid: return 0
    R, C = len(grid), len(grid[0]); n = 0
    def sink(r,c):
        if r<0 or c<0 or r>=R or c>=C or grid[r][c] != "1": return
        grid[r][c] = "0"
        for dr, dc in ((1,0),(-1,0),(0,1),(0,-1)): sink(r+dr, c+dc)
    for r in range(R):
        for c in range(C):
            if grid[r][c] == "1": n += 1; sink(r,c)
    return n
```

**Dense one-liner:** DFS each '1', sink to '0', count starts.

**Complexity:** O(R×C).  **Gotcha:** large grids hit recursion limit — convert to iterative DFS or BFS.

---

### Q.232 — Subarray sum equals K (prefix sum + dict)
**Companies:** Meta, Amazon.

**Prose:** Track `prefix[i]`; for each i, count seen prefixes equal to `prefix[i] - k`. O(N).

```python
def subarray_sum(nums: list[int], k: int) -> int:
    seen: dict = {0: 1}; total = pref = 0
    for x in nums:
        pref += x
        total += seen.get(pref - k, 0)
        seen[pref] = seen.get(pref, 0) + 1
    return total
```

**Dense one-liner:** `total += seen.get(pref-k, 0); seen[pref] += 1`.

**Complexity:** O(N).  **Gotcha:** initialise `seen = {0: 1}` for the prefix-equals-k case; without it, single-element matches are missed.

---

### Q.233 — Word ladder (BFS over word graph)
**Companies:** Amazon, Meta.

**Prose:** Each "edge" = words differing by one letter. BFS from start, count steps to end. Pattern key (`h*t` for `hot`) speeds neighbour lookup.

```python
from collections import defaultdict, deque

def ladder(begin: str, end: str, words: list[str]) -> int:
    if end not in words: return 0
    L = len(begin); patt = defaultdict(list)
    for w in words:
        for i in range(L): patt[w[:i]+"*"+w[i+1:]].append(w)
    q = deque([(begin, 1)]); seen = {begin}
    while q:
        w, d = q.popleft()
        if w == end: return d
        for i in range(L):
            for nb in patt[w[:i]+"*"+w[i+1:]]:
                if nb not in seen:
                    seen.add(nb); q.append((nb, d+1))
    return 0
```

**Dense one-liner:** pattern map `h*t -> [hot,hat]` + BFS.

**Complexity:** O(N × L²).  **Gotcha:** without pattern map you scan all words per step → O(N²×L); pattern reduces to O(N×L²).

---

### Q.234 — Reservoir sampling (k items from stream of unknown size)
**Companies:** Meta, Stripe, Snowflake.

**Prose:** For each item i ≥ k, replace random slot with prob k/i. Provably uniform sample. Used for log sampling, A/B traffic.

```python
import random

def reservoir(stream, k: int) -> list:
    sample: list = []
    for i, x in enumerate(stream):
        if i < k: sample.append(x)
        else:
            j = random.randint(0, i)
            if j < k: sample[j] = x
    return sample
```

**Dense one-liner:** `if random.randint(0,i) < k: sample[j] = x`.

**Complexity:** O(N).  **Gotcha:** off-by-one: `randint(0, i)` is **inclusive** in Python — that's the correct range; `randrange(0, i+1)` is equivalent.

---

### Q.235 — Find K closest points to origin (heap vs. quickselect)
**Companies:** Amazon, Meta, Google.

**Prose:** Heap: O(N log K). Quickselect: O(N) average, O(N²) worst. Heap simpler; quickselect when you need optimal.

```python
import heapq

def k_closest(points: list[list[int]], k: int) -> list[list[int]]:
    return heapq.nsmallest(k, points, key=lambda p: p[0]**2 + p[1]**2)
```

**Dense one-liner:** `heapq.nsmallest(k, points, key=dist)`.

**Complexity:** O(N log K).  **Gotcha:** `key=` for `nsmallest`/`nlargest` was added in 3.4 — fine everywhere now, but exists.

---

## Track B.17 — Python Gotchas & Footguns (Q.236–Q.248)

> Companies: every interviewer ever. The questions designed to trip up "Python developers" who don't actually know Python.

### Q.236 — Mutable default arguments
**Companies:** Stripe, Google.

**Prose:** `def f(x=[])` creates the list **once** at def time — all calls share it. Use `None` sentinel + `x = x or []`.

```python
def bad(x=[]): x.append(1); return x
print(bad()); print(bad())  # [1], [1,1] — surprise

def good(x=None):
    x = x if x is not None else []
    x.append(1); return x
```

**Dense one-liner:** never mutable default; use `None` + assign.

**Complexity:** O(1).  **Gotcha:** linters catch this (B006); still appears in legacy code constantly.

---

### Q.237 — Late binding in closures
**Companies:** Google, Meta.

**Prose:** Closures capture the **variable**, not its value. Fix with default-arg trick or partial.

```python
fns = [lambda: i for i in range(3)]
print([f() for f in fns])  # [2,2,2]

fns = [lambda i=i: i for i in range(3)]
print([f() for f in fns])  # [0,1,2]
```

**Dense one-liner:** `lambda x=x: ...`.

**Complexity:** O(N).  **Gotcha:** same trap with nested `def`, not just lambdas.

---

### Q.238 — `is` vs. `==` (and the small-int cache)
**Companies:** Google, Meta.

**Prose:** `is` checks identity; `==` checks value. CPython caches small ints (-5 to 256) and short strings → `is` "works" by accident.

```python
a = 256; b = 256; print(a is b)  # True (cached)
a = 257; b = 257; print(a is b)  # False (not cached)
```

**Dense one-liner:** `==` for value, `is` only for `None`/`True`/`False`/sentinels.

**Complexity:** O(1).  **Gotcha:** `if x is 0:` works in REPL, fails in non-trivial code; flake8 warns (E711/E712).

---

### Q.239 — Integer division `/` vs. `//` and floats
**Companies:** Stripe, Google.

**Prose:** `/` always returns float in Py3. `//` floor-divides; for negative results it floors **down** (`-1 // 2 == -1`, not 0).

```python
print(7 / 2)    # 3.5
print(7 // 2)   # 3
print(-7 // 2)  # -4 (not -3)
```

**Dense one-liner:** `//` floors toward negative infinity.

**Complexity:** O(1).  **Gotcha:** for "round toward zero" use `int(a/b)` (with float caveat) or `math.trunc(a/b)`.

---

### Q.240 — Floating point comparison
**Companies:** Stripe, Snowflake.

**Prose:** `0.1 + 0.2 != 0.3`. Use `math.isclose(a, b)` for tolerant compare. For money use `Decimal`, never float.

```python
import math
print(0.1 + 0.2)                    # 0.30000000000000004
print(math.isclose(0.1+0.2, 0.3))  # True
```

**Dense one-liner:** `math.isclose(a, b, rel_tol=1e-9)` for floats; `Decimal` for money.

**Complexity:** O(1).  **Gotcha:** `Decimal("0.1") + Decimal("0.2") == Decimal("0.3")` — exact, but `Decimal(0.1)` (from float) inherits the imprecision.

---

### Q.241 — `for ... else`
**Companies:** Google.

**Prose:** `else` on a for-loop runs if the loop **completed without break**. Useful for "search and act if not found" patterns.

```python
for x in items:
    if x == target:
        print("found"); break
else:
    print("not found")
```

**Dense one-liner:** `for ... else: # ran if no break`.

**Complexity:** O(N).  **Gotcha:** every team includes someone who reads it as "else if loop didn't run" (it's the opposite); usually clearer to refactor with a flag or function return.

---

### Q.242 — `try/except/else/finally` semantics
**Companies:** Stripe, Atlassian.

**Prose:** `else` runs only if no exception; `finally` runs always. `else` makes "happy path" code clearer (and avoids accidentally catching exceptions raised by it).

```python
try:
    x = parse()
except ValueError:
    handle()
else:
    use(x)        # only if parse didn't raise
finally:
    cleanup()
```

**Dense one-liner:** `else` = no exception; `finally` = always.

**Complexity:** O(1).  **Gotcha:** `return` in `finally` swallows exceptions and overrides any other return — never `return` from `finally`.

---

### Q.243 — Variable scope: LEGB
**Companies:** Google, Meta.

**Prose:** Local → Enclosing → Global → Built-in. `global x` to assign to module scope; `nonlocal x` to assign to enclosing function scope.

```python
x = "global"
def outer():
    x = "outer"
    def inner():
        nonlocal x
        x = "inner"
    inner(); print(x)  # "inner"
outer()
```

**Dense one-liner:** `nonlocal` for enclosing, `global` for module.

**Complexity:** O(1).  **Gotcha:** assignment creates a local — `def f(): x = x + 1` raises `UnboundLocalError` even if `x` is global; need `global x` first.

---

### Q.244 — Chained comparison (`1 < x < 10`)
**Companies:** Google, Stripe.

**Prose:** Pythonic and short-circuits — `a < b < c` evaluates `b` once. Avoids `(a < b) and (b < c)` boilerplate.

```python
x = 5
print(1 < x < 10)        # True
print(0 < x == 5 < 10)   # True (yes, mixed comparisons work)
```

**Dense one-liner:** `lo < x < hi`.

**Complexity:** O(1).  **Gotcha:** `1 < x > 5` is technically valid but readers misread it — keep chains monotonic.

---

### Q.245 — Walrus operator `:=` (3.8+)
**Companies:** Stripe, Cloudflare.

**Prose:** Assign-and-use in expressions. Cleans up "compute then test" idioms.

```python
import re
if (m := re.match(r"(\d+)", "abc123")):
    print(m.group(1))

while chunk := f.read(4096):
    process(chunk)
```

**Dense one-liner:** `while chunk := f.read(N): ...`.

**Complexity:** O(1).  **Gotcha:** binding leaks to the surrounding scope (in `if`/`while` body), not just the expression — easy to misread.

---

### Q.246 — `*args` and `**kwargs` ordering
**Companies:** Google, Stripe.

**Prose:** Signature order: positional, `*args`, keyword-only (after `*`), `**kwargs`. PEP 3102 keyword-only args after `*` enforce explicit naming.

```python
def f(a, b, *args, c, d=10, **kw):
    return a, b, args, c, d, kw

f(1, 2, 3, 4, c=5, x=6)  # c is keyword-only
```

**Dense one-liner:** `def f(a, b, *args, kw_only, **kw): ...`.

**Complexity:** O(1).  **Gotcha:** `def f(a, /, b, *, c)` — `/` for positional-only (3.8+), `*` for keyword-only; mix unlocks API design clarity.

---

### Q.247 — Iterating + modifying a list (the silent skip)
**Companies:** Stripe, Google.

**Prose:** `for x in xs: if cond: xs.remove(x)` skips elements. Iterate over a copy or build a new list.

```python
xs = [1,2,3,4]
for x in xs:
    if x == 2: xs.remove(x)
print(xs)  # [1,3,4] sometimes; depends on case

# safe
xs = [x for x in xs if x != 2]
```

**Dense one-liner:** `xs[:] = [x for x in xs if pred(x)]`.

**Complexity:** O(N).  **Gotcha:** silent — no exception; just wrong output. Linters flag it (B038).

---

### Q.248 — Garbage collection and cycle collector
**Companies:** Snowflake, Cloudflare.

**Prose:** CPython uses refcounting + cycle collector. Cycles with `__del__` were not collectable before 3.4; now are. Hot loops can disable GC for predictable latency.

```python
import gc
gc.disable()  # no auto cycle collection in this section
try:
    hot_loop()
finally:
    gc.enable(); gc.collect()
```

**Dense one-liner:** `gc.disable()` for hot path; `gc.collect()` later.

**Complexity:** O(N) on collect.  **Gotcha:** `gc.disable()` doesn't disable refcount-based cleanup — only cycle detection; pure refcount work still happens every dec.

---

# Track C — Algorithms Appendix (Q.249–Q.298)

> Companies: Google, Meta, Amazon, Microsoft, Apple, ByteDance, Stripe. The 50-question canonical FAANG algorithm warm-up. Format here is tighter than Tracks A/B — algos are pattern-recall under time pressure, not extended discussion.

## C.18.1 — Arrays & Strings (Q.249–Q.262)

### Q.249 — Two Sum
**Companies:** Amazon, Google.

**Prose:** Hash map of seen values → index; for each x, look up `target - x`. O(N).

```python
def two_sum(nums: list[int], target: int) -> list[int]:
    seen: dict[int, int] = {}
    for i, x in enumerate(nums):
        if (j := seen.get(target - x)) is not None: return [j, i]
        seen[x] = i
    return []
```

**Dense one-liner:** `seen={}; for i,x: if target-x in seen: return [seen[target-x], i]; seen[x]=i`.

**Complexity:** O(N) time, O(N) space.  **Gotcha:** record `seen[x] = i` AFTER the lookup, or `[3,3]` with target 6 returns `[0,0]`.

---

### Q.250 — Best Time to Buy/Sell Stock (single transaction)
**Companies:** Amazon, Google.

**Prose:** Track running min; profit at i = price[i] - min so far. O(N).

```python
def max_profit(prices: list[int]) -> int:
    lo, best = float("inf"), 0
    for p in prices:
        lo = min(lo, p); best = max(best, p - lo)
    return best
```

**Dense one-liner:** `lo=min(lo,p); best=max(best,p-lo)`.

**Complexity:** O(N).  **Gotcha:** initialise `best=0` not `-inf` — if prices monotonic decreasing, no transaction = 0 profit.

---

### Q.251 — Maximum Subarray (Kadane)
**Companies:** Amazon, Meta.

**Prose:** Running sum; reset when sum goes negative. O(N).

```python
def max_subarray(nums: list[int]) -> int:
    cur = best = nums[0]
    for x in nums[1:]:
        cur = max(x, cur + x); best = max(best, cur)
    return best
```

**Dense one-liner:** `cur = max(x, cur+x); best = max(best, cur)`.

**Complexity:** O(N).  **Gotcha:** all-negative input → answer is the largest single element; Kadane handles it because of `max(x, cur+x)`.

---

### Q.252 — Product of Array Except Self
**Companies:** Amazon, Meta.

**Prose:** No division. Two passes: prefix products left, then multiply by suffix product on the right.

```python
def product_except_self(nums: list[int]) -> list[int]:
    n = len(nums); out = [1] * n
    p = 1
    for i in range(n): out[i] = p; p *= nums[i]
    p = 1
    for i in range(n-1, -1, -1): out[i] *= p; p *= nums[i]
    return out
```

**Dense one-liner:** prefix pass + suffix pass, both O(1) extra.

**Complexity:** O(N), O(1) extra (output not counted).  **Gotcha:** division-based solution fails on zero elements.

---

### Q.253 — Container With Most Water
**Companies:** Meta, Amazon.

**Prose:** Two pointers from ends; move the shorter side inward.

```python
def max_area(height: list[int]) -> int:
    i, j, best = 0, len(height)-1, 0
    while i < j:
        best = max(best, (j-i) * min(height[i], height[j]))
        if height[i] < height[j]: i += 1
        else: j -= 1
    return best
```

**Dense one-liner:** two pointers; move shorter side.

**Complexity:** O(N).  **Gotcha:** moving the **taller** side never improves area (width shrinks, height capped); proof matters in interview follow-ups.

---

### Q.254 — Longest Substring Without Repeating Characters
**Companies:** Amazon, Meta, Google.

**Prose:** Sliding window with last-seen index map; advance left to `max(left, last[c]+1)`.

```python
def longest(s: str) -> int:
    last: dict[str,int] = {}; l = best = 0
    for r, c in enumerate(s):
        if c in last and last[c] >= l: l = last[c] + 1
        last[c] = r
        best = max(best, r - l + 1)
    return best
```

**Dense one-liner:** `l = max(l, last.get(c,-1)+1)`.

**Complexity:** O(N).  **Gotcha:** the `last[c] >= l` check is critical — `c` outside current window doesn't shrink it.

---

### Q.255 — Group Anagrams
**Companies:** Amazon, Meta.

**Prose:** Key by sorted-letter tuple; bucket into dict.

```python
from collections import defaultdict

def group(strs: list[str]) -> list[list[str]]:
    g: dict = defaultdict(list)
    for s in strs: g[tuple(sorted(s))].append(s)
    return list(g.values())
```

**Dense one-liner:** `g[tuple(sorted(s))].append(s)`.

**Complexity:** O(N × K log K).  **Gotcha:** for unicode-heavy input, `Counter` is O(K) — beats sorted; depends on alphabet.

---

### Q.256 — Valid Anagram
**Companies:** Amazon.

**Prose:** Counter equality.

```python
from collections import Counter
def is_anagram(a: str, b: str) -> bool:
    return Counter(a) == Counter(b)
```

**Dense one-liner:** `Counter(a) == Counter(b)`.

**Complexity:** O(N).  **Gotcha:** unicode normalisation needed if strings come from user input.

---

### Q.257 — Valid Palindrome (alphanumeric only)
**Companies:** Meta.

**Prose:** Two pointers; skip non-alphanumeric; case-insensitive compare.

```python
def is_pal(s: str) -> bool:
    i, j = 0, len(s)-1
    while i < j:
        while i < j and not s[i].isalnum(): i += 1
        while i < j and not s[j].isalnum(): j -= 1
        if s[i].lower() != s[j].lower(): return False
        i += 1; j -= 1
    return True
```

**Dense one-liner:** filter+lower then `t == t[::-1]` (slower).

**Complexity:** O(N).  **Gotcha:** `isalnum()` is unicode-aware — accents, digits in non-Latin scripts pass; locale-dependent behaviour.

---

### Q.258 — Longest Palindromic Substring (expand from center)
**Companies:** Amazon, Meta.

**Prose:** Try each index as a center (odd) and each gap (even); expand while equal. O(N²).

```python
def longest_pal(s: str) -> str:
    def grow(l, r):
        while l >= 0 and r < len(s) and s[l] == s[r]: l -= 1; r += 1
        return s[l+1:r]
    best = ""
    for i in range(len(s)):
        for cand in (grow(i,i), grow(i,i+1)):
            if len(cand) > len(best): best = cand
    return best
```

**Dense one-liner:** expand from each center, odd + even.

**Complexity:** O(N²).  **Gotcha:** Manacher's gives O(N) but is rarely required; mention it but don't implement unless asked.

---

### Q.259 — String to Integer (atoi)
**Companies:** Amazon, ByteDance.

**Prose:** Strip whitespace, optional sign, digit run, clamp to 32-bit range.

```python
def my_atoi(s: str) -> int:
    s = s.lstrip()
    if not s: return 0
    sign = 1; i = 0
    if s[0] in "+-":
        sign = -1 if s[0] == "-" else 1; i = 1
    n = 0
    while i < len(s) and s[i].isdigit():
        n = n*10 + int(s[i]); i += 1
    n *= sign
    return max(-2**31, min(2**31 - 1, n))
```

**Dense one-liner:** strip → sign → digits → clamp.

**Complexity:** O(N).  **Gotcha:** the spec is in the bug — leading whitespace yes, embedded no; "  +0 12" returns 0.

---

### Q.260 — Implement strStr / `find`
**Companies:** Amazon, Meta.

**Prose:** Naïve O(N×M); KMP O(N+M). Stdlib `s.find(needle)` is C-implemented and usually best.

```python
def strstr(h: str, n: str) -> int:
    return h.find(n)
```

**Dense one-liner:** `haystack.find(needle)`.

**Complexity:** Python stdlib uses Two-Way; near linear.  **Gotcha:** in interview, "implement KMP" means show the failure-function — not just `find`.

---

### Q.261 — Rotate Array (in place, k steps)
**Companies:** Amazon, Microsoft.

**Prose:** Reverse all, reverse first k, reverse rest. O(N), O(1) memory.

```python
def rotate(nums: list[int], k: int) -> None:
    k %= len(nums)
    nums.reverse(); nums[:k] = reversed(nums[:k]); nums[k:] = reversed(nums[k:])
```

**Dense one-liner:** triple reverse.

**Complexity:** O(N), O(1).  **Gotcha:** `k %= len` is mandatory; otherwise large k = wasted work.

---

### Q.262 — Move Zeroes (in place, preserve order)
**Companies:** Meta, Amazon.

**Prose:** Two pointers: write index for non-zero, then fill rest with zero.

```python
def move_zeroes(nums: list[int]) -> None:
    w = 0
    for x in nums:
        if x != 0: nums[w] = x; w += 1
    for i in range(w, len(nums)): nums[i] = 0
```

**Dense one-liner:** write-pointer for non-zero, fill rest.

**Complexity:** O(N), O(1).  **Gotcha:** swap-based variant looks elegant but does ~2x the writes; write-then-fill is faster.

---

## C.18.2 — Linked Lists (Q.263–Q.268)

### Q.263 — Reverse Linked List
**Companies:** Amazon, Meta.

**Prose:** Three-pointer iteration: prev, curr, next.

```python
class N:
    def __init__(self, v, n=None): self.v=v; self.n=n

def reverse(head):
    prev = None; curr = head
    while curr:
        curr.n, prev, curr = prev, curr, curr.n
    return prev
```

**Dense one-liner:** `curr.n, prev, curr = prev, curr, curr.n`.

**Complexity:** O(N), O(1).  **Gotcha:** recursive variant is elegant but blows stack on long lists.

---

### Q.264 — Merge Two Sorted Lists
**Companies:** Amazon, Meta.

**Prose:** Dummy head + two pointers.

```python
class N:
    def __init__(self, v, n=None): self.v=v; self.n=n

def merge(a, b):
    dummy = N(0); tail = dummy
    while a and b:
        if a.v <= b.v: tail.n, a = a, a.n
        else: tail.n, b = b, b.n
        tail = tail.n
    tail.n = a or b
    return dummy.n
```

**Dense one-liner:** dummy head + walk both.

**Complexity:** O(N+M).  **Gotcha:** `tail.n = a or b` for the leftover tail — both could be empty; works because of short-circuit.

---

### Q.265 — Remove Nth Node From End
**Companies:** Amazon.

**Prose:** Two pointers, fast leads by n; when fast hits end, slow is at predecessor.

```python
def remove_nth(head, n: int):
    dummy = type(head)(0, head); fast = slow = dummy
    for _ in range(n): fast = fast.n
    while fast.n: fast = fast.n; slow = slow.n
    slow.n = slow.n.n
    return dummy.n
```

**Dense one-liner:** fast pointer leads by n; advance both until fast.n is None.

**Complexity:** O(N).  **Gotcha:** dummy head simplifies removing the original head — without it, n == length is a special case.

---

### Q.266 — Linked List Cycle II (find start)
**Companies:** Amazon, Meta.

**Prose:** Floyd until meet; reset slow to head, advance both by 1; meet again at cycle start.

```python
def cycle_start(head):
    slow = fast = head
    while fast and fast.n:
        slow = slow.n; fast = fast.n.n
        if slow is fast:
            slow = head
            while slow is not fast:
                slow = slow.n; fast = fast.n
            return slow
    return None
```

**Dense one-liner:** Floyd find + reset slow to head.

**Complexity:** O(N).  **Gotcha:** the math is non-obvious — interview tip: cite the proof exists (distance from head to start = distance from meet point to start when traversed at speed 1).

---

### Q.267 — Add Two Numbers (digits as linked list)
**Companies:** Amazon, Meta.

**Prose:** Walk both, carry over. Dummy head.

```python
def add(a, b):
    dummy = type(a)(0); tail = dummy; carry = 0
    while a or b or carry:
        s = (a.v if a else 0) + (b.v if b else 0) + carry
        carry, d = divmod(s, 10)
        tail.n = type(a)(d); tail = tail.n
        a = a.n if a else None; b = b.n if b else None
    return dummy.n
```

**Dense one-liner:** loop while a or b or carry; `divmod(sum, 10)`.

**Complexity:** O(max(N,M)).  **Gotcha:** don't forget the `or carry` in loop condition — `9+1` = 10 carries one extra digit.

---

### Q.268 — Copy List With Random Pointer
**Companies:** Amazon, Meta.

**Prose:** Hash original → copy node; second pass to wire `n` and `random`.

```python
def copy(head):
    if not head: return None
    m: dict = {}
    cur = head
    while cur: m[cur] = type(cur)(cur.v); cur = cur.n
    cur = head
    while cur:
        m[cur].n = m.get(cur.n)
        m[cur].random = m.get(cur.random)
        cur = cur.n
    return m[head]
```

**Dense one-liner:** hash original→copy, then wire both pointers.

**Complexity:** O(N), O(N) space.  **Gotcha:** O(1) variant interleaves copies into the list — clever but hard to debug under time pressure; do the dict version unless asked.

---

## C.18.3 — Trees (Q.269–Q.276)

### Q.269 — Maximum Depth of Binary Tree
**Companies:** Amazon, Meta.

**Prose:** Recursion: `1 + max(left, right)`.

```python
def depth(root):
    return 0 if not root else 1 + max(depth(root.l), depth(root.r))
```

**Dense one-liner:** `0 if not root else 1+max(depth(L), depth(R))`.

**Complexity:** O(N).  **Gotcha:** very unbalanced trees can hit recursion limit (~1000 by default).

---

### Q.270 — Validate BST (in-order strict increasing)
**Companies:** Amazon, Meta, Google.

**Prose:** In-order traversal of BST is sorted; check strict increase, or pass min/max bounds down recursively.

```python
def valid_bst(root, lo=float("-inf"), hi=float("inf")) -> bool:
    if not root: return True
    if not (lo < root.v < hi): return False
    return valid_bst(root.l, lo, root.v) and valid_bst(root.r, root.v, hi)
```

**Dense one-liner:** recurse with `(lo, hi)` bounds.

**Complexity:** O(N).  **Gotcha:** `<=` vs `<` matters per spec — strict BST disallows duplicates.

---

### Q.271 — Same Tree
**Companies:** Amazon.

**Prose:** Recursive structural compare.

```python
def same(a, b) -> bool:
    if not a and not b: return True
    if not a or not b: return False
    return a.v == b.v and same(a.l, b.l) and same(a.r, b.r)
```

**Dense one-liner:** recursive struct compare.

**Complexity:** O(N).  **Gotcha:** None checks must come before value compare.

---

### Q.272 — Lowest Common Ancestor (BST)
**Companies:** Amazon, Meta.

**Prose:** Walk down; if both targets less than node → go left; both greater → right; else split = LCA.

```python
def lca(root, p, q):
    while root:
        if p.v < root.v > q.v: root = root.l
        elif p.v > root.v < q.v: root = root.r
        else: return root
```

**Dense one-liner:** descend until split point.

**Complexity:** O(H) height.  **Gotcha:** for general binary tree (not BST), need recursive `lca` returning bubble-up — different problem.

---

### Q.273 — LCA (general binary tree)
**Companies:** Meta, Amazon.

**Prose:** Recurse left/right; if both return non-null, current node is LCA.

```python
def lca(root, p, q):
    if not root or root is p or root is q: return root
    L = lca(root.l, p, q); R = lca(root.r, p, q)
    return root if L and R else L or R
```

**Dense one-liner:** `return root if L and R else L or R`.

**Complexity:** O(N).  **Gotcha:** assumes both p and q exist — if one is missing the function returns the other (silent bug).

---

### Q.274 — Serialize/Deserialize Binary Tree
**Companies:** Amazon, Meta.

**Prose:** Pre-order with `#` for null; deserialise from iterator.

```python
def ser(root) -> str:
    out = []
    def go(n):
        if not n: out.append("#"); return
        out.append(str(n.v)); go(n.l); go(n.r)
    go(root); return ",".join(out)

def des(s: str):
    it = iter(s.split(","))
    def go():
        v = next(it)
        if v == "#": return None
        n = type(_)(int(v)); n.l = go(); n.r = go(); return n
    return go()
```

**Dense one-liner:** pre-order with null marker, recursive parse.

**Complexity:** O(N).  **Gotcha:** must use iterator (single-pass) on deserialise — index-based recursion gets order wrong.

---

### Q.275 — Binary Tree Level Order Traversal
**Companies:** Amazon, Meta.

**Prose:** BFS with queue, snapshot level size each iteration.

```python
from collections import deque
def levels(root):
    if not root: return []
    q = deque([root]); out = []
    while q:
        out.append([n.v for n in q])
        q = deque(c for n in q for c in (n.l, n.r) if c)
    return out
```

**Dense one-liner:** snapshot level then expand to children.

**Complexity:** O(N).  **Gotcha:** rebuilding `q` from comprehension drops the level demarcation — this version captures values first, then re-derives the queue cleanly.

---

### Q.276 — Diameter of Binary Tree
**Companies:** Meta, Amazon.

**Prose:** At each node, diameter through it = depth(L) + depth(R). Track global max.

```python
def diameter(root) -> int:
    best = 0
    def depth(n):
        nonlocal best
        if not n: return 0
        L = depth(n.l); R = depth(n.r)
        best = max(best, L + R)
        return 1 + max(L, R)
    depth(root); return best
```

**Dense one-liner:** post-order; at each node update `max(L+R)`.

**Complexity:** O(N).  **Gotcha:** "diameter" is **edges**, not nodes — `L+R` (not `L+R+1`); easy to misremember.

---

## C.18.4 — Graphs (Q.277–Q.282)

### Q.277 — Clone Graph
**Companies:** Meta, Amazon.

**Prose:** DFS/BFS with visited dict mapping original → clone.

```python
def clone(node):
    if not node: return None
    m: dict = {}
    def dfs(n):
        if n in m: return m[n]
        c = type(n)(n.v); m[n] = c
        c.neighbors = [dfs(nb) for nb in n.neighbors]
        return c
    return dfs(node)
```

**Dense one-liner:** dict mapping original→clone + recursive copy.

**Complexity:** O(V+E).  **Gotcha:** insert into `m` **before** recursing on neighbours — otherwise cycles cause infinite recursion.

---

### Q.278 — Course Schedule (cycle in directed graph)
**Companies:** Meta, Amazon.

**Prose:** DFS with three-colour marking (white/gray/black) detects back edges.

```python
def can_finish(n: int, prereqs: list[list[int]]) -> bool:
    g: list = [[] for _ in range(n)]
    for a, b in prereqs: g[b].append(a)
    state = [0] * n  # 0=unseen, 1=visiting, 2=done
    def dfs(u):
        if state[u] == 1: return False
        if state[u] == 2: return True
        state[u] = 1
        for v in g[u]:
            if not dfs(v): return False
        state[u] = 2; return True
    return all(dfs(i) for i in range(n))
```

**Dense one-liner:** three-colour DFS; `state[u]==1` on revisit ⇒ cycle.

**Complexity:** O(V+E).  **Gotcha:** Kahn's BFS topo-sort works equally well — simpler iterative; pick whichever you can write fast.

---

### Q.279 — Number of Connected Components (undirected)
**Companies:** Amazon, Meta.

**Prose:** DFS each unvisited node; count starts. Or DSU.

```python
def components(n: int, edges: list[list[int]]) -> int:
    g: list = [[] for _ in range(n)]
    for a, b in edges: g[a].append(b); g[b].append(a)
    seen = [False] * n; count = 0
    def dfs(u):
        seen[u] = True
        for v in g[u]:
            if not seen[v]: dfs(v)
    for i in range(n):
        if not seen[i]: count += 1; dfs(i)
    return count
```

**Dense one-liner:** for each unseen node, DFS and bump count.

**Complexity:** O(V+E).  **Gotcha:** DSU also O(V+E) but with α(N) constant — choose by familiarity.

---

### Q.280 — Pacific Atlantic Water Flow
**Companies:** Amazon, Meta.

**Prose:** BFS from each ocean's borders inward (cells reachable from ocean by going uphill). Intersection = answer.

```python
def pacific_atlantic(h: list[list[int]]) -> list[list[int]]:
    if not h: return []
    R, C = len(h), len(h[0])
    pac, atl = set(), set()
    def fill(stack, seen):
        while stack:
            r, c = stack.pop(); seen.add((r,c))
            for dr,dc in ((1,0),(-1,0),(0,1),(0,-1)):
                nr,nc = r+dr, c+dc
                if 0<=nr<R and 0<=nc<C and (nr,nc) not in seen and h[nr][nc] >= h[r][c]:
                    stack.append((nr,nc))
    fill([(0,c) for c in range(C)] + [(r,0) for r in range(R)], pac)
    fill([(R-1,c) for c in range(C)] + [(r,C-1) for r in range(R)], atl)
    return [list(c) for c in pac & atl]
```

**Dense one-liner:** reverse-BFS from each ocean; intersect.

**Complexity:** O(R×C).  **Gotcha:** moving "uphill from the ocean" simulates "water flowing down to it" — the inversion trips many candidates.

---

### Q.281 — Word Search (DFS with backtracking)
**Companies:** Amazon, Meta.

**Prose:** DFS each cell; mark visited via temporary mutation, restore on backtrack.

```python
def exist(b: list[list[str]], w: str) -> bool:
    R, C = len(b), len(b[0])
    def dfs(r, c, i):
        if i == len(w): return True
        if not (0<=r<R and 0<=c<C) or b[r][c] != w[i]: return False
        b[r][c] = "#"
        ok = any(dfs(r+dr,c+dc,i+1) for dr,dc in ((1,0),(-1,0),(0,1),(0,-1)))
        b[r][c] = w[i]
        return ok
    return any(dfs(r,c,0) for r in range(R) for c in range(C))
```

**Dense one-liner:** mutate cell to sentinel, recurse, restore.

**Complexity:** O(R×C × 4^L).  **Gotcha:** must restore the cell or repeated paths stay marked across attempts.

---

### Q.282 — Dijkstra (shortest path, non-negative weights)
**Companies:** Google, Amazon.

**Prose:** Min-heap by current distance; relax edges. O((V+E) log V).

```python
import heapq

def dijkstra(g: dict, src: int) -> dict:
    dist: dict = {src: 0}; h = [(0, src)]
    while h:
        d, u = heapq.heappop(h)
        if d > dist.get(u, float("inf")): continue
        for v, w in g[u]:
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd; heapq.heappush(h, (nd, v))
    return dist
```

**Dense one-liner:** `if nd < dist[v]: dist[v]=nd; heappush(h,(nd,v))`.

**Complexity:** O((V+E) log V).  **Gotcha:** lazy deletion via `if d > dist[u]: continue` is the cleanest pattern; updating heap entries is messy.

---

## C.18.5 — Dynamic Programming (Q.283–Q.290)

### Q.283 — Climbing Stairs (Fibonacci)
**Companies:** Amazon.

**Prose:** `dp[n] = dp[n-1] + dp[n-2]`. O(1) memory with two vars.

```python
def climb(n: int) -> int:
    a, b = 1, 1
    for _ in range(n): a, b = b, a + b
    return a
```

**Dense one-liner:** `a, b = b, a+b` for n iterations.

**Complexity:** O(N).  **Gotcha:** off-by-one on initial values is the entire bug surface.

---

### Q.284 — House Robber
**Companies:** Amazon.

**Prose:** `dp[i] = max(dp[i-1], dp[i-2] + nums[i])`.

```python
def rob(nums: list[int]) -> int:
    prev = curr = 0
    for x in nums: prev, curr = curr, max(curr, prev + x)
    return curr
```

**Dense one-liner:** `prev, curr = curr, max(curr, prev+x)`.

**Complexity:** O(N).  **Gotcha:** the recurrence handles "skip current" vs "rob current + skip prev"; missing one option = wrong answer.

---

### Q.285 — Word Break
**Companies:** Amazon, Meta.

**Prose:** `dp[i]` = can split `s[:i]`. `dp[i] = any(dp[j] and s[j:i] in words for j < i)`.

```python
def word_break(s: str, words: list[str]) -> bool:
    ws = set(words); dp = [False] * (len(s) + 1); dp[0] = True
    for i in range(1, len(s) + 1):
        for j in range(i):
            if dp[j] and s[j:i] in ws: dp[i] = True; break
    return dp[len(s)]
```

**Dense one-liner:** `dp[i] = any(dp[j] and s[j:i] in ws for j<i)`.

**Complexity:** O(N²).  **Gotcha:** trie + DFS gives faster on long strings; mention as optimisation.

---

### Q.286 — Longest Increasing Subsequence (LIS, O(N log N))
**Companies:** Google, Meta.

**Prose:** Maintain `tails[]`; for each x, binary-search the position to replace. Length of `tails` is LIS length.

```python
import bisect
def lis(nums: list[int]) -> int:
    tails: list[int] = []
    for x in nums:
        i = bisect.bisect_left(tails, x)
        if i == len(tails): tails.append(x)
        else: tails[i] = x
    return len(tails)
```

**Dense one-liner:** `bisect_left(tails, x)`; append or overwrite.

**Complexity:** O(N log N).  **Gotcha:** `tails` is **not** an LIS itself — it's a length-witnessing structure; reconstructing the actual LIS needs more bookkeeping.

---

### Q.287 — Coin Change (min coins)
**Companies:** Amazon.

**Prose:** See Q.224. Bottom-up DP.

```python
def coin_change(coins: list[int], amount: int) -> int:
    INF = amount + 1
    dp = [0] + [INF] * amount
    for a in range(1, amount + 1):
        dp[a] = min((dp[a-c] for c in coins if c <= a), default=INF) + 1
    return dp[amount] if dp[amount] < INF else -1
```

**Dense one-liner:** `dp[a] = min(dp[a-c] for c if c<=a) + 1`.

**Complexity:** O(amount × coins).  **Gotcha:** unbounded knapsack flavour — coins can repeat; bounded variant changes the recurrence.

---

### Q.288 — Unique Paths (grid)
**Companies:** Amazon.

**Prose:** `dp[r][c] = dp[r-1][c] + dp[r][c-1]`. O(N) memory with 1D row.

```python
def unique_paths(m: int, n: int) -> int:
    dp = [1] * n
    for _ in range(1, m):
        for c in range(1, n): dp[c] += dp[c-1]
    return dp[-1]
```

**Dense one-liner:** roll 2D into 1D row; `dp[c] += dp[c-1]`.

**Complexity:** O(N×M), O(N) space.  **Gotcha:** combinatorics gives O(1): C(m+n-2, m-1); show off if asked.

---

### Q.289 — Decode Ways
**Companies:** Meta, Amazon.

**Prose:** `dp[i] = (dp[i-1] if s[i-1]!='0') + (dp[i-2] if 10<=int(s[i-2:i])<=26)`.

```python
def num_decodings(s: str) -> int:
    if not s or s[0] == "0": return 0
    a, b = 1, 1
    for i in range(1, len(s)):
        c = (b if s[i] != "0" else 0) + (a if 10 <= int(s[i-1:i+1]) <= 26 else 0)
        a, b = b, c
    return b
```

**Dense one-liner:** rolling two-state DP with two conditions.

**Complexity:** O(N).  **Gotcha:** "0" handling is the entire problem — `"06"` is invalid; a leading 0 in any 2-digit window must be excluded.

---

### Q.290 — Maximum Product Subarray
**Companies:** Amazon, Meta.

**Prose:** Track running max **and** min (negative × negative = positive).

```python
def max_product(nums: list[int]) -> int:
    cur_max = cur_min = best = nums[0]
    for x in nums[1:]:
        cands = (x, cur_max * x, cur_min * x)
        cur_max, cur_min = max(cands), min(cands)
        best = max(best, cur_max)
    return best
```

**Dense one-liner:** track both max and min; swap on negative.

**Complexity:** O(N).  **Gotcha:** the "swap on negative" intuition is correct but error-prone; `max(x, x*M, x*m)` covers all cases without manual sign tracking.

---

## C.18.6 — Heaps, Sorting, Misc (Q.291–Q.298)

### Q.291 — Kth Largest Element (heap or quickselect)
**Companies:** Amazon, Meta.

**Prose:** `heapq.nlargest(k, nums)[-1]` for the simple way.

```python
import heapq
def kth_largest(nums: list[int], k: int) -> int:
    return heapq.nlargest(k, nums)[-1]
```

**Dense one-liner:** `heapq.nlargest(k, nums)[-1]`.

**Complexity:** O(N log K).  **Gotcha:** quickselect O(N) average is the textbook answer; `nlargest` is the practical one.

---

### Q.292 — Top K Frequent Elements
**Companies:** Amazon, Meta.

**Prose:** Counter + nlargest.

```python
from collections import Counter
def top_k(nums: list[int], k: int) -> list[int]:
    return [x for x, _ in Counter(nums).most_common(k)]
```

**Dense one-liner:** `Counter(nums).most_common(k)`.

**Complexity:** O(N log K).  **Gotcha:** bucket-sort by frequency gives O(N) — say it; implement only if interviewer asks.

---

### Q.293 — Find Median From Data Stream
**Companies:** Amazon, Meta.

**Prose:** See Q.230. Two heaps.

```python
# already shown in Q.230
```

**Dense one-liner:** max-heap (lo) + min-heap (hi); balance + read.

**Complexity:** O(log N) add.  **Gotcha:** Python's heapq is min-only; lo via negation.

---

### Q.294 — Meeting Rooms II (min rooms required)
**Companies:** Meta, Amazon.

**Prose:** Sweep line: start events +1, end events -1, sorted; max running sum = answer. Or sort starts and ends separately.

```python
def min_rooms(intervals: list[list[int]]) -> int:
    starts = sorted(i[0] for i in intervals)
    ends = sorted(i[1] for i in intervals)
    rooms = max_rooms = j = 0
    for s in starts:
        if s < ends[j]: rooms += 1; max_rooms = max(max_rooms, rooms)
        else: j += 1
    return max_rooms
```

**Dense one-liner:** two sorted arrays; bump rooms when start before next end.

**Complexity:** O(N log N).  **Gotcha:** events at the same time — closing first or opening first changes count by one; spec usually says "end is exclusive".

---

### Q.295 — Merge Intervals
**Companies:** Amazon, Meta.

**Prose:** Sort by start; merge in place.

```python
def merge(intervals: list[list[int]]) -> list[list[int]]:
    intervals.sort()
    out: list[list[int]] = []
    for i in intervals:
        if out and i[0] <= out[-1][1]: out[-1][1] = max(out[-1][1], i[1])
        else: out.append(i)
    return out
```

**Dense one-liner:** sort; merge if `i[0] <= out[-1][1]`.

**Complexity:** O(N log N).  **Gotcha:** always extend with `max(...)` — the new interval might be entirely inside the previous.

---

### Q.296 — Spiral Matrix
**Companies:** Amazon, Meta.

**Prose:** Track four bounds (top, bottom, left, right); shrink each as you finish a side.

```python
def spiral(m: list[list[int]]) -> list[int]:
    out: list[int] = []; t,b,l,r = 0, len(m)-1, 0, len(m[0])-1
    while t <= b and l <= r:
        for c in range(l, r+1): out.append(m[t][c])
        t += 1
        for r_ in range(t, b+1): out.append(m[r_][r])
        r -= 1
        if t <= b:
            for c in range(r, l-1, -1): out.append(m[b][c])
            b -= 1
        if l <= r:
            for r_ in range(b, t-1, -1): out.append(m[r_][l])
            l += 1
    return out
```

**Dense one-liner:** four bounds; right, down, left, up; shrink each.

**Complexity:** O(R×C).  **Gotcha:** the two extra `if` checks (after top→right) catch the case where the matrix has only one row or column left.

---

### Q.297 — Set Matrix Zeroes (in place, O(1) extra)
**Companies:** Amazon, Meta.

**Prose:** Use first row + first column as marker storage; track flags for whether row 0 / col 0 themselves should be zeroed.

```python
def set_zeroes(m: list[list[int]]) -> None:
    R, C = len(m), len(m[0])
    row0 = any(m[0][c] == 0 for c in range(C))
    col0 = any(m[r][0] == 0 for r in range(R))
    for r in range(1, R):
        for c in range(1, C):
            if m[r][c] == 0: m[r][0] = 0; m[0][c] = 0
    for r in range(1, R):
        for c in range(1, C):
            if m[r][0] == 0 or m[0][c] == 0: m[r][c] = 0
    if row0:
        for c in range(C): m[0][c] = 0
    if col0:
        for r in range(R): m[r][0] = 0
```

**Dense one-liner:** first row/col = markers; flags for row0/col0.

**Complexity:** O(R×C).  **Gotcha:** order matters — process inner cells first, then row 0 / col 0 last; otherwise markers get overwritten.

---

### Q.298 — Trapping Rain Water
**Companies:** Amazon, Meta, Google.

**Prose:** Two pointers; track max-left and max-right. Add `(min_max - h[i])` at the lower side, advance.

```python
def trap(h: list[int]) -> int:
    i, j = 0, len(h)-1
    lmax = rmax = water = 0
    while i < j:
        if h[i] < h[j]:
            lmax = max(lmax, h[i]); water += lmax - h[i]; i += 1
        else:
            rmax = max(rmax, h[j]); water += rmax - h[j]; j -= 1
    return water
```

**Dense one-liner:** two pointers; lower side bounded by its own running max.

**Complexity:** O(N), O(1).  **Gotcha:** the symmetry intuition (lower side is bounded by its own max) is the only proof you need — interview often asks "why?"

---

# Index Summary

- **Track A — SRE-First (Q.001–Q.114):** boto3/AWS, k8s client, asyncio/GIL, system design, networking, file I/O, observability.
- **Track B — Thematic Mastery (Q.115–Q.248):** testing, performance, type hints, decorators, generators, OOP, functional, strings/regex, data structures (with ~10 integrated algos), gotchas.
- **Track C — Algorithms Appendix (Q.249–Q.298):** 50 canonical FAANG algorithm patterns across arrays, linked lists, trees, graphs, DP, heaps.

**Total:** 298 questions across 18 sections + appendix.

