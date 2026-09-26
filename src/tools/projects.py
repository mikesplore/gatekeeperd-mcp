"""Project management tools — CRUD, block/unblock, adjustments, transfer, wizard."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote
import client as gk
from utils import ok, err
from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def create_project_setup(slug: str, name: str, domain: str, project_type: str = "frontend", customer_id: str | None = None) -> str:
        """Create a project without a container; source, credentials, gateway, and deployment can follow later."""
        try:
            body: dict[str, Any] = {"slug": slug, "name": name, "domain": domain, "type": project_type}
            if customer_id:
                body["customerId"] = customer_id
            return ok(await gk.apost("/admin/project-setup/projects", body))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def configure_project_setup_source(
        project_id: str, repository: str, image_name: str, container_port: int,
        git_ref: str = "main", registry: str = "docker.io", image_tag: str = "latest",
        host_port: int | None = None, network: str = "bridge", restart_policy: str = "unless-stopped",
    ) -> str:
        """Save or update project source/runtime intent without accepting secret values."""
        try:
            body: dict[str, Any] = {
                "repository": repository, "gitRef": git_ref, "registry": registry,
                "imageName": image_name, "imageTag": image_tag, "containerPort": container_port,
                "network": network, "restartPolicy": restart_policy, "environment": "production",
            }
            if host_port is not None:
                body["hostPort"] = host_port
            return ok(await gk.aput(f"/admin/project-setup/projects/{quote(project_id, safe='')}/source-runtime", body))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def configure_project_setup_domain(project_id: str, domain: str, tls_mode: str = "http_only", gate_enabled: bool = True) -> str:
        """Save project domain and gateway intent, including before a runtime is deployed."""
        try:
            return ok(await gk.aput(f"/admin/project-setup/projects/{quote(project_id, safe='')}/domain-gateway", {
                "domain": domain, "tlsMode": tls_mode, "gateEnabled": gate_enabled,
            }))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def deploy_project_setup(project_id: str) -> str:
        """Queue deployment from the project's saved source/runtime configuration."""
        try:
            response = await gk.apost(f"/admin/project-setup/projects/{quote(project_id, safe='')}/deploy")
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
        slug: str,
        name: str,
        domain: str,
        container_name: str,
        project_type: str,
        amount_due: float | None = None,
        currency: str = "KES",
        due_date: str | None = None,
        grace_period_days: int = 3,
        deployment_mode: str = "developer_hosted",
        service_mode: str = "development",
        customer_id: str | None = None,
        new_customer_name: str | None = None,
        new_customer_email: str | None = None,
        new_customer_phone: str | None = None,
        billing_name: str | None = None,
        billing_email: str | None = None,
        billing_address: str | None = None,
    ) -> str:
        """
        Register a new project in Gatekeeperd. The Docker container must already exist.

        slug: unique lowercase identifier e.g. 'acme-corp'
        name: display name
        domain: client site domain e.g. 'acme.com'
        container_name: Docker container name or 'name:port' e.g. 'acme-app:9921'
        project_type: 'frontend' or 'backend'
        amount_due: total invoice amount (optional)
        currency: ISO currency code, default KES
        due_date: YYYY-MM-DD (optional)
        grace_period_days: auto-block grace window after due date (default 3)
        deployment_mode: 'developer_hosted' | 'client_hosted' | 'external_hosted'
        service_mode: 'development' | 'testing' | 'production'
        customer_id: UUID of an existing customer (mutually exclusive with new_customer_*)
        new_customer_name/email/phone: create a new customer inline (optional)
        billing_name/email/address: billing contact overrides (optional)
        """
        try:
            body: dict[str, Any] = {
                "slug": slug, "name": name, "domain": domain,
                "containerName": container_name, "type": project_type,
                "currency": currency, "gracePeriodDays": grace_period_days,
                "deploymentMode": deployment_mode, "serviceMode": service_mode,
            }
            if amount_due is not None: body["amountDue"] = amount_due
            if due_date: body["dueDate"] = due_date
            if customer_id: body["customerId"] = customer_id
            if new_customer_name:
                nc: dict[str, Any] = {"name": new_customer_name}
                if new_customer_email: nc["contactEmail"] = new_customer_email
                if new_customer_phone: nc["contactPhone"] = new_customer_phone
                body["newCustomer"] = nc
            if billing_name: body["billingName"] = billing_name
            if billing_email: body["billingEmail"] = billing_email
            if billing_address: body["billingAddress"] = billing_address
            return ok(await gk.apost("/admin/projects", body))
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
    async def update_deployment_source(
        slug: str,
        repository: str | None = None,
        git_ref: str = "main",
        image_name: str | None = None,
        image_tag: str = "latest",
        auto_deploy: bool = False,
    ) -> str:
        """
        Configure the GitHub/Docker deployment source for auto-redeployment on push events.
        repository: 'owner/repo' format (optional)
        git_ref: branch or tag e.g. 'main'
        image_name: Docker image name e.g. 'myorg/myapp'
        image_tag: Docker image tag e.g. 'latest'
        auto_deploy: whether to redeploy automatically on GitHub push events
        """
        try:
            body: dict[str, Any] = {"gitRef": git_ref, "imageTag": image_tag, "autoDeploy": auto_deploy}
            if repository: body["repository"] = repository
            if image_name: body["imageName"] = image_name
            return ok(await gk.apatch(f"/admin/projects/{slug}/deployment-source", body))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def get_project_wizard_context() -> str:
        """
        Get wizard helper context for creating a new project: running Docker containers
        with suggested slugs and all existing project slugs to avoid collisions.
        """
        try:
            return ok(await gk.aget("/admin/projects/wizard/context"))
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
