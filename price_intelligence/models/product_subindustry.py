# -*- coding: utf-8 -*-

from odoo import models, fields

class ProductSubindustry(models.Model):
    _name = 'product.subindustry'
    _description = 'Product Sub-Industry'
    _order = 'name'

    name = fields.Char(string='Sub-Industry', required=True)
    industry_id = fields.Many2one('product.industry', string='Industry', required=True)