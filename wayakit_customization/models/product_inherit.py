from odoo import models, fields, api

class ProductProduct(models.Model):
    _inherit = 'product.product'

    duration = fields.Float(string="Duration", default=0)