"""Service invoice and receipt tools."""
from __future__ import annotations

import base64
import client as gk
from utils import ok, err
from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def get_service_invoice(project_id: str, service_id: str) -> str:
        """
        Get the current Scribed invoice for a service: number, status, total amount,
        paid amount, outstanding balance, and download URL.
        """
        try:
            return ok(await gk.aget(f"/admin/projects/{project_id}/services/{service_id}/invoice"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def create_service_invoice(project_id: str, service_id: str, description: str, amount: float) -> str:
        """
        Create a Scribed invoice for a service that does not already have one.
        description: invoice line-item description e.g. 'Hosting and maintenance services for Q3 2026'
        Amount is the invoice's base amount; service-scoped adjustments affect the balance separately.
        """
        try:
            return ok(await gk.apost(f"/admin/projects/{project_id}/services/{service_id}/invoice", {"description": description, "amount": amount}))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def download_service_invoice(project_id: str, service_id: str) -> str:
        """
        Download the Scribed invoice PDF for a service.
        Returns filename, content_type, size in bytes, and the PDF as a base64 string.
        The service invoice must already exist.
        """
        try:
            _status, content, content_type = await gk.aget_bytes(f"/admin/projects/{project_id}/services/{service_id}/invoice/download")
            return ok({
                "filename": f"invoice-{service_id}.pdf",
                "content_type": content_type,
                "size_bytes": len(content),
                "base64": base64.b64encode(content).decode(),
            })
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def download_payment_receipt(project_id: str, service_id: str, payment_id: str) -> str:
        """
        Download a receipt PDF for a specific successful payment.
        project_id/service_id: project and service UUIDs
        payment_id: Gatekeeperd payment UUID
        Returns filename, content_type, size in bytes, and the PDF as a base64 string.
        """
        try:
            _status, content, content_type = await gk.aget_bytes(
                f"/admin/projects/{project_id}/services/{service_id}/payments/{payment_id}/receipt"
            )
            return ok({
                "filename": f"receipt-{payment_id}.pdf",
                "content_type": content_type,
                "size_bytes": len(content),
                "base64": base64.b64encode(content).decode(),
            })
        except Exception as e:
            return err(e)
