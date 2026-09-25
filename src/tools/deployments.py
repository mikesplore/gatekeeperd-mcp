"""Deployment tools — queue, monitor, cancel, retry, rollback, image prune."""
from __future__ import annotations

from typing import Any
import client as gk
from utils import ok, err
from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_deployments() -> str:
        """List all deployment jobs with their lifecycle state, image info, and logs."""
        try:
            return ok(await gk.aget("/admin/deployments"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def get_deployment(deployment_id: str) -> str:
        """Get full details for a deployment job including logs, commit SHA, and failure info."""
        try:
            return ok(await gk.aget(f"/admin/deployments/{deployment_id}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def create_deployment(
        repository: str,
        git_ref: str = "main",
        image_name: str = "",
        image_tag: str = "latest",
        registry: str = "docker.io",
        container_name: str | None = None,
        host_port: int | None = None,
        container_port: int | None = None,
        network: str | None = None,
        restart_policy: str = "unless-stopped",
        project_slug: str | None = None,
    ) -> str:
        """
        Queue a GitHub-to-container deployment job.
        repository: 'owner/repo' format e.g. 'mikesplore/acme-app'
        git_ref: branch or tag e.g. 'main'
        image_name: Docker image name to build/push to
        image_tag: Docker image tag
        registry: 'docker.io' or a custom registry host
        container_name: name for the resulting container (optional)
        host_port/container_port: port mapping (optional)
        network: Docker network to attach to (optional)
        restart_policy: Docker restart policy
        project_slug: link this deployment to a Gatekeeperd project (optional)
        """
        try:
            body: dict[str, Any] = {
                "repository": repository, "gitRef": git_ref, "imageName": image_name,
                "imageTag": image_tag, "registry": registry, "restartPolicy": restart_policy,
            }
            if container_name: body["containerName"] = container_name
            if host_port and container_port:
                body["hostPort"] = host_port
                body["containerPort"] = container_port
            if network: body["network"] = network
            if project_slug: body["projectSlug"] = project_slug
            return ok(await gk.apost("/admin/deployments", body))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def cancel_deployment(deployment_id: str) -> str:
        """Cancel a queued or in-progress deployment job."""
        try:
            return ok(await gk.apost(f"/admin/deployments/{deployment_id}/cancel"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def retry_deployment(deployment_id: str) -> str:
        """Retry a failed deployment job."""
        try:
            return ok(await gk.apost(f"/admin/deployments/{deployment_id}/retry"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def rollback_deployment(deployment_id: str) -> str:
        """
        Roll back a deployment to the previous container image.
        Uses the persisted previous image and performs health checks before swapping.
        """
        try:
            return ok(await gk.apost(f"/admin/deployments/{deployment_id}/rollback"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def get_deployment_audit(deployment_id: str) -> str:
        """Get the audit trail for a specific deployment job."""
        try:
            return ok(await gk.aget(f"/admin/deployments/{deployment_id}/audit"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def prune_docker_images(dry_run: bool = True, image_prefix: str = "") -> str:
        """
        Perform reference-aware Docker image cleanup.
        dry_run: if True (default), reports candidates without removing them — always run this first.
        image_prefix: limit cleanup to images matching this prefix e.g. 'myorg/myapp'.
        Active container images and current/previous deployment images are always preserved.
        Set dry_run=False to actually remove candidates.
        """
        try:
            params = f"dryRun={'true' if dry_run else 'false'}"
            if image_prefix: params += f"&imagePrefix={image_prefix}"
            return ok(await gk.apost(f"/admin/system/prune?{params}"))
        except Exception as e:
            return err(e)
