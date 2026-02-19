# -*- coding: utf-8 -*-
from odoo import models, fields

class ProductDilutionRecommendation(models.Model):
    _name = 'product.dilution.recommendation'
    _description = 'Dilution Recommendation by Use'
    _order = 'name'

    name = fields.Char(
        string='Use Case',
        required=True,
        help="Example: Floor Cleaning, Window Cleaning, Heavy Duty Degreasing..."
    )
    dilution_rate_ml = fields.Float(
        string='Recommended ml/L',
        required=True,
        help="Quantity of mililiters suggested for 1 liter of water."
    )