import logging
from datetime import datetime, timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

MAX_TEXT = 10000


class IndexworldMcpLog(models.Model):
    _name = "ai.mcp.log"
    _description = "AI MCP Connector Activity Log"
    _order = "create_date desc"
    _rec_name = "event_type"

    event_type = fields.Selection(
        [
            ("auth_success", "Authentication Success"),
            ("auth_failure", "Authentication Failure"),
            ("model_access", "Model Access"),
            ("permission_denied", "Permission Denied"),
            ("rate_limit", "Rate Limit Exceeded"),
            ("error", "Error"),
        ],
        required=True,
        index=True,
    )
    user_id = fields.Many2one("res.users", string="User", index=True)
    ip_address = fields.Char(string="IP Address", size=45)
    model_name = fields.Char(string="Model", index=True)
    operation = fields.Char()
    tool_name = fields.Char()
    error_message = fields.Text()
    duration_ms = fields.Integer(string="Duration (ms)")

    @api.model
    def log_event(self, event_type, **kw):
        """Create a log entry, respecting the global logging switch. Never raises."""
        params = self.env["ir.config_parameter"].sudo()
        if params.get_param("ai_mcp_connector.enable_logging", "True") != "True":
            return self.browse()
        if getattr(self.env.cr, "readonly", False):
            return self.browse()
        vals = {
            "event_type": event_type,
            "user_id": kw.get("user_id"),
            "ip_address": kw.get("ip_address"),
            "model_name": kw.get("model_name"),
            "operation": kw.get("operation"),
            "tool_name": kw.get("tool_name"),
            "error_message": kw.get("error_message"),
            "duration_ms": kw.get("duration_ms"),
        }
        if vals.get("error_message") and len(str(vals["error_message"])) > MAX_TEXT:
            vals["error_message"] = str(vals["error_message"])[:MAX_TEXT] + "... [truncated]"
        try:
            return self.sudo().create(vals)
        except Exception as e:  # noqa: BLE001 - logging must never break a request
            _logger.warning("Failed to write MCP log: %s", e)
            return self.browse()

    @api.model
    def cleanup_old_logs(self, days=None):
        """Delete log entries older than the configured retention (cron target)."""
        if days is None:
            days = int(
                self.env["ir.config_parameter"].sudo().get_param(
                    "ai_mcp_connector.log_retention_days", "30"
                )
            )
        if days <= 0:
            return 0
        cutoff = datetime.now() - timedelta(days=days)
        old = self.sudo().search([("create_date", "<", cutoff)])
        count = len(old)
        old.unlink()
        _logger.info("Cleaned up %d AI MCP Connector log entries older than %d days", count, days)
        return count
