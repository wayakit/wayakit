# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ProductClassification(models.Model):
    _name = 'product.classification'
    _description = 'Product Classification'
    _order = 'name'

    name = fields.Char(string='Type of Product', required=True,
                       help="Ej: 'H1-All purpose cleaner'")

    category = fields.Char(string='Category', required=True,
                           help="Ej: 'Households - 1. All-purpose cleaners'")

    subindustry_id = fields.Many2one('product.subindustry', string='Sub-Industry', required=True)

    industry_id = fields.Many2one('product.industry', string='Industry',
                                  related='subindustry_id.industry_id',
                                  store=True, readonly=True)

    generic_product_type = fields.Char(string='Generic Product Type', required=True,
                                       help="Ej: 'General purpose cleaner'")

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'El "Type of Product" debe ser único!')
    ]

    @api.onchange('subindustry_id')
    def _onchange_subindustry_id(self):
        if self.subindustry_id:
            self.industry_id = self.subindustry_id.industry_id
        else:
            self.industry_id = False