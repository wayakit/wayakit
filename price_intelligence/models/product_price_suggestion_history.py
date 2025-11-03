# -*- coding: utf-8 -*-
from odoo import models, fields


class ProductPriceSuggestionHistory(models.Model):
    """
    Almacena un registro histórico de las sugerencias de precios
    que fueron borradas de la tabla principal 'product.price.suggestion'.
    """
    _name = 'product.price.suggestion.history'
    _description = 'Price Suggestion History'
    _order = 'create_date desc'

    # Campos que vienen del script 'odoo_api_price_suggestion.py'
    product_id_str = fields.Char(
        string="Product ID",
        readonly=True)
    product_type = fields.Char(
        string="Product Type",
        readonly=True)
    generic_product_type = fields.Char(
        string="Generic Product Type",
        readonly=True)
    subindustry = fields.Char(
        string="Subindustry",
        readonly=True)
    industry = fields.Char(
        string="Industry",
        readonly=True)
    volume_units = fields.Float(
        string="Volume/Units",
        readonly=True)
    production_cost = fields.Float(
        string="Production Cost (SAR)",
        readonly=True)
    suggested_price = fields.Float(
        string="Suggested Price (SAR)",
        readonly=True)
    profit = fields.Float(
        string="Profit Margin (%)",
        readonly=True)

    # Campo para almacenar la fecha de creación del registro ORIGINAL
    original_create_date = fields.Datetime(
        string="Original Creation Date",
        readonly=True)