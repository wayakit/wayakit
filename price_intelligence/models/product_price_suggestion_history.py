# -*- coding: utf-8 -*-
from odoo import models, fields


class ProductPriceSuggestionHistory(models.Model):
    _name = 'product.price.suggestion.history'
    _description = 'Price Suggestion History'
    _order = 'create_date desc'

    product_id_str = fields.Char(string="Product ID", readonly=True)
    product_type = fields.Char(string="Product Type", readonly=True)
    generic_product_type = fields.Char(string="Generic Product Type", readonly=True)
    subindustry = fields.Char(string="Subindustry", readonly=True)
    industry = fields.Char(string="Industry", readonly=True)
    volume_units = fields.Float(string="Volume/Units", readonly=True)
    production_cost = fields.Float(string="Production Cost (SAR)", readonly=True)
    suggested_price = fields.Float(string="Suggested Price (SAR)", readonly=True)
    profit = fields.Float(string="Profit Margin (%)", readonly=True)
    original_create_date = fields.Datetime(string="Original Creation Date", readonly=True)
    product_name = fields.Char(string='Product Name', readonly=True)
    predicted_price_per_unit = fields.Float(string='Sugg. Price Per L/U', readonly=True)
    model_confidence = fields.Float(string='Model Confidence (%)', readonly=True)
    market_min_found = fields.Float(string='Market Min Found', readonly=True)
    market_max_found = fields.Float(string='Market Max Found', readonly=True)
    competitors_count = fields.Integer(string='Competitors Count', readonly=True)