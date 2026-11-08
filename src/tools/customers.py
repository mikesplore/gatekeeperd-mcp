"""Customer management tools — list, get, create, assign to project."""
from __future__ import annotations

from typing import Any
import client as gk
from utils import ok, err
from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_customers() -> str:
        """List all customers registered in Gatekeeperd."""
        try:
            return ok(await gk.aget("/admin/dashboard/customers"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def get_customer(customer_id: str) -> str:
        """Get a single customer by their UUID."""
        try:
            return ok(await gk.aget(f"/admin/dashboard/customers/{customer_id}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def create_customer(
        first_name: str,
        last_name: str,
        contact_email: str | None = None,
        contact_phone: str | None = None,
    ) -> str:
        """
        Create a new customer record.
        first_name/last_name: customer name
        contact_email: primary email (optional)
        contact_phone: primary phone number (optional)
        """
        try:
            body: dict[str, Any] = {"firstName": first_name, "lastName": last_name}
            if contact_email: body["contactEmail"] = contact_email
            if contact_phone: body["contactPhone"] = contact_phone
            return ok(await gk.apost("/admin/dashboard/customers", body))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def update_customer(customer_id: str, first_name: str, last_name: str, contact_email: str | None = None, contact_phone: str | None = None) -> str:
        """Update a customer's name and contact details."""
        try:
            body: dict[str, Any] = {"firstName": first_name, "lastName": last_name}
            if contact_email is not None: body["contactEmail"] = contact_email
            if contact_phone is not None: body["contactPhone"] = contact_phone
            return ok(await gk.aput(f"/admin/dashboard/customers/{customer_id}", body))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def delete_customer(customer_id: str) -> str:
        """Delete a customer who has no assigned projects."""
        try:
            status = await gk.adelete(f"/admin/dashboard/customers/{customer_id}")
            return ok({"deleted": 200 <= status < 300, "status_code": status})
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def assign_customer_to_project(project_id: str, customer_id: str | None = None) -> str:
        """
        Assign or clear the customer on a project.
        project_id: the project UUID (not slug — get it from get_project)
        customer_id: UUID of the customer to assign, or omit/None to unlink
        """
        try:
            return ok(await gk.apatch(f"/admin/dashboard/projects/{project_id}", {"customerId": customer_id}))
        except Exception as e:
            return err(e)
