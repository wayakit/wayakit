from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    filter_website_addresses = fields.Boolean(string="Filter Website Addresses")
    # This is the selection field for all countries
    allowed_country_id = fields.Many2one(
        'res.country',
        string="Allowed Country",
        help="Only addresses from this country will show on the checkout page."
    )