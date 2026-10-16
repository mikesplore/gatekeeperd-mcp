"""Read-only operational tools for logs, deployment versions, and assigned runtime ports."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

import client as gk
from utils import ok, err
from mcp.server.fastmcp import FastMCP


RUNTIME_FIELDS = {
    "deploymentId", "status", "containerName", "serviceId", "environment", "publishedPorts",
    "imageName", "imageTag", "imageDigest", "commitSha", "activeAt", "sharedSetId",
    "sharedSetVersion", "serviceSetId", "serviceSetVersion", "variables", "publicExposure",
    "fingerprintAlgorithm",
}
LOG_FIELDS = {"id", "timestamp", "level", "logger", "thread", "message", "requestId", "stackTrace"}


def _safe_runtime(payload: dict[str, Any]) -> dict[str, Any]:
    result = {key: payload[key] for key in RUNTIME_FIELDS if key in payload}
    variables = result.get("variables")
    if isinstance(variables, list):
        result["variables"] = [
            {key: item[key] for key in ("key", "source", "fingerprint") if key in item}
            for item in variables if isinstance(item, dict)
        ]
    return result


def _safe_logs(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return {
        "logs": [
            {key: item[key] for key in LOG_FIELDS if key in item}
            for item in payload.get("logs", []) if isinstance(item, dict)
        ],
        "total": payload.get("total"),
        "limit": payload.get("limit"),
        "offset": payload.get("offset"),
        "hasMore": payload.get("hasMore"),
        "truncated": payload.get("truncated"),
        "summary": summary if isinstance(summary, dict) else {},
    }


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def get_gatekeeperd_logs(
        limit: int = 25,
        offset: int = 0,
        search: str = "",
        level: str = "",
    ) -> str:
        """Search paginated Gatekeeperd journal logs; credentials are redacted by the backend."""
        if not 1 <= limit <= 100:
            return err(ValueError("limit must be between 1 and 100"))
        if offset < 0:
            return err(ValueError("offset must not be negative"))
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if search:
            params["search"] = search[:200]
        if level:
            params["level"] = level.upper()
        try:
            return ok(_safe_logs(await gk.aget("/admin/logs", params)))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def get_project_service_runtime(
        project_id: str,
        service_id: str,
        environment: str = "production",
    ) -> str:
        """Inspect active or ready runtime state, including Gatekeeperd-assigned host port mappings."""
        try:
            path = (
                f"/admin/projects/{quote(project_id, safe='')}/services/"
                f"{quote(service_id, safe='')}/runtime"
            )
            return ok(_safe_runtime(await gk.aget(path, {"environment": environment})))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def get_deployment_reconciliation() -> str:
        """Report differences between canonical active deployments, Docker, and managed Nginx routes."""
        try:
            return ok(await gk.aget("/admin/deployments/reconciliation"))
        except Exception as e:
            return err(e)
