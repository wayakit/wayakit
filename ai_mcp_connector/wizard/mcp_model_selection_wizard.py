from odoo import api, fields, models


class IndexworldMcpModelSelectionWizard(models.TransientModel):
    """Enable many models for MCP access at once."""

    _name = "ai.mcp.model.selection.wizard"
    _description = "AI MCP Connector Model Selection Wizard"

    @api.model
    def _get_model_domain(self):
        # Only filter out models already enabled. Transient (wizard) models are
        # intentionally selectable too: driving an Odoo wizard over MCP (e.g.
        # sale.advance.payment.inv to invoice an order) requires exposing it.
        enabled_ids = self.env["ai.mcp.enabled.model"].search([]).mapped("model_id.id")
        domain = []
        if enabled_ids:
            domain.append(("id", "not in", enabled_ids))
        return domain

    model_ids = fields.Many2many(
        "ir.model", string="Models", required=True,
        domain=lambda self: self._get_model_domain(),
        help="Pick the models to expose through MCP.",
    )
    allow_read = fields.Boolean(string="Allow Read", default=True)
    allow_create = fields.Boolean(string="Allow Create", default=False)
    allow_write = fields.Boolean(string="Allow Update", default=False)
    allow_unlink = fields.Boolean(string="Allow Delete", default=False)

    def action_enable_models(self):
        self.ensure_one()
        Enabled = self.env["ai.mcp.enabled.model"]
        for model in self.model_ids:
            if not Enabled.search([("model_id", "=", model.id)], limit=1):
                Enabled.create({
                    "model_id": model.id,
                    "allow_read": self.allow_read,
                    "allow_create": self.allow_create,
                    "allow_write": self.allow_write,
                    "allow_unlink": self.allow_unlink,
                })
        return {"type": "ir.actions.act_window_close"}
