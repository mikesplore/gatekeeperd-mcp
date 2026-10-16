"""Project-scoped deployment tools. Responses are metadata-only by allowlist."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

import client as gk
from utils import ok, err
from mcp.server.fastmcp import FastMCP


HISTORY_FIELDS = {
    "id", "environment", "sourceCommit", "imageName", "imageTag", "imageDigest",
    "trigger", "actor", "status", "createdAt", "activeAt", "healthCheckResult",
    "failureReason", "credentialSetId", "credentialSetVersion", "secretSetId",
    "secretSetVersion", "canRollback", "canRedeploy", "canCancel",
}


def _safe_history(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "projectId": payload.get("projectId"),
        "environment": payload.get("environment"),
        "items": [
            {key: item[key] for key in HISTORY_FIELDS if key in item}
            for item in payload.get("items", []) if isinstance(item, dict)
        ],
    }


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def get_project_deployment_history(
        project_slug: str,
        environment: str = "production",
        service_id: str = "",
    ) -> str:
        """Read project deployment history and credential/secret version references only; no logs or values."""
        try:
            slug = quote(project_slug, safe="")
            params: dict[str, Any] = {"environment": environment}
            if service_id:
                params["serviceId"] = service_id
            data = await gk.aget(f"/admin/projects/{slug}/deployments/history", params)
            return ok(_safe_history(data))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def get_project_deployment(project_slug: str, deployment_id: str, environment: str = "production") -> str:
        """Read one deployment's safe history metadata by project and deployment ID."""
        try:
            slug = quote(project_slug, safe="")
            data = _safe_history(await gk.aget(f"/admin/projects/{slug}/deployments/history", {"environment": environment}))
            item = next((item for item in data["items"] if item.get("id") == deployment_id), None)
            return ok({"projectId": data["projectId"], "environment": data["environment"], "deployment": item})
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def create_deployment(
        project_id: str,
        service_id: str | None = None,
    ) -> str:
        """Queue a deployment from saved desired configuration; configure it first if needed."""
        try:
            path = f"/admin/project-setup/projects/{quote(project_id, safe='')}/deploy"
            if service_id:
                path += f"?serviceId={quote(service_id, safe='')}"
            response = await gk.apost(path)
            return ok({key: response.get(key) for key in ("deploymentId", "status")})
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def redeploy_project(project_slug: str, deployment_id: str) -> str:
        """Queue a redeploy of the saved configuration for an active deployment."""
        try:
            slug = quote(project_slug, safe="")
            response = await gk.apost(f"/admin/projects/{slug}/deployments/{quote(deployment_id, safe='')}/redeploy")
            return ok({key: response.get(key) for key in ("deploymentId", "status")})
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def rollback_project_deployment(project_slug: str, deployment_id: str) -> str:
        """Queue a real, auditable rollback deployment for a superseded project deployment."""
        try:
            slug = quote(project_slug, safe="")
            response = await gk.apost(f"/admin/projects/{slug}/deployments/{quote(deployment_id, safe='')}/rollback")
            return ok({key: response.get(key) for key in ("deploymentId", "status")})
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def rotate_project_secrets_and_redeploy(project_id: str, secret_env: dict[str, str]) -> str:
        """Write a new project secret-set version and queue its deployment atomically. Values are never returned."""
        try:
            response = await gk.apost(
                f"/admin/projects/{quote(project_id, safe='')}/secret-sets/rotate-and-deploy",
                {"secretEnv": secret_env},
            )
            return ok({key: response.get(key) for key in ("deploymentId", "status")})
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def list_provider_credential_references(provider: str = "", credential_type: str = "") -> str:
        """List provider credential IDs, scopes, current versions, and rotation metadata only."""
        try:
            params = {key: value for key, value in (("provider", provider), ("type", credential_type)) if value}
            data = await gk.aget("/admin/project-setup/provider-credentials", params or None)
            allowed = {"id", "provider", "type", "displayName", "scope", "version", "current", "rotatedAt", "rotatedBy", "createdAt"}
            return ok([{key: item[key] for key in allowed if key in item} for item in data if isinstance(item, dict)])
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def prune_docker_images(dry_run: bool = True, image_prefix: str = "") -> str:
        """Perform reference-aware image cleanup; default is a report-only dry run."""
        try:
            params = f"dryRun={'true' if dry_run else 'false'}"
            if image_prefix:
                params += f"&imagePrefix={quote(image_prefix, safe='')}"
            return ok(await gk.apost(f"/admin/system/prune?{params}"))
        except Exception as e:
            return err(e)
