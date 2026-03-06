from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    website_tracking_is_active = fields.Boolean(
        string='Activate Tracking',
        related='website_id.tracking_is_active',
        readonly=False,
    )
    website_tracking_is_logged = fields.Boolean(
        string='Logging',
        related='website_id.tracking_is_logged',
        readonly=False,
    )
    website_tracking_log_clean_up_period = fields.Integer(
        config_parameter='website_sale_tracking_base.log_clean_up_period',
    )
    website_tracking_log_clean_up_unlink = fields.Boolean(
        string="Completely delete log entries older than the specified period",
        config_parameter='website_sale_tracking_base.log_clean_up_unlink',
    )
    website_tracking_user_name_order = fields.Selection(
        related='website_id.tracking_user_name_order',
        readonly=False,
    )
