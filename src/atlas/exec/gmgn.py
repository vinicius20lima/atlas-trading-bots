"""Read-only wrapper around GMGN OpenAPI.

Auth for these GET routes is `X-APIKEY` plus `timestamp` and `client_id`.
Signed swap and order routes are not called. `swap()` always raises.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from atlas.errors import CredentialsMissing, LiveTradingDisabled
from atlas.http import GetJson, build_url, http_get_json


class GMGNReadClient:
    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://openapi.gmgn.ai",
        get_json: GetJson | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self._get_json = get_json or (lambda url, headers=None: http_get_json(url, headers))

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def trending(self, chain: str = "sol", interval: str = "1h", limit: int = 20) -> Any:
        return self._get(
            "/v1/market/rank",
            {"chain": chain, "interval": interval, "limit": limit},
        )

    def token_info(self, chain: str, address: str) -> Any:
        return self._get("/v1/token/info", {"chain": chain, "address": address})

    def smart_money(self, chain: str = "sol", limit: int = 20) -> Any:
        return self._get("/v1/user/smartmoney", {"chain": chain, "limit": limit})

    def _get(self, path: str, params: dict[str, object]) -> Any:
        if not self.api_key:
            raise CredentialsMissing("GMGN_API_KEY is not set")
        query = {
            **params,
            "timestamp": int(time.time()),
            "client_id": str(uuid.uuid4()),
        }
        url = build_url(self.base_url, path, query)
        payload = self._get_json(url, {"X-APIKEY": self.api_key})
        return payload


class GMGNExecutor:
    """The execution role. Market reads are delegated; anything that trades is refused."""

    def __init__(self, client: GMGNReadClient | None = None) -> None:
        self.client = client or GMGNReadClient()

    def status_note(self) -> str:
        if self.client.available:
            return "gmgn: key present; swaps disabled in v0.1.0"
        return "gmgn: GMGN_API_KEY missing; read-only client idle"

    def trending(self, chain: str = "sol", interval: str = "1h", limit: int = 20) -> Any:
        return self.client.trending(chain=chain, interval=interval, limit=limit)

    def token_info(self, chain: str, address: str) -> Any:
        return self.client.token_info(chain, address)

    def smart_money(self, chain: str = "sol", limit: int = 20) -> Any:
        return self.client.smart_money(chain=chain, limit=limit)

    def swap(self, *_args: object, **_kwargs: object) -> None:
        raise LiveTradingDisabled(
            "GMGN swap and order routes are disabled in v0.1.0. This wrapper is read-only."
        )
