
#!/usr/bin/env python3
"""
Gatekeeperd MCP Server — entrypoint.

Token resolution order at startup:
  1. GATEKEEPERD_TOKEN in .env (pre-seeded, skips login)
  2. GATEKEEPERD_ADMIN_EMAIL + GATEKEEPERD_ADMIN_PASSWORD in .env (login at startup)
  3. Neither set — server starts unauthenticated; call login() manually as the first tool.

Transports
----------
stdio           — Bob spawns this process directly (default).
http            — Legacy SSE/HTTP endpoint for older MCP clients (Bob, MCP Inspector).
                  Requires MCP_API_KEY. Set ALLOW_UNAUTHENTICATED_HTTP=true to override
                  (not recommended — exposes all admin tools to the network).
streamable-http — Modern Streamable HTTP transport for Claude.ai and newer clients.
                  Uses OAuth 2.0 PKCE; requires MCP_OAUTH_ISSUER in .env.
                  Exposes POST /mcp plus the full OAuth discovery/consent endpoints.

Environment variables: see ../.env.example
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is on the path regardless of how the script is invoked
sys.path.insert(0, str(Path(__file__).parent))

import config as cfg
import client as gk

from mcp.server.fastmcp import FastMCP

from tools import auth, projects, payments, invoices, containers, deployments, nginx, customers, audit, system

# ── Server instance ───────────────────────────────────────────────────────────
mcp = FastMCP(
    "gatekeeperd",
    instructions=(
        "You are an assistant for the Gatekeeperd payment-gating backend. "
        "Call login() first if no token is pre-seeded via GATEKEEPERD_TOKEN in .env. "
        "All /admin/* tools require authentication. "
        "gate_check() is public and requires no auth."
    ),
)

# ── Register every tool module ────────────────────────────────────────────────
auth.register(mcp)
projects.register(mcp)
payments.register(mcp)
invoices.register(mcp)
containers.register(mcp)
deployments.register(mcp)
nginx.register(mcp)
customers.register(mcp)
audit.register(mcp)
system.register(mcp)


# ── Startup auth ──────────────────────────────────────────────────────────────
def _bootstrap_token() -> None:
    """
    Obtain a Gatekeeperd JWT at startup so no manual login() call is needed.

    Priority:
      1. GATEKEEPERD_TOKEN — use as-is (caller manages rotation)
      2. GATEKEEPERD_ADMIN_EMAIL + PASSWORD — login and cache the token
      3. Neither — warn and continue; tools will fail until login() is called
    """
    if cfg.GATEKEEPERD_TOKEN:
        gk.set_token(cfg.GATEKEEPERD_TOKEN)
        sys.stderr.write("gatekeeperd-mcp: using pre-seeded JWT from GATEKEEPERD_TOKEN\n")
        return

    if cfg.GATEKEEPERD_ADMIN_EMAIL and cfg.GATEKEEPERD_ADMIN_PASSWORD:
        sys.stderr.write(
            f"gatekeeperd-mcp: logging in as {cfg.GATEKEEPERD_ADMIN_EMAIL} ...\n"
        )
        token = gk.bootstrap_sync(cfg.GATEKEEPERD_ADMIN_EMAIL, cfg.GATEKEEPERD_ADMIN_PASSWORD)
        if token:
            gk.set_token(token)
            sys.stderr.write("gatekeeperd-mcp: authenticated successfully\n")
        else:
            sys.stderr.write(
                "gatekeeperd-mcp: ERROR — startup login failed; "
                "server will start unauthenticated. Call login() manually.\n"
            )
        return

    sys.stderr.write(
        "gatekeeperd-mcp: no credentials configured — "
        "set GATEKEEPERD_ADMIN_EMAIL + GATEKEEPERD_ADMIN_PASSWORD in .env, "
        "or call login() as the first tool\n"
    )


# ── API key middleware (HTTP transport only) ──────────────────────────────────
def _build_protected_app(base_app):
    """
    Wrap the FastMCP Starlette app with API key enforcement.
    Uses the public Starlette middleware API instead of a private FastMCP attribute.
    """
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse
    from starlette.routing import Mount

    api_key = cfg.MCP_API_KEY

    class ApiKeyMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer ") or auth_header[7:] != api_key:
                return JSONResponse(
                    {"error": "Unauthorized", "detail": "Valid Bearer token required"},
                    status_code=401,
                )
            return await call_next(request)

    # Wrap the existing ASGI app in a new Starlette app with the middleware applied
    return Starlette(
        routes=[Mount("/", app=base_app)],
        middleware=[Middleware(ApiKeyMiddleware)],
    )


# ── Streamable-HTTP OAuth bootstrap ──────────────────────────────────────────
def _build_oauth_mcp() -> "FastMCP":
    """
    Re-create the FastMCP instance with OAuth wired in.

    FastMCP does not support adding auth after construction, so we build a
    dedicated instance here and re-register all tool modules onto it.
    """
    from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
    from oauth_provider import GatekeeperdOAuthProvider

    if not cfg.MCP_OAUTH_ISSUER:
        sys.stderr.write(
            "gatekeeperd-mcp: FATAL — MCP_OAUTH_ISSUER is not set.\n"
            "gatekeeperd-mcp: Streamable-HTTP transport requires a public HTTPS issuer URL.\n"
            "gatekeeperd-mcp: Set MCP_OAUTH_ISSUER=https://your.domain in .env.\n"
        )
        sys.exit(1)

    provider = GatekeeperdOAuthProvider()

    auth_settings = AuthSettings(
        issuer_url=cfg.MCP_OAUTH_ISSUER,           # type: ignore[arg-type]
        resource_server_url=cfg.MCP_OAUTH_ISSUER,  # type: ignore[arg-type]
        validate_token_resource=False,             # our provider validates internally
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=["mcp"],
            default_scopes=["mcp"],
        ),
        required_scopes=[],  # allow any authenticated client
    )

    oauth_mcp = FastMCP(
        "gatekeeperd",
        instructions=(
            "You are an assistant for the Gatekeeperd payment-gating backend. "
            "Call login() first if no token is pre-seeded via GATEKEEPERD_TOKEN in .env. "
            "All /admin/* tools require authentication. "
            "gate_check() is public and requires no auth."
        ),
        auth_server_provider=provider,
        auth=auth_settings,
    )

    # Re-register all tool modules on the OAuth-enabled instance
    auth.register(oauth_mcp)
    projects.register(oauth_mcp)
    payments.register(oauth_mcp)
    invoices.register(oauth_mcp)
    containers.register(oauth_mcp)
    deployments.register(oauth_mcp)
    nginx.register(oauth_mcp)
    customers.register(oauth_mcp)
    audit.register(oauth_mcp)
    system.register(oauth_mcp)

    return oauth_mcp, provider


def _build_streamable_app(oauth_mcp: "FastMCP", provider):
    """
    Build the final Starlette ASGI app: the FastMCP streamable-HTTP app at /mcp
    plus a hand-rolled /authorize/consent route that renders and processes the
    OAuth consent form (the SDK handles /authorize redirect, /token, etc.).
    """
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import HTMLResponse, RedirectResponse
    from starlette.routing import Mount, Route
    from urllib.parse import urlencode

    from oauth_provider import build_consent_page, issue_auth_code

    async def consent_get(request: Request):
        """Render the consent form.  All OAuth params arrive as query-string."""
        params = dict(request.query_params)
        client_id = params.get("client_id", "")
        client = await provider.get_client(client_id)
        if client is None:
            return HTMLResponse("Unknown client.", status_code=400)
        return HTMLResponse(build_consent_page(client, params))

    async def consent_post(request: Request):
        """
        Process the consent form submission.
        - decision=allow  → mint auth code, redirect back to client redirect_uri
        - decision=deny   → redirect with error=access_denied
        """
        form = await request.form()
        decision = form.get("decision", "deny")
        client_id = str(form.get("client_id", ""))
        redirect_uri = str(form.get("redirect_uri", ""))
        state = str(form.get("state", ""))
        code_challenge = str(form.get("code_challenge", ""))
        redirect_uri_explicit = str(form.get("redirect_uri_provided_explicitly", "False")).lower() == "true"
        scopes = str(form.get("scope", "")).split()
        resource = str(form.get("resource", ""))

        if decision != "allow":
            qs = urlencode({"error": "access_denied", "state": state})
            return RedirectResponse(f"{redirect_uri}?{qs}", status_code=302)

        code = issue_auth_code(
            client_id=client_id,
            code_challenge=code_challenge,
            redirect_uri=redirect_uri,
            redirect_uri_provided_explicitly=redirect_uri_explicit,
            scopes=scopes,
            resource=resource,
        )
        qs = urlencode({"code": code, "state": state})
        return RedirectResponse(f"{redirect_uri}?{qs}", status_code=302)

    consent_routes = [
        Route("/authorize/consent", endpoint=consent_get, methods=["GET"]),
        Route("/authorize/consent", endpoint=consent_post, methods=["POST"]),
    ]

    # The streamable HTTP app provides /mcp + all OAuth discovery/token routes
    base_app = oauth_mcp.streamable_http_app()

    return Starlette(
        routes=[
            *consent_routes,
            Mount("/", app=base_app),
        ]
    )


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    _bootstrap_token()

    if cfg.MCP_TRANSPORT == "streamable-http":
        sys.stderr.write(
            f"gatekeeperd-mcp: starting Streamable HTTP (OAuth) on "
            f"{cfg.MCP_HOST}:{cfg.MCP_PORT}\n"
            f"gatekeeperd-mcp: OAuth issuer: {cfg.MCP_OAUTH_ISSUER}\n"
            f"gatekeeperd-mcp: MCP endpoint: POST {cfg.MCP_OAUTH_ISSUER}/mcp\n"
        )
        import uvicorn
        oauth_mcp, provider = _build_oauth_mcp()
        app = _build_streamable_app(oauth_mcp, provider)
        uvicorn.run(app, host=cfg.MCP_HOST, port=cfg.MCP_PORT)

    elif cfg.MCP_TRANSPORT == "http":
        if not cfg.MCP_API_KEY:
            allow_unauthed = cfg.ALLOW_UNAUTHENTICATED_HTTP
            if not allow_unauthed:
                sys.stderr.write(
                    "gatekeeperd-mcp: FATAL — MCP_API_KEY is not set.\n"
                    "gatekeeperd-mcp: Refusing to start HTTP transport without authentication.\n"
                    "gatekeeperd-mcp: Set MCP_API_KEY in .env, or set ALLOW_UNAUTHENTICATED_HTTP=true\n"
                    "gatekeeperd-mcp: to explicitly allow unauthenticated access (NOT recommended).\n"
                )
                sys.exit(1)
            sys.stderr.write(
                "gatekeeperd-mcp: WARNING — MCP_API_KEY is not set and "
                "ALLOW_UNAUTHENTICATED_HTTP=true is set. HTTP transport is unauthenticated.\n"
            )
        else:
            sys.stderr.write("gatekeeperd-mcp: API key auth enabled\n")

        sys.stderr.write(
            f"gatekeeperd-mcp: starting HTTP/SSE on {cfg.MCP_HOST}:{cfg.MCP_PORT}\n"
        )

        import uvicorn
        # Build the Starlette ASGI app from FastMCP, then wrap it with auth middleware
        base_app = mcp.sse_app()
        app = _build_protected_app(base_app) if cfg.MCP_API_KEY else base_app
        uvicorn.run(app, host=cfg.MCP_HOST, port=cfg.MCP_PORT)

    else:
        sys.stderr.write("gatekeeperd-mcp: starting on stdio\n")
        mcp.run(transport="stdio")
