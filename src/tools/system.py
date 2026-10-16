"""System / dashboard tools — summary, notifications, metrics, registry credentials."""
from __future__ import annotations

import client as gk
from utils import ok, err
from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def get_dashboard_summary() -> str:
        """
        Get the admin dashboard summary in one call: project status counts, payment status counts,
        revenue totals, integration outbox counts, nginx site counts, and runtime metrics.
        """
        try:
            return ok(await gk.aget("/admin/dashboard/summary"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def list_notifications(limit: int = 25, offset: int = 0) -> str:
        """List admin notifications (payment alerts, suspension notices, system events)."""
        try:
            return ok(await gk.aget("/admin/notifications", {"limit": limit, "offset": offset}))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def get_metrics() -> str:
        """
        Get in-process operational counters: gate checks, webhook outcomes, fail-open/closed events.
        Counters reset on process restart.
        """
        try:
            return ok(await gk.aget("/admin/metrics"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def health_check() -> str:
        """Check the overall health (liveness) of the Gatekeeperd service."""
        try:
            return ok(await gk.aget("/health"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def health_ready() -> str:
        """Check readiness — returns whether PostgreSQL and Redis are reachable."""
        try:
            return ok(await gk.aget("/health/ready"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def get_backend_version() -> str:
        """Read the public Gatekeeperd version endpoint without admin credentials."""
        try:
            return ok(await gk.aget("/version"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def list_registries() -> str:
        """List configured Docker registry credentials (passwords are never returned)."""
        try:
            return ok(await gk.aget("/admin/registries"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def upsert_registry_credential(registry: str, username: str, password: str) -> str:
        """
        Add or update Docker registry credentials (stored AES-256-GCM encrypted at rest).
        registry: registry host e.g. 'docker.io' or 'ghcr.io'
        username: registry username
        password: registry password or access token
        """
        try:
            response = await gk.aput(f"/admin/registries/{registry}", {"username": username, "password": password})
            return ok({key: response.get(key) for key in ("credentialId", "version", "configured")})
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def rotate_github_credential(credential_type: str, value: str) -> str:
        """Write a new GitHub webhook-secret or App private-key version; never returns the value."""
        if credential_type not in ("webhook_secret", "app_private_key"):
            return err(ValueError("credential_type must be webhook_secret or app_private_key"))
        try:
            response = await gk.aput(f"/admin/github/credentials/{credential_type}", {"value": value})
            return ok({key: response.get(key) for key in ("id", "type", "configured", "version", "writeOnly")})
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def delete_registry_credential(registry: str) -> str:
        """Delete stored credentials for a Docker registry."""
        try:
            code = await gk.adelete(f"/admin/registries/{registry}")
            return ok({"deleted": True, "registry": registry, "status_code": code})
        except Exception as e:
            return err(e)
