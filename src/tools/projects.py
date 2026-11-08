"""Project management tools — CRUD, block/unblock, adjustments, transfer, wizard."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote
import client as gk
from utils import ok, err
from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def search_gatekeeperd(query: str) -> str:
        """Search customers, projects, services, and domain bindings/configs across Gatekeeperd."""
        if not query.strip():
            return err(ValueError("query must not be empty"))
        try:
            return ok(await gk.aget("/admin/search", {"q": query.strip()}))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def configure_project_setup_source(
        project_id: str, image_name: str, repository: str | None = None, container_port: int | None = None,
        git_ref: str = "main", registry: str = "docker.io", image_tag: str = "latest",
        host_port: int | None = None, network: str = "bridge", restart_policy: str = "unless-stopped",
    ) -> str:
        """Save or update project source/runtime intent without accepting secret values."""
        try:
            body: dict[str, Any] = {
                "repository": repository, "gitRef": git_ref, "registry": registry,
                "imageName": image_name, "imageTag": image_tag,
                "network": network, "restartPolicy": restart_policy, "environment": "production",
            }
            if container_port is not None:
                body["containerPort"] = container_port
            if repository:
                body["repository"] = repository
            if host_port is not None:
                body["hostPort"] = host_port
            return ok(await gk.aput(f"/admin/project-setup/projects/{quote(project_id, safe='')}/source-runtime", body))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def configure_project_setup_domain(project_id: str, domain: str, service_id: str | None = None) -> str:
        """Save a service domain. Configure or enable its Nginx site separately."""
        try:
            body: dict[str, Any] = {"domain": domain}
            if service_id:
                body["serviceId"] = service_id
            return ok(await gk.aput(f"/admin/project-setup/projects/{quote(project_id, safe='')}/domain-gateway", body))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def deploy_project_setup(project_id: str, service_id: str = "") -> str:
        """Queue deployment from the project's saved source/runtime configuration."""
        try:
            path = f"/admin/project-setup/projects/{quote(project_id, safe='')}/deploy"
            if service_id:
                path += f"?serviceId={quote(service_id, safe='')}"
            response = await gk.apost(path)
            return ok({key: response.get(key) for key in ("deploymentId", "status")})
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def list_projects(search: str = "", status: str = "", limit: int = 100, offset: int = 0) -> str:
        """
        List all projects. Optionally filter by name/slug/domain text and/or
        status: 'active' | 'blocked' | 'manual_block'.
        Returns each project's billing info, due dates, and remaining balances.
        """
        try:
            params: dict[str, Any] = {"limit": limit, "offset": offset}
            if search: params["search"] = search
            if status: params["status"] = status
            return ok(await gk.aget("/admin/projects", params))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def get_project(slug: str) -> str:
        """
        Get full details for a single project including payments, adjustments, and audit log.
        slug is the project's unique identifier e.g. 'acme-corp'.
        """
        try:
            return ok(await gk.aget(f"/admin/projects/{slug}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def get_project_health(slug: str) -> str:
        """
        Get aggregated runtime health for a project: container state, nginx enabled status,
        SSL certificate installed, and overall readiness score.
        """
        try:
            return ok(await gk.aget(f"/admin/projects/{slug}/health"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def create_project(
        name: str,
        customer_id: str = "",
        amount_due: float | None = None,
        currency: str = "KES",
        due_date: str | None = None,
        grace_period_days: int = 3,
    ) -> str:
        """Create a project using the current setup API; Gatekeeperd generates its slug."""
        try:
            body: dict[str, Any] = {"name": name, "currency": currency, "gracePeriodDays": grace_period_days}
            if customer_id: body["customerId"] = customer_id
            if amount_due is not None: body["amountDue"] = amount_due
            if due_date: body["dueDate"] = due_date
            return ok(await gk.apost("/admin/project-setup/projects", body))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def update_project(
        slug: str,
        name: str | None = None,
        domain: str | None = None,
        container_name: str | None = None,
        project_type: str | None = None,
        amount_due: float | None = None,
        currency: str | None = None,
        due_date: str | None = None,
        grace_period_days: int | None = None,
        deployment_mode: str | None = None,
        service_mode: str | None = None,
        billing_name: str | None = None,
        billing_email: str | None = None,
        billing_address: str | None = None,
        customer_id: str | None = None,
    ) -> str:
        """
        Update one or more fields on an existing project. Only provided fields are changed.
        Pass due_date='' to clear the due date; pass amount_due=0 to clear the charge.
        """
        try:
            body: dict[str, Any] = {}
            if name is not None: body["name"] = name
            if domain is not None: body["domain"] = domain
            if container_name is not None: body["containerName"] = container_name
            if project_type is not None: body["type"] = project_type
            if amount_due is not None: body["amountDue"] = amount_due
            if currency is not None: body["currency"] = currency
            if due_date is not None: body["dueDate"] = due_date
            if grace_period_days is not None: body["gracePeriodDays"] = grace_period_days
            if deployment_mode is not None: body["deploymentMode"] = deployment_mode
            if service_mode is not None: body["serviceMode"] = service_mode
            if billing_name is not None: body["billingName"] = billing_name
            if billing_email is not None: body["billingEmail"] = billing_email
            if billing_address is not None: body["billingAddress"] = billing_address
            if customer_id is not None: body["customerId"] = customer_id
            return ok(await gk.apatch(f"/admin/projects/{slug}", body))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def block_project(slug: str, reason: str) -> str:
        """
        Manually block a project (sets status to manual_block). Immediately invalidates the
        Redis cache so traffic is denied within seconds. Notifies Scribed of suspension.

        slug: project slug e.g. 'acme-corp' — must be a non-empty string
        reason: human-readable reason — must be a non-empty string
        """
        if not slug or not slug.strip():
            return err(ValueError("slug must not be empty"))
        if not reason or not reason.strip():
            return err(ValueError("reason must not be empty"))
        try:
            return ok(await gk.apost(f"/admin/projects/{slug}/block", {"reason": reason}))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def unblock_project(slug: str, reason: str) -> str:
        """
        Manually unblock a project (sets status back to active). Immediately invalidates
        the Redis cache so traffic is allowed within seconds.
        """
        try:
            return ok(await gk.apost(f"/admin/projects/{slug}/unblock", {"reason": reason}))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def archive_project(slug: str) -> str:
        """
        Soft-delete (archive) a project. Preserves all payments and audit history.
        Attempts best-effort nginx cleanup. The slug is reserved and cannot be reused.

        slug: project slug e.g. 'acme-corp' — must be a non-empty string
        """
        if not slug or not slug.strip():
            return err(ValueError("slug must not be empty"))
        try:
            code = await gk.adelete(f"/admin/projects/{slug}")
            return ok({"archived": True, "slug": slug, "status_code": code})
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def transfer_project(slug: str, deployment_mode: str, service_mode: str) -> str:
        """
        Transfer a project to client ownership.
        deployment_mode: 'client_hosted' | 'external_hosted' | 'developer_hosted'
        service_mode: 'production' | 'testing' | 'development'
        """
        try:
            return ok(await gk.apost(f"/admin/projects/{slug}/transfer", {
                "deploymentMode": deployment_mode, "serviceMode": service_mode,
            }))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def bulk_block_projects(slugs: list[str], reason: str) -> str:
        """Block multiple projects at once. slugs: list of project slug strings."""
        try:
            return ok(await gk.apost("/admin/projects/bulk/block", {"slugs": slugs, "reason": reason}))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def bulk_unblock_projects(slugs: list[str], reason: str) -> str:
        """Unblock multiple projects at once. slugs: list of project slug strings."""
        try:
            return ok(await gk.apost("/admin/projects/bulk/unblock", {"slugs": slugs, "reason": reason}))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def get_overdue_projects() -> str:
        """
        List all active projects past their due date, sorted by days overdue descending.
        Shows the auto-block date based on each project's grace period.
        """
        try:
            return ok(await gk.aget("/admin/projects/overdue"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def add_project_adjustment(slug: str, adjustment_type: str, amount: float, reason: str) -> str:
        """
        Add a financial adjustment to a project ledger without altering original charge or payments.
        adjustment_type: 'ADDITIONAL_CHARGE' or 'DISCOUNT'
        amount: positive number
        reason: human-readable explanation
        Returns old balance, new balance, and the adjustment record.
        """
        if amount <= 0:
            return err(ValueError("amount must be a positive number"))
        if adjustment_type not in ("ADDITIONAL_CHARGE", "DISCOUNT"):
            return err(ValueError("adjustment_type must be 'ADDITIONAL_CHARGE' or 'DISCOUNT'"))
        try:
            return ok(await gk.apost(f"/admin/projects/{slug}/adjustments", {
                "type": adjustment_type, "amount": amount, "reason": reason,
            }))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def add_service_adjustment(project_id: str, service_id: str, adjustment_type: str, amount: float, reason: str) -> str:
        """Add an additional charge or discount to one service's billing ledger."""
        if amount <= 0:
            return err(ValueError("amount must be a positive number"))
        if adjustment_type not in ("ADDITIONAL_CHARGE", "DISCOUNT"):
            return err(ValueError("adjustment_type must be 'ADDITIONAL_CHARGE' or 'DISCOUNT'"))
        try:
            return ok(await gk.apost(f"/admin/projects/{project_id}/services/{service_id}/adjustments", {
                "type": adjustment_type, "amount": amount, "reason": reason,
            }))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def update_deployment_source(
        project_id: str,
        image_name: str,
        repository: str | None = None,
        git_ref: str = "main",
        image_tag: str = "latest",
        environment: str = "production",
        network: str = "bridge",
        restart_policy: str = "unless-stopped",
    ) -> str:
        """
        Save the project's image/runtime source using its UUID.
        repository: 'owner/repo' format (optional)
        git_ref: branch or tag e.g. 'main'
        image_name: Docker image name e.g. 'myorg/myapp'
        image_tag: Docker image tag e.g. 'latest'
        environment: deployment environment
        """
        try:
            body: dict[str, Any] = {
                "repository": repository, "gitRef": git_ref, "registry": "docker.io",
                "imageName": image_name, "imageTag": image_tag, "network": network,
                "restartPolicy": restart_policy, "environment": environment,
            }
            return ok(await gk.aput(f"/admin/project-setup/projects/{quote(project_id, safe='')}/source-runtime", body))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def get_project_wizard_context() -> str:
        """
        List containers available during project setup.
        """
        try:
            return ok(await gk.aget("/admin/project-setup/containers"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def gate_check(slug: str) -> str:
        """
        Check whether a project is currently active or blocked (public — no auth needed).
        Returns 'active' or 'blocked' with paywall data when blocked.
        """
        import httpx as _httpx
        try:
            result = await gk.aget(f"/gate/check?project={slug}")
            return ok({"status": "active", "data": result})
        except _httpx.HTTPStatusError as e:
            return ok({"status": "blocked", "http_status": e.response.status_code, "body": e.response.text})
        except Exception as e:
            return err(e)
