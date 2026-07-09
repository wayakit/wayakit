from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

OPERATIONS = ("read", "create", "write", "unlink")


class IndexworldMcpEnabledModel(models.Model):
    """Which Odoo models (and operations) are exposed through the MCP server.

    Namespaced as ``ai.mcp.enabled.model`` so it never collides with any
    other MCP module that may also be installed.
    """

    _name = "ai.mcp.enabled.model"
    _description = "AI MCP Connector Enabled Model"
    _rec_name = "model_id"
    _order = "model_name"

    model_id = fields.Many2one(
        "ir.model",
        string="Model",
        required=True,
        index=True,
        ondelete="cascade",
        help="The Odoo model to expose through MCP.",
    )
    model_name = fields.Char(
        related="model_id.model", string="Technical Name", store=True, readonly=True
    )
    active = fields.Boolean(
        default=True, help="Uncheck to disable MCP access to this model without deleting the rule."
    )
    allow_read = fields.Boolean(string="Allow Read", default=True)
    allow_create = fields.Boolean(string="Allow Create", default=False)
    allow_write = fields.Boolean(string="Allow Update", default=False)
    allow_unlink = fields.Boolean(string="Allow Delete", default=False)
    notes = fields.Text()

    _sql_constraints = [
        (
            "unique_model",
            "UNIQUE(model_id)",
            "This model is already configured for MCP access.",
        ),
    ]

    @api.model
    def check_operation(self, model_name, operation):
        """Return True if ``operation`` is enabled for ``model_name``.

        ``operation`` must be one of read / create / write / unlink.
        """
        if operation not in OPERATIONS:
            raise ValidationError(_("Invalid operation: %s") % operation)
        record = self.search(
            [("model_name", "=", model_name), ("active", "=", True)], limit=1
        )
        if not record:
            return False
        return bool(record["allow_" + operation])

    @api.model
    def enabled_model_names(self):
        """Return the technical names of all active, exposed models."""
        return self.search([("active", "=", True)]).mapped("model_name")
