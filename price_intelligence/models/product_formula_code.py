# -*- coding: utf-8 -*-
from odoo import models, fields

class ProductFormulaCode(models.Model):
    _name = 'product.formula.code'
    _description = 'Product Formula Code'

    product_template_id = fields.Many2one(
        'product.template',
        string='Product Template',
        ondelete='cascade',
        index=True
    )

    sku = fields.Char(string='SKUS')

    base_product = fields.Char(string='Base product')

    formula_status = fields.Selection([
        ('pending', 'Pending'),
        ('not_available', 'No formula yet'),
        ('available', 'Available')
    ], string='Formula Status', default='pending')

    notes = fields.Text(string='Notes')

    price_per_liter = fields.Float(
        string='Price per liter without bottle',
        digits='Product Price'
    )