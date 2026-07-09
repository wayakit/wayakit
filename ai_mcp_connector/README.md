# AI MCP Connector Server

A **native Model Context Protocol (MCP) server built into Odoo 17**. It lets MCP
clients — including the **Claude mobile and web apps** — use your Odoo instance
over a single HTTPS URL, with **no desktop bridge process**.

Built to be safe on a production server:

- **Native Odoo API keys** for authentication (`res.users.apikeys`, scope `rpc`).
  Keys are managed/revoked per user under *Preferences → Account Security*.
- **Per-model, per-operation access control.** Nothing is exposed until an admin
  enables a model and ticks which operations (read / create / write / delete)
  are allowed. The connecting user's own Odoo ACLs apply on top.
- **Activity logging** with automatic retention cleanup.
- **Fully isolated** — every model/param is namespaced `ai.mcp.*`, so it can't
  collide with any other MCP module. Depends only on `base` + `web`, no external
  Python packages.

## Install

The module is in your addons path. Install/upgrade:

```bash
cd /home/tughal-khan/WS/odoo17
./venv17/bin/python3 odoo-bin -c odoo.conf -d <db> -i ai_mcp_connector --stop-after-init
```

> After installing, **fully restart** the Odoo server (controllers load at boot).

## Configure (admin)

1. **Settings → AI MCP Connector**
   - *Enable MCP Server* (master switch, on by default).
   - *Allow Arbitrary Method Calls* — off by default; turn on only if you want the
     universal `call_method` tool.
   - Logging + retention options.
2. **MCP Server → MCP Models** — add each model you want to expose and tick the
   allowed operations. **Nothing is reachable until you do this.**

## Connect to Claude

1. **MCP Server → Connect to Claude**.
2. Click **Generate New API Key** (creates a native Odoo key for you) — or paste an
   existing one.
3. Copy the **Connection URL** (`https://host/mcp/<key>`).
4. In Claude → **Settings → Connectors → Add custom connector** → paste → confirm.

The key authenticates as *your* Odoo user, so the AI can only do what you can do —
further narrowed by the MCP Models rules above.

### Reaching a local server from your phone

Claude needs a public **HTTPS** URL. If Odoo is hosted on a domain
(`https://yourdomain/...`) just use it directly. If it's local, expose it with a
tunnel, e.g.:

```bash
cloudflared tunnel --url http://localhost:8069
```

Set `proxy_mode = True` and a single-DB `dbfilter` in `odoo.conf` so the URL works
header-free.

## Tools

`list_models`, `fields_get`, `search_read`, `search_count`, `read_records`,
`name_search`, `create_record`, `update_records`, `delete_records`,
`call_method` (gated), `who_am_i`. All are enforced against the MCP Models rules.

## Security notes

- Treat the connection URL like a password (it carries the API key). Revoke it
  under *Preferences → Account Security*.
- Prefer binding to a **scoped Odoo user** + minimal enabled models on production.
- Private methods (leading `_`) are always refused by `call_method`.
