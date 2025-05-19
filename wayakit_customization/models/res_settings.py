
from odoo import _, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    notification_token = fields.Char("Notification Token", config_parameter="wayakit_customization.notification_token")
    notification_url = fields.Char("Notification URL", config_parameter="wayakit_customization.notification_url")