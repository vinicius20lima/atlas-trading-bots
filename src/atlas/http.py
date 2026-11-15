"""Small GET-only JSON client. v0.1 has no helper that submits an order body."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from atlas.errors import AdapterError

USER_AGENT = "atlas-trading-bots/0.1.0"
GetJson = Callable[[str, dict[str, str] | None], Any]


def http_get_json(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = 20.0,
    attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    last: Exception | None = None
    merged = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        merged.update(headers)
    path = urllib.parse.urlparse(url).path or "/"
    for attempt in range(attempts):
        request = urllib.request.Request(url, headers=merged, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8")
            return json.loads(payload)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:400]
            last = AdapterError(f"HTTP {exc.code} {path}: {body}")
            if exc.code in {418, 429, 500, 502, 503, 504} and attempt + 1 < attempts:
                sleep(0.4 * (attempt + 1))
                continue
            raise last from exc
        except urllib.error.URLError as exc:
            last = AdapterError(f"network failure {path}: {exc.reason}")
            if attempt + 1 < attempts:
                sleep(0.4 * (attempt + 1))
                continue
            raise last from exc
        except json.JSONDecodeError as exc:
            raise AdapterError(f"invalid JSON from {path}") from exc
    raise AdapterError(f"request failed {path}: {last}")


def build_url(base: str, path: str, params: dict[str, object] | None = None) -> str:
    root = base.rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    if not params:
        return f"{root}{suffix}"
    query = urllib.parse.urlencode(params, doseq=True)
    return f"{root}{suffix}?{query}"
