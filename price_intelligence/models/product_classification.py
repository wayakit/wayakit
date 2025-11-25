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

    base_margin_07 = fields.Float(
        string='Standard Base Margin (0.7L)',
        default=0.30,  # 30% por defecto
        digits=(12, 4),
        help="Base margin for standard presentation of 0.7L. Other volumes are calculated automatically."
    )

    # 2. Reglas de Volumen (Configuración Centralizada)
    # Aquí defines cuánto sumar al margen base para cada tamaño.
    variance_box = fields.Float(
        string='Regla Caja (8.4L)',
        default=0.00,  # +0%
        help="How much to add to price of boxes."
    )
    variance_4l = fields.Float(
        string='Regla Galón (4L)',
        default=0.15,  # +15%
        help="How much to add to price of gallons."
    )
    variance_20l = fields.Float(
        string='Regla Bidón (20L)',
        default=0.20,  # +20% (Tu nueva regla)
        help="How much to add to price of bids."
    )

    _sql_constraints = [
        ('name_uniq', 'unique (name)', '"Type of Product" must be unique!')
    ]

    @api.onchange('subindustry_id')
    def _onchange_subindustry_id(self):
        if self.subindustry_id:
            self.industry_id = self.subindustry_id.industry_id
        else:
            self.industry_id = False