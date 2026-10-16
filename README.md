# gatekeeperd-mcp

MCP (Model Context Protocol) server for the [Gatekeeperd](https://github.com/mikesplore/gatekeeperd) payment-gating backend. Exposes the full Gatekeeperd admin API as conversational tools so an AI assistant (Bob, Claude, etc.) can manage projects, payments, invoices, containers, deployments, nginx, and more through natural language.

---

## Features

- **Tools across 11 domains** — project, payment, deployment, runtime, container, Nginx, certificate, and operations workflows
- **Auto-login at startup** — provide admin credentials in `.env` and a fresh JWT is obtained automatically on every start
- **Three transports** — `stdio` for Bob, `http/SSE` for legacy remote clients, `streamable-http` for Claude.ai web
- **API key protection** — when running over HTTP/SSE, all requests require `Authorization: Bearer <MCP_API_KEY>`
- **OAuth 2.0 PKCE** — when running over `streamable-http`, full OAuth flow with browser consent page
- **Modular codebase** — one file per domain, easy to extend

---

## Project Structure

```
gatekeeperd-mcp/
├── .env                  # Your local config (never commit this)
├── .env.example          # Template — copy to .env and fill in values
├── run.sh                # Entrypoint wrapper script
├── src/
│   ├── server.py         # Thin orchestrator — wires all modules, handles startup auth
│   ├── config.py         # Loads .env + environment variables
│   ├── client.py         # Shared HTTP client (httpx wrapper)
│   ├── utils.py          # ok() / err() response helpers
│   ├── oauth_provider.py # In-memory OAuth 2.0 provider (streamable-http transport)
│   └── tools/
│       ├── auth.py       # login, logout, get_current_user
│       ├── projects.py   # CRUD, block/unblock, adjustments, transfer, gate_check
│       ├── payments.py   # initialize, cash capture, list, reconcile, events, revenue
│       ├── invoices.py   # create, resync, download invoice PDF, download receipt PDF
│       ├── containers.py # create, start/stop/restart/delete, logs, images, wizard
│       ├── deployments.py# deployment history, deploy, redeploy, rollback, image prune
│       ├── operations.py # backend logs, version, runtime port mappings, reconciliation
│       ├── nginx.py      # enable/disable/remove sites, custom locations, certs, config
│       ├── customers.py  # list, get, create, assign to project
│       ├── audit.py      # global log, per-project log, CSV export
│       └── system.py     # dashboard, notifications, metrics, version, registry credentials
└── .venv/                # Python virtual environment (created during setup)
```

---

## Requirements

- Python 3.11+
- The Gatekeeperd backend reachable at `GATEKEEPERD_URL`
- Admin credentials for Gatekeeperd (`GATEKEEPERD_ADMIN_EMAIL` + `GATEKEEPERD_ADMIN_PASSWORD`)

---

## Setup

### 1. Clone / navigate to the project

```bash
cd /home/mike/Development/gatekeeperd-mcp
```

### 2. Create and activate the virtual environment

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
GATEKEEPERD_URL=https://your-gatekeeperd-instance.com/api
GATEKEEPERD_ADMIN_EMAIL=admin@example.com
GATEKEEPERD_ADMIN_PASSWORD=your-admin-password

# Only needed for the legacy SSE transport
MCP_API_KEY=your-generated-api-key

# Change to 'http' (legacy SSE) or 'streamable-http' (Claude.ai / OAuth)
MCP_TRANSPORT=stdio
MCP_HOST=0.0.0.0
MCP_PORT=9000

# Only needed for MCP_TRANSPORT=streamable-http
MCP_OAUTH_ISSUER=https://mcp.example.com
MCP_OAUTH_CLIENT_ID=claude
```

Generate a secure `MCP_API_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 4. Make the entrypoint executable

```bash
chmod +x run.sh
```

---

## Running

### Docker (HTTP/SSE)

Create `.env` from `.env.example`, then set `MCP_API_KEY` and Gatekeeperd credentials. Start the container with:

```bash
docker compose up -d --build
```

The MCP server listens on `http://localhost:9000/sse`; requests must include `Authorization: Bearer <MCP_API_KEY>`. The port is bound to localhost by default. To use a Gatekeeperd instance running on the Docker host, set `GATEKEEPERD_URL=http://host.docker.internal:8080/api` in `.env`. For a remote Gatekeeperd server, set its reachable URL instead.

Stop the container with `docker compose down`.

### stdio (default — for Bob / local use)

Bob spawns the server automatically once registered in `mcp.json`. No manual start needed.

To test manually:

```bash
./run.sh
```

Expected output:

```
gatekeeperd-mcp: logging in as admin@example.com ...
gatekeeperd-mcp: authenticated successfully
gatekeeperd-mcp: starting on stdio
```

### HTTP / SSE (legacy — Bob remote, MCP Inspector)

Set in `.env`:

```env
MCP_TRANSPORT=http
MCP_HOST=0.0.0.0
MCP_PORT=9000
MCP_API_KEY=<your-key>
```

Then start:

```bash
./run.sh
```

Clients connect to `http://your-host:9000/sse` with header:

```
Authorization: Bearer <your-key>
```

### Streamable HTTP + OAuth 2.0 (Claude.ai web)

This transport implements the current MCP spec (`POST /mcp`) with full OAuth 2.0 PKCE so Claude.ai can connect.

**Requirements:**
- A publicly reachable HTTPS URL (e.g. behind nginx + Let's Encrypt)
- `MCP_OAUTH_ISSUER` set to that URL

Set in `.env`:

```env
MCP_TRANSPORT=streamable-http
MCP_HOST=0.0.0.0
MCP_PORT=9000
MCP_OAUTH_ISSUER=https://mcp.example.com
MCP_OAUTH_CLIENT_ID=claude
MCP_OAUTH_CLIENT_SECRET=          # optional; leave blank for PKCE-only
MCP_OAUTH_TOKEN_TTL=3600
```

Then start:

```bash
./run.sh
```

**Endpoints exposed:**

| Endpoint | Purpose |
|---|---|
| `POST /mcp` | MCP Streamable HTTP (main transport) |
| `GET /.well-known/oauth-authorization-server` | OAuth discovery |
| `GET /authorize` | OAuth authorization redirect |
| `GET /authorize/consent` | Browser consent form |
| `POST /authorize/consent` | Consent form submission |
| `POST /token` | Token exchange |
| `POST /register` | Dynamic client registration |
| `POST /revoke` | Token revocation |

**Adding to Claude.ai:**

1. Go to **Claude.ai → Settings → Integrations**
2. Click **Add integration** and enter `https://mcp.example.com`
3. Claude opens the consent page in your browser — click **Allow**
4. Claude is now connected and can use all Gatekeeperd tools

> **Note:** Tokens are stored in-process memory and reset on server restart. After a restart, Claude will re-trigger the OAuth flow automatically on the next tool call.

---

## Bob Integration

The server is registered globally in `~/.bob/settings/mcp.json`:

```json
{
  "mcpServers": {
    "gatekeeperd": {
      "command": "/home/mike/Development/gatekeeperd-mcp/run.sh",
      "args": [],
      "env": {
        "GATEKEEPERD_URL": "http://localhost:8080/api"
      }
    }
  }
}
```

> The `env` block in `mcp.json` is optional — all config is read from `.env` automatically. Only set values here if you need to override `.env` for a specific workspace.

Bob hot-reloads the server on config save. Once connected you can ask things like:

- *"List all blocked projects"*
- *"Generate a payment link for project acme-corp"*
- *"Create an invoice for acme-corp — description: Q3 hosting services"*
- *"Deploy mikesplore/acme-app from the main branch"*
- *"What's the nginx and SSL status for acme-corp?"*
- *"Show me all failed payment webhook events"*
- *"Record a cash payment of KES 5000 for project acme-corp"*

---

## Tool Reference

Deployment tools now use Gatekeeperd's project setup API. Configure desired source/runtime settings first, then queue a deployment by project ID. Runtime inspection reports recorded container-to-host port mappings, including ready candidates waiting for Nginx cutover. Managed deployments use stable, Gatekeeperd-allocated loopback ports; do not change container ports manually to chase a moving Docker mapping.

Use `get_gatekeeperd_logs` to inspect the authenticated, redacted journal endpoint. For a deployment that is Ready but not Active, inspect its runtime, logs, and reconciliation report before taking action. `repair_deployment_nginx_upstream` is an explicit mutation that points a managed site at its active runtime and probes it through Nginx.

| Module | Tools |
|---|---|
| **auth** | `login` `logout` `get_current_user` |
| **projects** | `list_projects` `get_project` `get_project_health` `create_project` `update_project` `block_project` `unblock_project` `archive_project` `transfer_project` `bulk_block_projects` `bulk_unblock_projects` `get_overdue_projects` `add_project_adjustment` `update_deployment_source` `get_project_wizard_context` `gate_check` |
| **payments** | `initialize_payment` `record_cash_payment` `list_payments` `list_project_payments` `reconcile_payment` `list_payment_events` `replay_payment_event` `get_revenue_report` |
| **invoices** | `get_project_invoice` `create_project_invoice` `resync_project_invoice` `download_invoice` `download_payment_receipt` |
| **containers** | `list_containers` `get_container` `get_container_credentials` `get_container_logs` `start_container` `stop_container` `restart_container` `delete_container` `create_container` `validate_container_create` `check_ports_availability` `get_container_wizard_context` `check_image_exists` `pull_image` `delete_image` `list_networks` |
| **deployments** | `get_project_deployment_history` `get_project_deployment` `create_deployment` `redeploy_project` `rollback_project_deployment` `rotate_project_secrets_and_redeploy` `list_provider_credential_references` `prune_docker_images` |
| **operations** | `get_gatekeeperd_logs` `get_project_service_runtime` `get_deployment_reconciliation` |
| **nginx** | `get_nginx_status` `enable_nginx_site` `disable_nginx_site` `remove_nginx_site` `get_nginx_config` `add_custom_nginx_location` `remove_custom_nginx_location` `run_nginx_diagnostics` `rollback_nginx_config` `list_nginx_config_versions` `get_nginx_wizard_context` `list_certificates` `install_certificate` `renew_certificate` `remove_certificate` `check_certificate_status` `repair_deployment_nginx_upstream` |
| **customers** | `list_customers` `get_customer` `create_customer` `assign_customer_to_project` |
| **audit** | `get_audit_log` `get_project_audit_log` `export_audit_log` |
| **system** | `get_dashboard_summary` `list_notifications` `get_metrics` `health_check` `health_ready` `get_backend_version` `list_registries` `upsert_registry_credential` `delete_registry_credential` |

---

## Authentication Flow

```
startup
  │
  ├─ GATEKEEPERD_TOKEN set? ──► use token as-is (you manage rotation)
  │
  ├─ GATEKEEPERD_ADMIN_EMAIL + PASSWORD set? ──► POST /auth/login ──► cache JWT
  │
  └─ neither set ──► start unauthenticated ──► call login() as first tool
```

JWTs issued by Gatekeeperd expire after 24 hours. Using credentials is recommended — a fresh token is obtained automatically on every process restart.

---

## Security Notes
- `MCP_API_KEY` is only enforced when `MCP_TRANSPORT=http`; stdio connections are process-level isolated
- `streamable-http` tokens are in-memory only; a server restart forces a fresh OAuth consent
- Registry credential passwords stored in Gatekeeperd are AES-256-GCM encrypted at rest and never returned by the API
