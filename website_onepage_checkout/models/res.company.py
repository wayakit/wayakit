from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'
    filter_website_addresses = fields.Boolean(string="Filter Website Addresses")
    allowed_address_company_id = fields.Many2one(
        'res.partner',
        string="Allowed Address Company",
        domain="[('is_company', '=', True)]",
        help="If 'Filter Website Addresses' is checked, only addresses belonging to this company will show."
    )