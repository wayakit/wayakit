from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    facebook_pixel_key = fields.Char(
        related='website_id.facebook_pixel_key',
        readonly=False,
    )
    fbp_cookies_consent_is_revoked = fields.Boolean(
        related='website_id.fbp_cookies_consent_is_revoked',
        readonly=False,
    )

    @api.depends('website_id')
    def _compute_has_facebook_pixel(self):
        for config in self:
            config.has_facebook_pixel = bool(config.facebook_pixel_key)

    def _inverse_has_facebook_pixel(self):
        for config in self:
            if config.has_facebook_pixel:
                continue
            config.facebook_pixel_key = False

    has_facebook_pixel = fields.Boolean(
        string='Facebook Pixel',
        compute=_compute_has_facebook_pixel,
        inverse=_inverse_has_facebook_pixel,
    )
