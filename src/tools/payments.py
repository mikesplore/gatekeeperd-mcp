"""Payment tools — initialize, cash capture, list, reconcile, events, revenue."""
from __future__ import annotations

from typing import Any
import client as gk
from utils import ok, err
from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def initialize_payment(slug: str, email: str | None = None, amount: float | None = None) -> str:
        """
        Generate a Paystack payment link for a project.
        Returns a payment_link URL to send to the client.
        email: override the project's customer email (optional)
        amount: partial payment amount (optional, defaults to full outstanding balance)
        Pending transactions are reconciled automatically if they block a retry.
        """
        try:
            body: dict[str, Any] = {}
            if email: body["email"] = email
            if amount is not None: body["amount"] = amount
            return ok(await gk.apost(f"/admin/projects/{slug}/payment/initialize", body))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def record_cash_payment(
        slug: str,
        amount: float,
        currency: str | None = None,
        paid_at: str | None = None,
        receipt_number: str | None = None,
        notes: str | None = None,
    ) -> str:
        """
        Record a cash payment received in person by an administrator.
        Partial payments are accepted up to the remaining balance.
        paid_at: ISO datetime e.g. '2026-09-20T10:30:00' (optional, defaults to now)
        receipt_number: unique identifier — reusing the same number is rejected as a duplicate
        notes: free-text memo (optional)
        """
        try:
            body: dict[str, Any] = {"amount": amount}
            if currency: body["currency"] = currency
            if paid_at: body["paidAt"] = paid_at
            if receipt_number: body["receiptNumber"] = receipt_number
            if notes: body["notes"] = notes
            return ok(await gk.apost(f"/admin/projects/{slug}/payments/cash", body))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def list_payments(
        status: str = "",
        project_slug: str = "",
        from_date: str = "",
        to_date: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> str:
        """
        List all payments across all projects with optional filters.
        status: 'pending' | 'success' | 'failed' | 'abandoned' | 'reversed'
        project_slug: filter to one project
        from_date/to_date: ISO date range e.g. '2026-01-01'
        """
        try:
            params: dict[str, Any] = {"limit": limit, "offset": offset}
            if status: params["status"] = status
            if project_slug: params["project_slug"] = project_slug
            if from_date: params["from"] = from_date
            if to_date: params["to"] = to_date
            return ok(await gk.aget("/admin/payments", params))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def list_project_payments(slug: str, limit: int = 25, offset: int = 0) -> str:
        """List paginated payment history for a specific project."""
        try:
            return ok(await gk.aget(f"/admin/projects/{slug}/payments", {"limit": limit, "offset": offset}))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def reconcile_payment(payment_id: str) -> str:
        """
        Manually trigger reconciliation for a pending payment by its UUID.
        Verifies the transaction with the payment provider and updates the status.
        """
        try:
            return ok(await gk.apost(f"/admin/payments/{payment_id}/reconcile"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def list_payment_events(status: str = "", limit: int = 100, offset: int = 0) -> str:
        """
        List raw webhook payment events — useful for debugging failed webhooks.
        status: 'received' | 'processed' | 'failed' (optional)
        """
        try:
            params: dict[str, Any] = {"limit": limit, "offset": offset}
            if status: params["status"] = status
            return ok(await gk.aget("/admin/payment-events", params))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def replay_payment_event(event_id: str) -> str:
        """Replay a stored failed webhook event through the idempotent payment handlers."""
        try:
            return ok(await gk.apost(f"/admin/payment-events/{event_id}/replay"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def get_revenue_report(months: int = 6) -> str:
        """
        Get revenue summary: total this month, total last month, MoM delta,
        and a per-month breakdown for the last N months (max 24).
        """
        try:
            return ok(await gk.aget("/admin/revenue", {"period": "month", "months": months}))
        except Exception as e:
            return err(e)
