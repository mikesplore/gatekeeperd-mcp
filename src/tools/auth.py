"""Authentication tools — login, logout, current user."""
from __future__ import annotations

import client as gk
from utils import ok, err
from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def login(email: str, password: str) -> str:
        """
        Authenticate with the Gatekeeperd admin API and store the JWT for subsequent calls.
        Must be called before any admin tool unless GATEKEEPERD_TOKEN is pre-set in .env.
        Returns the logged-in user email and role on success.
        """
        try:
            data = await gk.apost("/auth/login", {"email": email, "password": password})
            token = data.get("token")
            if not token:
                return ok({"error": True, "detail": "Login succeeded but no token was returned", "raw": data})
            gk.set_token(token)
            me = await gk.aget("/auth/me")
            return ok({"authenticated": True, "email": me.get("email"), "role": me.get("role")})
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def logout() -> str:
        """Revoke the current JWT token and clear the stored session."""
        try:
            result = await gk.apost("/auth/logout")
        except Exception:
            result = {}
        gk.set_token("")
        return ok({"logged_out": True, **result})

    @mcp.tool()
    async def get_current_user() -> str:
        """Return the profile of the currently authenticated admin user (email, role, createdAt)."""
        try:
            return ok(await gk.aget("/auth/me"))
        except Exception as e:
            return err(e)
