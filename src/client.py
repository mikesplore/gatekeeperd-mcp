"""
Async HTTP client for the Gatekeeperd API.

All tools must use the async helpers (aget, apost, apatch, adelete, aget_bytes).
On any 401 response the client attempts a single token refresh using the stored
admin credentials before propagating the error — this covers the case where a
long-running process outlives the 24-hour JWT expiry.
"""
from __future__ import annotations

import httpx
from typing import Any
import config as cfg

# ── Session state ─────────────────────────────────────────────────────────────
_token: str = cfg.GATEKEEPERD_TOKEN


def set_token(token: str) -> None:
    global _token
    _token = token


def get_token() -> str:
    return _token


# ── Internal helpers ──────────────────────────────────────────────────────────
def _headers() -> dict[str, str]:
    h: dict[str, str] = {"Content-Type": "application/json"}
    if _token:
        h["Authorization"] = f"Bearer {_token}"
    return h


def _base() -> str:
    return cfg.GATEKEEPERD_URL


async def _refresh_token() -> bool:
    """
    Re-authenticate using stored credentials and update the in-memory token.
    Returns True if a new token was obtained, False otherwise.
    """
    if not (cfg.GATEKEEPERD_ADMIN_EMAIL and cfg.GATEKEEPERD_ADMIN_PASSWORD):
        return False
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                f"{_base()}/auth/login",
                json={"email": cfg.GATEKEEPERD_ADMIN_EMAIL, "password": cfg.GATEKEEPERD_ADMIN_PASSWORD},
                headers={"Content-Type": "application/json"},
            )
            r.raise_for_status()
            token = r.json().get("token")
            if token:
                set_token(token)
                return True
    except Exception:
        pass
    return False


async def _request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    """
    Execute an async HTTP request. On a 401 response, attempt a single token
    refresh and retry. Raises httpx.HTTPStatusError on all other failures.
    """
    url = f"{_base()}{path}"
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.request(method, url, headers=_headers(), **kwargs)
        if r.status_code == 401:
            refreshed = await _refresh_token()
            if refreshed:
                r = await c.request(method, url, headers=_headers(), **kwargs)
        r.raise_for_status()
        return r


# ── Public async API ──────────────────────────────────────────────────────────
async def aget(path: str, params: dict[str, Any] | None = None) -> Any:
    r = await _request("GET", path, params=params)
    return r.json()


async def apost(path: str, body: dict[str, Any] | None = None) -> Any:
    r = await _request("POST", path, json=body or {})
    return r.json()


async def apatch(path: str, body: dict[str, Any]) -> Any:
    r = await _request("PATCH", path, json=body)
    return r.json()


async def aput(path: str, body: dict[str, Any]) -> Any:
    r = await _request("PUT", path, json=body)
    return r.json()


async def adelete(path: str) -> int:
    r = await _request("DELETE", path)
    return r.status_code


async def aget_bytes(path: str) -> tuple[int, bytes, str]:
    """Return (status_code, body_bytes, content_type)."""
    r = await _request("GET", path)
    return r.status_code, r.content, r.headers.get("content-type", "")


# ── Startup bootstrap (sync, called once before the event loop starts) ────────
def bootstrap_sync(email: str, password: str) -> str | None:
    """
    Synchronous login used only at startup (before the async loop is running).
    Returns the token on success or None on failure.
    """
    try:
        r = httpx.post(
            f"{_base()}/auth/login",
            json={"email": email, "password": password},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("token")
    except Exception:
        return None
