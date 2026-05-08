from odoo import models, fields


class Website(models.Model):
    _inherit = 'website'

    filter_website_addresses = fields.Boolean(string="Filter Website Addresses")
    allowed_country_ids = fields.Many2many(
        'res.country',
        string="Allowed Countries",
        help="Only addresses from these countries will show on this website."
    )