import re

from odoo import models, fields,api
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    customer_kaust_id = fields.Char(string="Customer KAUST ID")

    x_national_short_code = fields.Char(
        string="National Address Short Code",
        size=8,
        help="Saudi National Address short code (8 chars: 4 letters + 4 digits, e.g. RRRD2929). "
             "Found in the Absher or Saudi Post | SPL app.",
    )

    @api.constrains('customer_kaust_id')
    def _check_customer_kaust_id(self):
        for record in self:
            if record.customer_kaust_id and self.search_count(
                    [('customer_kaust_id', '=', record.customer_kaust_id)]) > 1:
                raise ValidationError('The KAUST ID must be unique.')

    @api.constrains('x_national_short_code')
    def _check_national_short_code(self):
        for record in self:
            code = record.x_national_short_code
            if code and not re.match(r'^[A-Za-z]{4}\d{4}$', code):
                raise ValidationError(
                    'The National Address Short Code must be exactly 4 letters '
                    'followed by 4 digits (e.g. RRRD2929).'
                )

    @api.onchange('x_national_short_code')
    def _onchange_national_short_code(self):
        if self.x_national_short_code:
            self.x_national_short_code = self.x_national_short_code.upper()
