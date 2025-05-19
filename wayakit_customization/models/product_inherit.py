from odoo import models, fields

class ProductProduct(models.Model):
    _inherit = 'product.product'

    duration = fields.Float(string="Duration", default=0)
