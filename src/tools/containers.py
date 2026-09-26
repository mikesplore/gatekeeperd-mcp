"""Docker container and image tools — list, create, start/stop/restart/delete, logs, wizard."""
from __future__ import annotations

from typing import Any
import client as gk
from utils import ok, err
from mcp.server.fastmcp import FastMCP


CONTAINER_FIELDS = {
    "id", "name", "image", "status", "state", "ports", "created", "networks",
    "environmentKeys", "health", "restartCount", "oomKilled",
}


def _safe_container(item: dict[str, Any]) -> dict[str, Any]:
    return {key: item[key] for key in CONTAINER_FIELDS if key in item}


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_containers(limit: int = 50, offset: int = 0) -> str:
        """List all Docker containers (running and stopped) on the host."""
        try:
            data = await gk.aget("/admin/containers", {"limit": limit, "offset": offset})
            return ok({
                "containers": [_safe_container(item) for item in data.get("containers", []) if isinstance(item, dict)],
                "total": data.get("total"), "limit": data.get("limit"), "offset": data.get("offset"),
            })
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def get_container(name: str) -> str:
        """Get details for a single Docker container by name or ID prefix."""
        try:
            data = await gk.aget(f"/admin/containers/{name}")
            return ok(_safe_container(data) if isinstance(data, dict) else {})
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def start_container(name: str) -> str:
        """Start a stopped Docker container."""
        try:
            return ok(await gk.apost(f"/admin/containers/{name}/start"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def stop_container(name: str) -> str:
        """Stop a running Docker container."""
        try:
            return ok(await gk.apost(f"/admin/containers/{name}/stop"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def restart_container(name: str) -> str:
        """Restart a Docker container."""
        try:
            return ok(await gk.apost(f"/admin/containers/{name}/restart"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def delete_container(name: str) -> str:
        """
        Permanently delete a Docker container (force-stops it first if running).

        name: container name or ID prefix — must be a non-empty string
        """
        if not name or not name.strip():
            return err(ValueError("name must not be empty"))
        try:
            return ok(await gk.apost(f"/admin/containers/{name}/delete"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def create_container(
        name: str,
        image: str,
        ports: dict[str, int] | None = None,
        env: dict[str, str] | None = None,
        network: str = "bridge",
        restart_policy: str = "unless-stopped",
        pull_image: bool = True,
        pull_via_cli: bool = False,
        project_slug: str | None = None,
        volumes: list[dict[str, Any]] | None = None,
    ) -> str:
        """
        Create and start a new Docker container.
        name: container name
        image: Docker image e.g. 'nginx:latest'
        ports: map of host_port (str) -> container_port (int) e.g. {'9921': 8080}
        env: environment variables as key-value pairs
        network: Docker network name (default 'bridge')
        restart_policy: 'no' | 'always' | 'unless-stopped' | 'on-failure'
        pull_image: pull the image before creating (default True)
        pull_via_cli: use 'docker pull' for private Docker Hub images that need host auth
        project_slug: optional — auto-names the container from the project slug
        volumes: list of {'hostPath':..., 'containerPath':..., 'readOnly': bool}
        """
        try:
            body: dict[str, Any] = {
                "name": name, "image": image, "network": network,
                "restartPolicy": restart_policy, "pullImage": pull_image, "pullViaCli": pull_via_cli,
            }
            if ports: body["ports"] = ports
            if env: body["env"] = env
            if project_slug: body["projectSlug"] = project_slug
            if volumes: body["volumes"] = volumes
            return ok(await gk.apost("/admin/containers/create", body))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def validate_container_create(
        name: str,
        image: str,
        ports: dict[str, int] | None = None,
        env: dict[str, str] | None = None,
        network: str = "bridge",
        restart_policy: str = "unless-stopped",
    ) -> str:
        """
        Validate container creation parameters without creating the container.
        Returns port conflicts, image availability, network existence, and warnings.
        Use this before create_container to catch issues early.
        """
        try:
            body: dict[str, Any] = {
                "name": name, "image": image, "network": network,
                "restartPolicy": restart_policy, "pullImage": False,
            }
            if ports: body["ports"] = ports
            if env: body["env"] = env
            return ok(await gk.apost("/admin/containers/wizard/validate", body))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def check_ports_availability(host_ports: list[int]) -> str:
        """Check whether the given host port numbers are currently in use on the Docker host."""
        try:
            return ok(await gk.apost("/admin/containers/wizard/ports/check", {"hostPorts": host_ports}))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def get_container_wizard_context() -> str:
        """
        Get Docker wizard context: internal network name, whether it exists, and available networks.
        Use before creating a container to pick the right network.
        """
        try:
            return ok(await gk.aget("/admin/containers/wizard/context"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def check_image_exists(image: str) -> str:
        """Check whether a Docker image is already available locally on the host."""
        try:
            return ok(await gk.apost("/admin/images/status", {"image": image}))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def pull_image(image: str, tag: str = "latest", pull_via_cli: bool = False) -> str:
        """
        Pull a Docker image from a registry.
        pull_via_cli: set True for private Docker Hub images that need the host's Docker auth.
        """
        try:
            return ok(await gk.apost("/admin/images/pull", {"image": image, "tag": tag, "pullViaCli": pull_via_cli}))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def delete_image(image: str, tag: str = "latest", force: bool = True) -> str:
        """Delete a Docker image from the local host. force=True removes even if containers use it."""
        try:
            return ok(await gk.apost("/admin/images/delete", {"image": image, "tag": tag, "force": force}))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def list_networks() -> str:
        """List all Docker networks on the host."""
        try:
            return ok(await gk.aget("/admin/networks"))
        except Exception as e:
            return err(e)
