"""Shared helpers used across all tool modules."""
from __future__ import annotations

import json
from typing import Any
import httpx


def ok(data: Any) -> str:
    """Serialize a successful result to JSON."""
    return json.dumps(data, default=str)


def err(e: Exception) -> str:
    """Serialize an exception into a structured error JSON string."""
    if isinstance(e, httpx.HTTPStatusError):
        try:
            body = e.response.json()
        except Exception:
            body = e.response.text
        return json.dumps({"error": True, "status": e.response.status_code, "detail": body})
    return json.dumps({"error": True, "detail": str(e)})
