"""Invoice and receipt tools — create, resync, download invoice PDF, download receipt PDF."""
from __future__ import annotations

import base64
import client as gk
from utils import ok, err
from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def get_project_invoice(slug: str) -> str:
        """
        Get the current Scribed invoice for a project: number, status, total amount,
        paid amount, outstanding balance, and download URL.
        """
        try:
            return ok(await gk.aget(f"/admin/projects/{slug}/invoice"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def create_project_invoice(slug: str, description: str) -> str:
        """
        Create a Scribed invoice for a project that does not already have one.
        description: invoice line-item description e.g. 'Hosting and maintenance services for Q3 2026'
        Queues a ledger sync and replays successful payments to generate missing receipts.
        """
        try:
            return ok(await gk.apost(f"/admin/projects/{slug}/invoice", {"description": description}))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def resync_project_invoice(slug: str) -> str:
        """
        Resync the project's Scribed invoice: ensures the invoice exists, replays successful
        payments to refresh totals, and generates any missing receipts idempotently.
        """
        try:
            return ok(await gk.apost(f"/admin/projects/{slug}/invoice/resync"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def download_invoice(slug: str) -> str:
        """
        Download the Scribed invoice PDF for a project.
        Returns filename, content_type, size in bytes, and the PDF as a base64 string.
        If no invoice exists yet, one is created and payments are synced first.
        """
        try:
            _status, content, content_type = await gk.aget_bytes(f"/admin/projects/{slug}/invoice/download")
            return ok({
                "filename": f"invoice-{slug}.pdf",
                "content_type": content_type,
                "size_bytes": len(content),
                "base64": base64.b64encode(content).decode(),
            })
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def download_payment_receipt(slug: str, payment_id: str) -> str:
        """
        Download a receipt PDF for a specific successful payment.
        slug: project slug
        payment_id: Gatekeeperd payment UUID
        Returns filename, content_type, size in bytes, and the PDF as a base64 string.
        """
        try:
            _status, content, content_type = await gk.aget_bytes(
                f"/admin/projects/{slug}/payments/{payment_id}/receipt"
            )
            return ok({
                "filename": f"receipt-{slug}-{payment_id}.pdf",
                "content_type": content_type,
                "size_bytes": len(content),
                "base64": base64.b64encode(content).decode(),
            })
        except Exception as e:
            return err(e)
