# Cheatsheet — Python for SRE

## Idioms to never get wrong
| Symbol | Meaning |
|---|---|
| `is` | identity |
| `==` | equality |
| `:=` | walrus (Python 3.8+) |
| `*args`, `**kwargs` | variadic positional / keyword |
| `/` and `*` in def | positional-only / keyword-only markers |

## Mutable default trap
```python
def f(x, lst=None):     # GOOD
    lst = lst or []
```

## Pathlib over os.path
```python
from pathlib import Path
for p in Path("logs").rglob("*.json"):
    print(p, p.stat().st_size)
```

## Logging that doesn't lie
```python
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)
log.info("started", extra={"cluster": c, "ns": ns})
```
**Never** use `print()` in services. Never `f-string` into the message: use `%s` so structured loggers can capture args.

## asyncio essentials
```python
import asyncio
async def main():
    results = await asyncio.gather(*(work(x) for x in items), return_exceptions=True)
asyncio.run(main())
```
- `asyncio.Semaphore` to bound concurrency.
- `asyncio.TaskGroup` (3.11+) for structured concurrency.
- Never `time.sleep` inside async — use `await asyncio.sleep`.

## httpx (sync + async)
```python
import httpx
async with httpx.AsyncClient(timeout=10) as c:
    r = await c.get(url, headers={"Authorization": f"Bearer {tok}"})
    r.raise_for_status()
    data = r.json()
```

## Retry with backoff (no library)
```python
import asyncio, random
async def with_retry(fn, tries=3, base=0.2):
    for i in range(tries):
        try: return await fn()
        except Exception:
            if i == tries - 1: raise
            await asyncio.sleep(base * (2 ** i) + random.random() * base)
```

## Pytest patterns
```python
import pytest
@pytest.fixture
def fake_client(): ...

@pytest.mark.parametrize("x,want", [(1,2),(2,4)])
def test_double(x, want):
    assert double(x) == want
```
Use `pytest -x --ff -k name` while debugging.

## Type hints worth using
```python
from typing import Iterable, Iterator, Protocol
class Fetchable(Protocol):
    def fetch(self, key: str) -> bytes: ...

def sizes(items: Iterable[bytes]) -> Iterator[int]:
    for b in items: yield len(b)
```

## boto3 paginator
```python
for page in boto3.client("s3").get_paginator("list_objects_v2").paginate(Bucket=b, Prefix=p):
    for obj in page.get("Contents", []): yield obj
```

## Common SRE one-liners
```python
# Top N keys by size from a dict
sorted(d.items(), key=lambda kv: kv[1], reverse=True)[:N]

# Group by
from itertools import groupby
groups = {k: list(v) for k, v in groupby(sorted(items, key=key), key=key)}

# Chunked
def chunks(xs, n):
    for i in range(0, len(xs), n): yield xs[i:i+n]
```
