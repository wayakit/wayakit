# -*- coding: utf-8 -*-

from odoo import models, fields

class ProductIndustry(models.Model):
    _name = 'product.industry'
    _description = 'Product Industry'
    _order = 'name'

    name = fields.Char(string='Industry', required=True)