from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ai_mcp_connector_enabled = fields.Boolean(
        string="Enable MCP Server",
        help="Master switch. When off, the /mcp endpoint refuses all tool calls.",
        config_parameter="ai_mcp_connector.enabled",
        default=True,
    )
    ai_mcp_connector_allow_method_calls = fields.Boolean(
        string="Allow Arbitrary Method Calls",
        help="When enabled, the universal 'call_method' tool can invoke any public "
        "method on an MCP-enabled model (e.g. action_confirm). Powerful but risky - "
        "leave off unless you need it.",
        config_parameter="ai_mcp_connector.allow_method_calls",
        default=False,
    )
    ai_mcp_connector_enable_rate_limiting = fields.Boolean(
        string="Enable Rate Limiting",
        help="Throttle each user to a maximum number of MCP requests per minute.",
        config_parameter="ai_mcp_connector.enable_rate_limiting",
        default=True,
    )
    ai_mcp_connector_request_limit = fields.Integer(
        string="Requests per Minute",
        help="Max MCP requests per user per minute. 0 = unlimited.",
        config_parameter="ai_mcp_connector.request_limit",
        default=300,
    )
    ai_mcp_connector_enable_logging = fields.Boolean(
        string="Enable Activity Logging",
        help="Log authentications and model operations for auditing.",
        config_parameter="ai_mcp_connector.enable_logging",
        default=True,
    )
    ai_mcp_connector_log_retention_days = fields.Integer(
        string="Log Retention (days)",
        help="Delete logs older than this many days. 0 = keep forever.",
        config_parameter="ai_mcp_connector.log_retention_days",
        default=30,
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        p = self.env["ir.config_parameter"].sudo()
        res.update(
            ai_mcp_connector_enabled=p.get_param("ai_mcp_connector.enabled", "True") == "True",
            ai_mcp_connector_allow_method_calls=p.get_param(
                "ai_mcp_connector.allow_method_calls", "False") == "True",
            ai_mcp_connector_enable_rate_limiting=p.get_param(
                "ai_mcp_connector.enable_rate_limiting", "True") == "True",
            ai_mcp_connector_request_limit=int(
                p.get_param("ai_mcp_connector.request_limit", "300")),
            ai_mcp_connector_enable_logging=p.get_param(
                "ai_mcp_connector.enable_logging", "True") == "True",
            ai_mcp_connector_log_retention_days=int(
                p.get_param("ai_mcp_connector.log_retention_days", "30")),
        )
        return res

    def set_values(self):
        res = super().set_values()
        p = self.env["ir.config_parameter"].sudo()
        p.set_param("ai_mcp_connector.enabled", str(self.ai_mcp_connector_enabled))
        p.set_param("ai_mcp_connector.allow_method_calls", str(self.ai_mcp_connector_allow_method_calls))
        p.set_param("ai_mcp_connector.enable_rate_limiting", str(self.ai_mcp_connector_enable_rate_limiting))
        p.set_param("ai_mcp_connector.request_limit", str(self.ai_mcp_connector_request_limit))
        p.set_param("ai_mcp_connector.enable_logging", str(self.ai_mcp_connector_enable_logging))
        p.set_param("ai_mcp_connector.log_retention_days", str(self.ai_mcp_connector_log_retention_days))
        return res
