from odoo import models, fields

class ProductProduct(models.Model):
    _inherit = 'product.product'

    duration = fields.Float(string="Duration", default=0)

    master_product_id = fields.Many2one('product.master', string="Master Product (Temporal)")