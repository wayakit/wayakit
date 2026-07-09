{
    "name": "AI MCP Connector",
    "version": "17.0.3.0.0",
    "summary": "Connect Odoo to AI assistants (Claude, ChatGPT and any MCP client) over a "
               "single HTTPS URL. Native MCP server with per-model access control, API keys and logging.",
    "description": """
AI MCP Connector
================

A self-contained Model Context Protocol (MCP) server that runs inside Odoo and
speaks the MCP Streamable-HTTP transport directly, so remote MCP clients - such as
the Claude and ChatGPT apps (web, desktop and mobile) - can connect over a single
HTTPS URL with no desktop bridge.

Designed to be safe for production
----------------------------------
* **Native Odoo API keys** - authentication uses Odoo's own API-key system
  (revocable per user under Account Security). No custom credential store.
* **Granular access control** - administrators choose exactly which models are
  exposed and which operations (read / create / write / delete) are allowed.
  Nothing is exposed until explicitly enabled.
* **Activity logging** - every authentication and model operation can be logged
  for auditing, with automatic retention cleanup.
* **Isolated** - all models and config keys are namespaced under ``ai.mcp``
  so the module cannot collide with any other MCP module. Depends only on
  ``base`` and ``web`` with no external Python dependencies.

Usage
-----
1. Settings -> AI MCP Connector: enable the server and add the models you want to
   expose (with the desired permissions).
2. MCP Server -> Connect AI Assistant: generate/paste an API key and copy the
   connection URL.
3. Paste the URL into the "Add custom connector" field in Claude or ChatGPT. Done.
    """,
    "author": "IndexWorld",
    "website": "https://indexworld.net",
    "category": "Productivity/Tools",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "data": [
        "security/mcp_security.xml",
        "security/ir.model.access.csv",
        "wizard/mcp_model_selection_wizard_views.xml",
        "views/mcp_enabled_model_views.xml",
        "views/mcp_log_views.xml",
        "views/mcp_connection_views.xml",
        "wizard/mcp_connect_wizard_views.xml",
        "views/res_config_settings_views.xml",
        "views/mcp_menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ai_mcp_connector/static/src/css/mcp_wizard.css",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
}
