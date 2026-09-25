"""
In-memory OAuth 2.0 Authorization Server Provider for the streamable-HTTP transport.

This provider implements the full MCP OAuth PKCE flow so Claude.ai (and any other
modern MCP client) can connect without a static Bearer token.

Storage is **in-process memory only** — tokens are lost on restart.  That is
intentional for a single-admin tool: every restart forces a fresh OAuth dance,
which is no worse than rotating an API key.

The "authorize" step renders a minimal HTML consent form.  Submitting it issues
an auth code that Claude exchanges for an access token.  The access token is then
verified on every POST /mcp request by the SDK's built-in token-verifier path.

Configuration (all read from config.py):
    MCP_OAUTH_ISSUER          — public HTTPS URL of this server (required)
    MCP_OAUTH_CLIENT_ID       — pre-registered client ID  (default: "claude")
    MCP_OAUTH_CLIENT_SECRET   — pre-registered client secret (optional,
                                 leave blank to rely on PKCE-only validation)
    MCP_OAUTH_TOKEN_TTL       — access token lifetime in seconds (default: 3600)
"""
from __future__ import annotations

import hashlib
import hmac
import html
import os
import secrets
import time
from base64 import urlsafe_b64decode
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

import config as cfg


# ── Simple in-memory stores ───────────────────────────────────────────────────

_auth_codes: dict[str, AuthorizationCode] = {}          # code  -> AuthorizationCode
_access_tokens: dict[str, AccessToken]    = {}          # token -> AccessToken
_refresh_tokens: dict[str, RefreshToken]  = {}          # token -> RefreshToken
_clients: dict[str, OAuthClientInformationFull] = {}    # client_id -> client info


# ── Helpers ───────────────────────────────────────────────────────────────────

def _verify_pkce(code_challenge: str, code_verifier: str) -> bool:
    """S256 PKCE verification."""
    digest = hashlib.sha256(code_verifier.encode()).digest()
    # urlsafe_b64encode without padding
    import base64
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return hmac.compare_digest(expected, code_challenge)


def _consent_html(client_name: str, scopes: list[str], action_url: str, hidden: dict[str, str]) -> str:
    """Minimal inline-styled consent page — no external resources."""
    scope_list = "".join(f"<li>{html.escape(s)}</li>" for s in scopes) if scopes else "<li>(all tools)</li>"
    hidden_inputs = "".join(
        f'<input type="hidden" name="{html.escape(k)}" value="{html.escape(v)}">'
        for k, v in hidden.items()
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Authorize Gatekeeperd MCP</title>
<style>
  body{{font-family:-apple-system,Segoe UI,sans-serif;background:#f7f8fa;
        display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}
  .card{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:2rem;
         max-width:420px;width:90%;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
  h1{{font-size:1.1rem;margin:0 0 .5rem}}
  p{{color:#57606a;font-size:.9rem;margin:.25rem 0 1rem}}
  ul{{color:#1f2328;font-size:.9rem;margin:.5rem 0 1.25rem;padding-left:1.25rem}}
  .btn{{display:inline-block;padding:.5rem 1.25rem;border-radius:6px;
        border:none;cursor:pointer;font-size:.9rem}}
  .allow{{background:#3b82d4;color:#fff;margin-right:.5rem}}
  .deny{{background:#f7f8fa;color:#1f2328;border:1px solid #e5e7eb}}
</style>
</head>
<body>
<div class="card">
  <h1>Authorize <strong>{html.escape(client_name)}</strong></h1>
  <p>This client is requesting access to <strong>Gatekeeperd MCP</strong>.</p>
  <p>Requested scopes:</p><ul>{scope_list}</ul>
  <form method="post" action="{html.escape(action_url)}">
    {hidden_inputs}
    <button class="btn allow" name="decision" value="allow">Allow</button>
    <button class="btn deny"  name="decision" value="deny">Deny</button>
  </form>
</div>
</body>
</html>"""


# ── Provider implementation ───────────────────────────────────────────────────

class GatekeeperdOAuthProvider(OAuthAuthorizationServerProvider):
    """
    Minimal in-memory OAuth provider.

    Pre-registers the client specified by MCP_OAUTH_CLIENT_ID at construction
    time so Claude.ai can start the flow immediately without dynamic registration
    (dynamic registration is still supported if the client sends a POST /register).
    """

    def __init__(self) -> None:
        # Pre-register the configured client (only when issuer is set).
        # redirect_uris requires at least one entry; we use a placeholder because
        # Claude supplies its own redirect_uri dynamically at authorization time.
        if cfg.MCP_OAUTH_CLIENT_ID and cfg.MCP_OAUTH_ISSUER:
            _clients[cfg.MCP_OAUTH_CLIENT_ID] = OAuthClientInformationFull(
                client_id=cfg.MCP_OAUTH_CLIENT_ID,
                client_secret=cfg.MCP_OAUTH_CLIENT_SECRET or None,
                redirect_uris=["https://claude.ai/oauth/callback"],
                grant_types=["authorization_code", "refresh_token"],
                response_types=["code"],
                scope="mcp",
                client_name="Claude (pre-registered)",
                issuer=cfg.MCP_OAUTH_ISSUER,
            )

    # ── Client registry ───────────────────────────────────────────────────────

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return _clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        _clients[client_info.client_id] = client_info

    # ── Authorization ─────────────────────────────────────────────────────────

    async def authorize(
        self,
        client: OAuthClientInformationFull,
        params: AuthorizationParams,
    ) -> str:
        """
        Return an HTML consent page URL.  The SDK calls this when Claude hits
        GET /authorize and expects us to return a URL to redirect the browser to.

        We redirect to our own /authorize/consent endpoint (handled by the
        Starlette app we build in server.py) passing all params as query params.
        """
        qs = urlencode(
            {
                "client_id": client.client_id,
                "state": params.state or "",
                "code_challenge": params.code_challenge or "",
                "redirect_uri": str(params.redirect_uri) if params.redirect_uri else "",
                "redirect_uri_provided_explicitly": str(params.redirect_uri_provided_explicitly),
                "scope": " ".join(params.scopes or []),
                "resource": str(params.resource) if params.resource else "",
            }
        )
        return f"{cfg.MCP_OAUTH_ISSUER}/authorize/consent?{qs}"

    # ── Auth code handling ────────────────────────────────────────────────────

    async def load_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: str,
    ) -> AuthorizationCode | None:
        code = _auth_codes.get(authorization_code)
        if code and code.expires_at > time.time() and code.client_id == client.client_id:
            return code
        return None

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: AuthorizationCode,
    ) -> OAuthToken:
        # Consume the code
        _auth_codes.pop(authorization_code.code, None)

        ttl = cfg.MCP_OAUTH_TOKEN_TTL
        access_token = secrets.token_urlsafe(32)
        refresh_tok  = secrets.token_urlsafe(32)

        _access_tokens[access_token] = AccessToken(
            token=access_token,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=int(time.time()) + ttl,
        )
        _refresh_tokens[refresh_tok] = RefreshToken(
            token=refresh_tok,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=None,  # refresh tokens don't expire in this impl
        )

        return OAuthToken(
            access_token=access_token,
            token_type="bearer",
            expires_in=ttl,
            scope=" ".join(authorization_code.scopes) if authorization_code.scopes else "",
            refresh_token=refresh_tok,
        )

    # ── Refresh tokens ────────────────────────────────────────────────────────

    async def load_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: str,
    ) -> RefreshToken | None:
        tok = _refresh_tokens.get(refresh_token)
        if tok and tok.client_id == client.client_id:
            return tok
        return None

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        ttl = cfg.MCP_OAUTH_TOKEN_TTL
        access_token = secrets.token_urlsafe(32)

        _access_tokens[access_token] = AccessToken(
            token=access_token,
            client_id=client.client_id,
            scopes=scopes or refresh_token.scopes,
            expires_at=int(time.time()) + ttl,
        )

        return OAuthToken(
            access_token=access_token,
            token_type="bearer",
            expires_in=ttl,
            scope=" ".join(scopes or refresh_token.scopes or []),
            refresh_token=refresh_token.token,
        )

    # ── Access token verification ─────────────────────────────────────────────

    async def load_access_token(self, token: str) -> AccessToken | None:
        tok = _access_tokens.get(token)
        if tok is None:
            return None
        if tok.expires_at and tok.expires_at < time.time():
            _access_tokens.pop(token, None)
            return None
        return tok

    # ── Revocation ────────────────────────────────────────────────────────────

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        if isinstance(token, AccessToken):
            _access_tokens.pop(token.token, None)
        else:
            _refresh_tokens.pop(token.token, None)


# ── Consent route helpers (used by server.py) ─────────────────────────────────

def build_consent_page(
    client: OAuthClientInformationFull,
    params: dict[str, str],
) -> str:
    """Return the HTML consent page string."""
    scopes = params.get("scope", "").split() if params.get("scope") else []
    action_url = f"{cfg.MCP_OAUTH_ISSUER}/authorize/consent"
    return _consent_html(
        client_name=client.client_name or client.client_id,
        scopes=scopes,
        action_url=action_url,
        hidden=params,
    )


def issue_auth_code(
    client_id: str,
    code_challenge: str,
    redirect_uri: str,
    redirect_uri_provided_explicitly: bool,
    scopes: list[str],
    resource: str,
) -> str:
    """Mint a short-lived auth code and store it; return the code string."""
    code = secrets.token_urlsafe(24)
    _auth_codes[code] = AuthorizationCode(
        code=code,
        client_id=client_id,
        code_challenge=code_challenge,
        redirect_uri=redirect_uri or None,
        redirect_uri_provided_explicitly=redirect_uri_provided_explicitly,
        scopes=scopes,
        expires_at=int(time.time()) + 300,  # 5-minute window
        resource=resource or None,
    )
    return code
