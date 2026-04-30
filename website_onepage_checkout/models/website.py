from odoo import models, fields


class Website(models.Model):
    _inherit = 'website'

    filter_website_addresses = fields.Boolean(string="Filter Website Addresses")
    allowed_country_id = fields.Many2one(
        'res.country',
        string="Allowed Country",
        help="Only addresses from this country will show on this specific website."
    )