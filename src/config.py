"""
Central configuration loader.
Reads from .env (project root) then environment variables.
Environment variables take precedence over .env values.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (one level above src/)
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)

# ── Gatekeeperd backend ───────────────────────────────────────────────────────
GATEKEEPERD_URL: str = os.environ.get("GATEKEEPERD_URL", "http://localhost:8080/api").rstrip("/")

# Credentials — used to obtain a fresh JWT at startup
GATEKEEPERD_ADMIN_EMAIL: str = os.environ.get("GATEKEEPERD_ADMIN_EMAIL", "")
GATEKEEPERD_ADMIN_PASSWORD: str = os.environ.get("GATEKEEPERD_ADMIN_PASSWORD", "")

# Pre-seeded token — takes precedence over credentials if set
GATEKEEPERD_TOKEN: str = os.environ.get("GATEKEEPERD_TOKEN", "")

# ── MCP server auth (legacy SSE / http transport) ─────────────────────────────
MCP_API_KEY: str = os.environ.get("MCP_API_KEY", "")

# Set to 'true' to allow HTTP transport without an API key (NOT recommended)
ALLOW_UNAUTHENTICATED_HTTP: bool = os.environ.get("ALLOW_UNAUTHENTICATED_HTTP", "").lower() == "true"

# ── OAuth 2.0 (streamable-http transport) ─────────────────────────────────────
# Public HTTPS URL of this MCP server — used as the OAuth issuer identifier.
# Must match the URL Claude.ai uses to reach this server.
# Example: https://mcp.example.com
MCP_OAUTH_ISSUER: str = os.environ.get("MCP_OAUTH_ISSUER", "").rstrip("/")

# Pre-registered OAuth client for Claude.ai (or any trusted client).
# Leave MCP_OAUTH_CLIENT_SECRET blank to rely on PKCE-only validation.
MCP_OAUTH_CLIENT_ID: str = os.environ.get("MCP_OAUTH_CLIENT_ID", "claude")
MCP_OAUTH_CLIENT_SECRET: str = os.environ.get("MCP_OAUTH_CLIENT_SECRET", "")

# Access token lifetime in seconds (default 1 hour).
MCP_OAUTH_TOKEN_TTL: int = int(os.environ.get("MCP_OAUTH_TOKEN_TTL", "3600"))

# ── Transport ─────────────────────────────────────────────────────────────────
MCP_TRANSPORT: str = os.environ.get("MCP_TRANSPORT", "stdio").lower()
MCP_HOST: str = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT: int = int(os.environ.get("MCP_PORT", "9000"))
