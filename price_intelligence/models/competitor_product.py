# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class CompetitorProduct(models.Model):
    _name = 'competitor.product'
    _description = 'Competitor Product Intelligence'
    _rec_name = 'name'

    name = fields.Char(string="Product Name", required=True)
    date = fields.Date(string="Date", default=fields.Date.context_today, required=True)
    country_id = fields.Many2one('res.country', string="Country", required=True)
    company = fields.Char(string="Company")
    source = fields.Char(string="Source (e.g., Website)")
    link = fields.Char(string="Link")
    product_channel = fields.Selection([
        ('b2b', 'B2B'),
        ('retail', 'Retail'),
        ('ecommerce', 'E-commerce')
    ], string="Product Channel", required=True)

    classification_id = fields.Many2one(
        'product.classification',
        string="Type of product",
        required=True,
        help="Select the product classification. Other fields will be auto-filled."
    )

    industry_id = fields.Many2one(
        'product.industry',
        string="Industry",
        related='classification_id.industry_id',
        store=True,
        readonly=True
    )
    subindustry_id = fields.Many2one(
        'product.subindustry',
        string="Sub Industry",
        related='classification_id.subindustry_id',
        store=True,
        readonly=True
    )
    product_category = fields.Char(
        string="Product Category",
        related='classification_id.category',
        store=True,
        readonly=True
    )
    generic_product_type = fields.Char(
        string="Generic Product Type",
        related='classification_id.generic_product_type',
        store=True,
        readonly=True
    )

    pack_size = fields.Integer(string="Pack Size (Number of units)", default=1, required=True)
    quantity_per_unit = fields.Float(string="Quantity per Unit", required=True)
    uom = fields.Selection([
        ('ml', 'mL'),
        ('g', 'g'),
        ('units', 'Units')
    ], string="Unit of Measurement", default='units', required=True)

    total_quantity = fields.Float(
        string="Total Quantity",
        compute='_compute_total_quantity',
        store=True,
        help="= Pack Size * Quantity per Unit")
    ecofriendly = fields.Char(string="Ecofriendly")
    rating = fields.Float(string="Rating")
    number_of_ratings = fields.Integer(string="Number of Ratings")
    popularity = fields.Float(
        string="Popularity",
        compute='_compute_popularity',
        store=True,
        help="= Rating * Number of Ratings")

    price_source = fields.Float(string="Original Price", digits='Product Price', required=True)

    currency_id = fields.Many2one(
        'res.currency',
        string="Original Currency",
        required=True,
        default=lambda self: self.env.company.currency_id)

    price_unit_usd = fields.Monetary(
        string="Price per Unit (USD)",
        compute='_compute_converted_prices',
        currency_field='usd_currency_id')
    price_unit_sar = fields.Monetary(
        string="Price per Unit (SAR)",
        compute='_compute_converted_prices',
        currency_field='sar_currency_id')
    price_unit_cop = fields.Monetary(
        string="Price per Unit (COP)",
        compute='_compute_converted_prices',
        currency_field='cop_currency_id')

    price_per_liter_usd = fields.Monetary(
        string="Price per L/kg (USD)",
        compute='_compute_converted_prices',
        currency_field='usd_currency_id',
        help="Price per Liter (if uom=mL) or per Kg (if uom=g). 0 for Units.")
    price_per_liter_sar = fields.Monetary(
        string="Price per L/kg (SAR)",
        compute='_compute_converted_prices',
        currency_field='sar_currency_id')
    price_per_liter_cop = fields.Monetary(
        string="Price per L/kg (COP)",
        compute='_compute_converted_prices',
        currency_field='cop_currency_id')

    price_per_ml = fields.Float(
        string="Price per mL/g (USD)",
        compute='_compute_converted_prices',
        digits=(16, 8),
        help="Price per mL or g in USD. 0 for Units.")

    usd_currency_id = fields.Many2one('res.currency', compute='_get_target_currencies')
    sar_currency_id = fields.Many2one('res.currency', compute='_get_target_currencies')
    cop_currency_id = fields.Many2one('res.currency', compute='_get_target_currencies')

    @api.depends('pack_size', 'quantity_per_unit')
    def _compute_total_quantity(self):
        for rec in self:
            rec.total_quantity = rec.pack_size * rec.quantity_per_unit

    @api.depends('rating', 'number_of_ratings')
    def _compute_popularity(self):
        for rec in self:
            rec.popularity = rec.rating * rec.number_of_ratings

    def _get_target_currencies(self):
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        sar = self.env.ref('base.SAR', raise_if_not_found=False)
        cop = self.env.ref('base.COP', raise_if_not_found=False)
        for rec in self:
            rec.usd_currency_id = usd or False
            rec.sar_currency_id = sar or False
            rec.cop_currency_id = cop or False

    @api.depends('price_source', 'currency_id', 'uom', 'total_quantity', 'date')
    def _compute_converted_prices(self):
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        sar = self.env.ref('base.SAR', raise_if_not_found=False)
        cop = self.env.ref('base.COP', raise_if_not_found=False)

        if not all([usd, sar, cop]):
            self.update({
                'price_unit_usd': 0, 'price_unit_sar': 0, 'price_unit_cop': 0,
                'price_per_liter_usd': 0, 'price_per_liter_sar': 0, 'price_per_liter_cop': 0,
                'price_per_ml': 0,
            })
            return

        for rec in self:
            price_unit_usd = 0.0
            price_unit_sar = 0.0
            price_unit_cop = 0.0
            price_per_liter_usd = 0.0
            price_per_liter_sar = 0.0
            price_per_liter_cop = 0.0
            price_per_ml = 0.0

            if rec.price_source > 0 and rec.currency_id and rec.date:
                price_unit_usd = rec.currency_id._convert(
                    rec.price_source, usd, rec.env.company, rec.date)
                price_unit_sar = rec.currency_id._convert(
                    rec.price_source, sar, rec.env.company, rec.date)
                price_unit_cop = rec.currency_id._convert(
                    rec.price_source, cop, rec.env.company, rec.date)

                if rec.uom in ('ml', 'g') and rec.total_quantity > 0:
                    price_per_ml_g_usd = (price_unit_usd / rec.total_quantity)
                    price_per_ml_g_sar = (price_unit_sar / rec.total_quantity)
                    price_per_ml_g_cop = (price_unit_cop / rec.total_quantity)

                    price_per_ml = price_per_ml_g_usd

                    price_per_liter_usd = price_per_ml_g_usd * 1000
                    price_per_liter_sar = price_per_ml_g_sar * 1000
                    price_per_liter_cop = price_per_ml_g_cop * 1000

            rec.price_unit_usd = price_unit_usd
            rec.price_unit_sar = price_unit_sar
            rec.price_unit_cop = price_unit_cop
            rec.price_per_liter_usd = price_per_liter_usd
            rec.price_per_liter_sar = price_per_liter_sar
            rec.price_per_liter_cop = price_per_liter_cop
            rec.price_per_ml = price_per_ml

    @api.constrains('quantity_per_unit', 'price_source')
    def _check_quantity_and_price_positive(self):
        for record in self:
            if record.quantity_per_unit <= 0:
                raise ValidationError("'Quantity per Unit' must be greater than 0.")
            if record.price_source <= 0:
                raise ValidationError("'Original Price' must be greater than 0.")