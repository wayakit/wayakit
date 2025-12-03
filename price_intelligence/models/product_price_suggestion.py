# -*- coding: utf-8 -*-

from odoo import models, fields

class ProductPriceSuggestion(models.Model):
    _name = 'product.price.suggestion'
    _description = 'Product Price Suggestion'
    _order = 'last_update_date desc'

    last_update_date = fields.Datetime(string='Last Update Date', readonly=True, default=fields.Datetime.now)
    product_id_str = fields.Char(string='Product ID', required=True)
    product_type = fields.Char(string='Product Type')
    generic_product_type = fields.Char(string='Generic Product Type')
    subindustry = fields.Char(string='Sub-industry')
    industry = fields.Char(string='Industry')
    volume_units = fields.Float(string='Volume (L)/Units')
    production_cost = fields.Float(string='Production Cost')
    suggested_price = fields.Float(string='Suggested Sale Price')
    profit = fields.Float(string='Profit')
    product_name = fields.Char(string='Product Name')
    predicted_price_per_unit = fields.Float(string='Sugg. Price Per L/U')
    model_confidence = fields.Float(string='Model Confidence (%)')
    market_min_found = fields.Float(string='Market Min Found')
    market_max_found = fields.Float(string='Market Max Found')
    competitors_count = fields.Integer(string='Competitors Count')