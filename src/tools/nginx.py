"""Nginx management tools — enable/disable/remove sites, config inspection, rollback, wizard."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote
import client as gk
from utils import ok, err
from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def get_nginx_status(slug: str) -> str:
        """
        Check nginx status for a project: enabled state, config path, port,
        SSL enabled, and certificate domain.
        """
        try:
            return ok(await gk.aget(f"/admin/nginx/status/{slug}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def enable_nginx_site(
        slug: str,
        port: int | None = None,
        upstream_scheme: str | None = None,
        certificate_domain: str | None = None,
        ssl_cert_path: str | None = None,
        ssl_key_path: str | None = None,
        require_ssl: bool = False,
    ) -> str:
        """
        Generate and enable an nginx reverse-proxy config for a project.
        The project's Docker container must be running.
        port: upstream port (inferred from containerName 'name:port' if omitted)
        upstream_scheme: 'http' or 'https' (auto-inferred if omitted)
        certificate_domain: Let's Encrypt domain for SSL e.g. 'example.com'
        ssl_cert_path/ssl_key_path: explicit cert file paths (override all other SSL selection)
        require_ssl: fail if no certificate is found (default False — enables HTTP fallback)
        """
        try:
            body: dict[str, Any] = {"requireSsl": require_ssl}
            if port is not None: body["port"] = port
            if upstream_scheme: body["upstreamScheme"] = upstream_scheme
            if certificate_domain: body["certificateDomain"] = certificate_domain
            if ssl_cert_path: body["sslCertificatePath"] = ssl_cert_path
            if ssl_key_path: body["sslCertificateKeyPath"] = ssl_key_path
            return ok(await gk.apost(f"/admin/nginx/enable/{slug}", body))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def disable_nginx_site(slug: str) -> str:
        """Disable (unlink) an nginx site without removing its config file."""
        try:
            return ok(await gk.apost(f"/admin/nginx/disable/{slug}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def remove_nginx_site(slug: str) -> str:
        """Completely remove an nginx site config (sites-available file and sites-enabled symlink)."""
        try:
            return ok(await gk.apost(f"/admin/nginx/remove/{slug}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def get_nginx_config(slug: str) -> str:
        """
        Get the live nginx config for a project: raw text, parsed blocks, SHA-256 fingerprint,
        and a drift flag showing if it differs from the last config applied through Gatekeeperd.
        """
        try:
            return ok(await gk.aget(f"/admin/nginx/config/{slug}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def run_nginx_diagnostics() -> str:
        """Run 'nginx -t' on the host and return exit code, validity, and full command output."""
        try:
            return ok(await gk.aget("/admin/nginx/diagnostics"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def rollback_nginx_config(slug: str) -> str:
        """
        Roll back a project's nginx config to the most recent backup.
        Validates with 'nginx -t' and reloads nginx. Restores current config if validation fails.
        """
        try:
            return ok(await gk.apost(f"/admin/nginx/rollback/{slug}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def list_nginx_config_versions(slug: str) -> str:
        """List available nginx configuration backups for a project."""
        try:
            return ok(await gk.aget(f"/admin/nginx/config/{slug}/versions"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def get_nginx_wizard_context(slug: str) -> str:
        """
        Get nginx wizard context for a project: container hints, published ports,
        installed certificates, and current nginx/SSL state. Use before enable_nginx_site.
        """
        try:
            return ok(await gk.aget(f"/admin/nginx/wizard/context/{slug}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def list_certificates() -> str:
        """
        List all installed Let's Encrypt certificates: domain, paths, expiry date,
        days remaining, and renewal status ('active' | 'expired' | 'unknown').
        """
        try:
            return ok(await gk.aget("/admin/nginx/certificate/list"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def install_certificate(domain: str, email: str) -> str:
        """
        Install a Let's Encrypt SSL certificate using certbot.
        Requires certbot and the gatekeeperd-certbot sudo helper on the host.
        domain: domain to certify e.g. 'acme.example.com'
        email: Let's Encrypt renewal contact address
        """
        try:
            return ok(await gk.apost("/admin/nginx/certificate/install", {"domain": domain, "email": email}))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def remove_certificate(domain: str) -> str:
        """Remove an installed Let's Encrypt SSL certificate for a domain."""
        try:
            return ok(await gk.apost(f"/admin/nginx/certificate/remove/{domain}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def check_certificate_status(domain: str) -> str:
        """Check whether a Let's Encrypt certificate is installed for a domain."""
        try:
            return ok(await gk.aget(f"/admin/nginx/certificate/status/{domain}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def renew_certificate(domain: str) -> str:
        """Renew an installed Certbot certificate. Check Gatekeeperd logs if renewal fails."""
        try:
            return ok(await gk.apost(f"/admin/nginx/certificate/renew/{domain}"))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def add_custom_nginx_location(slug: str, path: str, directives: str) -> str:
        """Add a validated application-specific Nginx location while preserving Gatekeeper auth and paywall blocks."""
        try:
            return ok(await gk.apost(
                f"/admin/nginx/config/{quote(slug, safe='')}/custom-blocks",
                {"path": path, "directives": directives},
            ))
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def remove_custom_nginx_location(slug: str, location_id: str) -> str:
        """Remove one saved custom Nginx location by its returned ID."""
        try:
            status = await gk.adelete(
                f"/admin/nginx/config/{quote(slug, safe='')}/custom-blocks/{quote(location_id, safe='')}"
            )
            return ok({"removed": 200 <= status < 300, "status_code": status})
        except Exception as e:
            return err(e)

    @mcp.tool()
    async def repair_deployment_nginx_upstream(service_id: str) -> str:
        """Explicitly point a deployment-managed Nginx site at its active runtime and verify it through Nginx."""
        try:
            return ok(await gk.apost(f"/admin/nginx/upstream-repair/{quote(service_id, safe='')}"))
        except Exception as e:
            return err(e)
