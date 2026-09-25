"""Audit log tools — global log, per-project log, CSV export."""
from __future__ import annotations

from typing import Any
import client as gk
from utils import ok, err
from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def get_audit_log(
        limit: int = 50,
        offset: int = 0,
        query: str = "",
        action: str = "",
        sort: str = "createdAt",
        direction: str = "desc",
    ) -> str:
        """
        Get the global audit log across all projects.
        query: free-text search over actor/reason fields
        action: filter by action type e.g. 'payment_received', 'blocked', 'project_adjustment'
        sort: field to sort by (default createdAt)
        direction: 'asc' or 'desc'
        """
        try:
            params: dict[str, Any] = {"limit": limit, "offset": offset, "sort": sort, "direction": direction}
            if query: params["q"] = query
            if action: params["action"] = action
            return ok(await gk.aget("/admin/audit", params))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def get_project_audit_log(slug: str) -> str:
        """Get the full audit log for a specific project."""
        try:
            return ok(await gk.aget(f"/admin/projects/{slug}/audit"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def export_audit_log(action: str = "", actor: str = "") -> str:
        """
        Export filtered audit log entries as CSV text.
        action: filter by action type (optional)
        actor: filter by actor email or 'system' (optional)
        """
        try:
            path = "/admin/audit/export"
            parts = []
            if action: parts.append(f"action={action}")
            if actor: parts.append(f"actor={actor}")
            if parts: path += "?" + "&".join(parts)
            _status, content, _ct = await gk.aget_bytes(path)
            return content.decode("utf-8", errors="replace")
        except Exception as e:
            return err(e)
