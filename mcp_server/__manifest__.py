{
    "name": "MCP Server",
    "version": "17.0.1.0.6",
    "summary": "Connect AI assistants to your Odoo instance via Model Context Protocol",
    "description": """
MCP Server for Odoo
===================

Enable AI assistants like Claude to securely access your Odoo data through natural language queries.

Key Features
------------
* Search and retrieve any Odoo records using natural language
* Granular permissions control per model and operation
* Secure API key authentication with rate limiting
* Easy configuration through Odoo settings

How It Works
------------
1. Install this module and configure model access
2. Generate API keys for authentication
3. Install the MCP client on your AI assistant
4. Start querying your Odoo data naturally

Requirements: Odoo 17.0 and mcp-server-odoo client package
    """,
    "author": "Andrey Ivanov",
    "website": "https://github.com/ivnvxd/mcp-server-odoo",
    "category": "Productivity",
    "depends": ["base", "base_setup", "mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "wizard/mcp_model_selection_wizard_views.xml",
        "views/mcp_enabled_models_views.xml",
        "views/mcp_log_views.xml",
        "views/res_config_settings_views.xml",
        "views/mcp_menu.xml",
    ],
    "demo": [],
    "images": [
        "static/description/banner.png",
        "static/description/icon.png",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "OPL-1",
    "price": 99.0,
    "currency": "EUR",
    "support": "ivnv.xd@gmail.com",
}
