from odoo import models, fields,api
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    customer_kaust_id = fields.Char(string="Customer KAUST ID")

    @api.constrains('customer_kaust_id')
    def _check_customer_kaust_id(self):
        for record in self:
            if record.customer_kaust_id and self.search_count(
                    [('customer_kaust_id', '=', record.customer_kaust_id)]) > 1:
                raise ValidationError('The KAUST ID must be unique.')
