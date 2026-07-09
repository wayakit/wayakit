from odoo import api, fields, models


class IndexworldMcpConnectWizard(models.TransientModel):
    """Helper that turns an Odoo API key into a ready-to-paste MCP connection URL.

    The admin either generates a fresh native Odoo API key (one click) or pastes
    an existing one. The wizard builds the full ``https://host/mcp/<key>`` URL.
    The key is never stored on a persistent model - this is a transient wizard.
    """

    _name = "ai.mcp.connect.wizard"
    _description = "AI MCP Connector Connect Wizard"

    api_key = fields.Char(
        string="API Key",
        help="Paste an existing Odoo API key, or click 'Generate New API Key'.",
    )
    base_url = fields.Char(string="Server URL", compute="_compute_urls")
    connection_url = fields.Char(
        string="Connection URL (paste into Claude)", compute="_compute_urls"
    )
    user_id = fields.Many2one(
        "res.users", string="For user", default=lambda self: self.env.user, readonly=True
    )

    @api.depends("api_key")
    def _compute_urls(self):
        base = (self.env["ir.config_parameter"].sudo().get_param("web.base.url") or "").rstrip("/")
        for rec in self:
            rec.base_url = base
            rec.connection_url = "%s/mcp/%s" % (base, rec.api_key) if rec.api_key else False

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_generate_key(self):
        """Mint a fresh, persistent native Odoo API key for the current user."""
        self.ensure_one()
        # sudo() keeps the current uid but elevates privileges so a persistent
        # (no-expiry) key is allowed; the key is created for self.env.user.
        key = self.env["res.users.apikeys"].sudo()._generate(
            "rpc", "AI MCP Connector"
        )
        self.api_key = key
        return self._reopen()

    def action_open_claude(self):
        """Deep-link straight to Claude's 'Add custom connector' modal.

        Claude has no documented way to pre-fill the server URL via query
        param, so the user still pastes the copied connection URL into the
        modal - this just opens the right screen in one click.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": "https://claude.ai/customize/connectors?modal=add-custom-connector",
            "target": "new",
        }

    def action_open_chatgpt(self):
        """Deep-link to ChatGPT's Connectors settings (best effort).

        Like Claude, ChatGPT exposes no documented URL param to pre-fill the
        connector; the user pastes the copied connection URL once the screen
        opens.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": "https://chatgpt.com/apps#settings/Connectors",
            "target": "new",
        }

    def _open_url(self, url):
        self.ensure_one()
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}

    def action_open_lechat(self):
        """Open Mistral Le Chat (Intelligence -> Connectors -> Custom MCP)."""
        return self._open_url("https://chat.mistral.ai/")

    def action_open_perplexity(self):
        """Open Perplexity (Settings -> Connectors). Best effort."""
        return self._open_url("https://www.perplexity.ai/")

    def action_open_grok(self):
        """Open Grok (Settings -> Connectors). Best effort."""
        return self._open_url("https://grok.com/")
