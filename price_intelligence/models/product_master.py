# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ProductMaster(models.Model):
    _name = 'product.master'
    _description = 'Master Product Table'

    create_date = fields.Datetime(string="Creation Date")
    external_id = fields.Char(string='External ID')
    product_id = fields.Char(string='Product ID', required=True)
    product_name = fields.Char(string='Product Name', required=True)
    label_product_name = fields.Char(string='Label Product Name', required=True)

    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], string='Status', default='active')
    master_product = fields.Boolean(string='Master Product')
    uploaded_in_odoo = fields.Boolean(string='Uploaded in Odoo')
    notes = fields.Text(string='Notes')

    formula_code = fields.Many2one('product.formula.code', string='Formula Code')

    moq = fields.Float(string='MOQ')

    order_unit = fields.Char(string='Order Unit')
    presentation = fields.Char(string='Presentation')
    scent = fields.Selection([
        ('rose_musk', 'Rose musk'),
        ('unscented', 'Unscented'),
        ('jasmine', 'Jasmine'),
        ('baby_scent', 'Baby scent'),
        ('not_applicable', 'Attribute not applicable')
    ], string='Scent')
    type = fields.Selection([
        ('not_applicable', 'Attribute not applicable'),
        ('new', 'New'),
        ('refill', 'Refill (only liquid)')
    ], string='Type')

    link_to_product_mockup = fields.Char(string='Link to Product Mockup')

    volume_liters = fields.Float(string='Volume (Liters)')
    pack_quantity_units = fields.Integer(string='Pack Quantity (Units)')

    type_of_product_id = fields.Many2one('product.classification', string='Type of Product', required=True)

    category = fields.Char(
        string='Category',
        related='type_of_product_id.category',
        store=True,
        readonly=True
    )
    generic_product_type = fields.Char(
        string='Generic Product Type',
        related='type_of_product_id.generic_product_type',
        store=True,
        readonly=True
    )
    subindustry_id = fields.Many2one(
        'product.subindustry',
        string='Sub-Industry',
        related='type_of_product_id.subindustry_id',
        store=True,
        readonly=True
    )
    industry_id = fields.Many2one(
        'product.industry',
        string='Industry',
        related='type_of_product_id.industry_id',
        store=True,
        readonly=True
    )
    description = fields.Text(string='Description')
    dilution_rate = fields.Char(string='Dilution Rate')

    bottle_cost = fields.Float(string='Bottle', required=True)
    label_cost = fields.Float(string='Label', required=True)
    liquid_cost = fields.Float(string='Liquid',
                               compute='_compute_liquid_cost',
                               store=True,
                               readonly=True)
    microfibers_cost = fields.Float(string='Microfibers', required=True)
    plastic_bag_cost = fields.Float(string='Plastic Bag', required=True)
    labor_cost = fields.Float(string='Labor', required=True)
    shipping_cost = fields.Float(string='Shipping', required=True)
    other_costs = fields.Float(string='Other Costs', required=True)

    unit_cost_sar = fields.Float(string='Unit Cost (SAR)',
                                 compute='_compute_unit_cost_sar',
                                 store=True)

    # =========================================================
    # LOGICA DE PRECIOS E INTELIGENCIA
    # =========================================================

    # 1. Configuración Manual (Delegada a Clasificación)
    manual_base_margin = fields.Float(
        string='Strategy Base Margin (0.7L)',
        related='type_of_product_id.base_margin_07',
        readonly=False,
    )

    # 2. Margen Efectivo (Calculado)
    base_prediction_margin = fields.Float(
        string='Applied Margin (%)',
        compute='_compute_pricing_list',
        store=True,
        digits=(12, 4),
        help="Final margin used for the operation(Margin Base + Margin per volume)."
    )

    # 3. AI Prediction & Profit
    ai_predicted_price = fields.Float(string='AI Prediction (Price)', compute='_compute_ai_predicted_price')
    ai_predicted_margin = fields.Float(string='AI Margin (%)', compute='_compute_ai_predicted_price')

    # 4. PRECIOS POR TIER (Editables para refresco en vivo)
    price_tier_spark = fields.Float(string='Spark Price (Tier 1)', compute='_compute_pricing_list', store=True,
                                    readonly=False)
    price_tier_flow = fields.Float(string='Flow Price (Tier 2)', compute='_compute_pricing_list', store=True,
                                   readonly=False)
    price_tier_cycle = fields.Float(string='Cycle Price (Tier 3)', compute='_compute_pricing_list', store=True,
                                    readonly=False)
    price_tier_stream = fields.Float(string='Stream Price (Tier 4)', compute='_compute_pricing_list', store=True,
                                     readonly=False)
    price_tier_source = fields.Float(string='Source Price (Tier 5)', compute='_compute_pricing_list', store=True,
                                     readonly=False)

    # 5. DETALLES POR TIER (Márgenes y Precio/Litro) - NUEVO
    # Margenes
    margin_tier_spark = fields.Float(string='Spark Margin', compute='_compute_pricing_list', store=True, digits=(12, 2))
    margin_tier_flow = fields.Float(string='Flow Margin', compute='_compute_pricing_list', store=True, digits=(12, 2))
    margin_tier_cycle = fields.Float(string='Cycle Margin', compute='_compute_pricing_list', store=True, digits=(12, 2))
    margin_tier_stream = fields.Float(string='Stream Margin', compute='_compute_pricing_list', store=True,
                                      digits=(12, 2))
    margin_tier_source = fields.Float(string='Source Margin', compute='_compute_pricing_list', store=True,
                                      digits=(12, 2))

    # Precio por Litro
    pl_tier_spark = fields.Float(string='Spark P/L', compute='_compute_pricing_list', store=True, digits=(12, 2))
    pl_tier_flow = fields.Float(string='Flow P/L', compute='_compute_pricing_list', store=True, digits=(12, 2))
    pl_tier_cycle = fields.Float(string='Cycle P/L', compute='_compute_pricing_list', store=True, digits=(12, 2))
    pl_tier_stream = fields.Float(string='Stream P/L', compute='_compute_pricing_list', store=True, digits=(12, 2))
    pl_tier_source = fields.Float(string='Source P/L', compute='_compute_pricing_list', store=True, digits=(12, 2))

    # --- FUNCIONES COMPUTE ---

    @api.depends('formula_code', 'formula_code.price_per_liter', 'volume_liters')
    def _compute_liquid_cost(self):
        for record in self:
            if record.formula_code and record.volume_liters > 0:
                cost_liter = record.formula_code.price_per_liter
                record.liquid_cost = cost_liter * record.volume_liters
            else:
                record.liquid_cost = 0.0

    @api.depends('bottle_cost', 'label_cost', 'liquid_cost', 'microfibers_cost',
                 'plastic_bag_cost', 'labor_cost', 'shipping_cost', 'other_costs')
    def _compute_unit_cost_sar(self):
        for record in self:
            record.unit_cost_sar = (
                    record.bottle_cost +
                    record.label_cost +
                    record.liquid_cost +
                    record.microfibers_cost +
                    record.plastic_bag_cost +
                    record.labor_cost +
                    record.shipping_cost +
                    record.other_costs
            )

    @api.depends('unit_cost_sar', 'volume_liters', 'type_of_product_id',
                 'manual_base_margin',
                 'type_of_product_id.base_margin_07',
                 'type_of_product_id.variance_box',
                 'type_of_product_id.variance_4l',
                 'type_of_product_id.variance_20l')
    def _compute_pricing_list(self):
        for record in self:
            cost = record.unit_cost_sar
            vol = record.volume_liters or 1.0  # Evitar división por cero en P/L

            # 1. CALCULAR EL MARGEN OBJETIVO (Antes de revisar costos)
            # Esto arregla que aparezca en 0 cuando no hay costos
            base = record.type_of_product_id.base_margin_07 if record.type_of_product_id else 0.0

            added_margin = 0.0
            if record.type_of_product_id and record.volume_liters > 0:
                if 8.0 <= record.volume_liters <= 9.0:  # Caja
                    added_margin = record.type_of_product_id.variance_box
                elif 3.5 <= record.volume_liters <= 5.0:  # 4L
                    added_margin = record.type_of_product_id.variance_4l
                elif record.volume_liters >= 18.0:  # 20L
                    added_margin = record.type_of_product_id.variance_20l

            effective_margin = base + added_margin
            record.base_prediction_margin = effective_margin

            # Si no hay costo, precios en 0, pero el margen ya se calculó arriba
            if not cost:
                record.price_tier_spark = 0.0
                record.price_tier_flow = 0.0
                record.price_tier_cycle = 0.0
                record.price_tier_stream = 0.0
                record.price_tier_source = 0.0
                # Reset detalles
                record.margin_tier_spark = 0.0
                record.margin_tier_flow = 0.0
                record.margin_tier_cycle = 0.0
                record.margin_tier_stream = 0.0
                record.margin_tier_source = 0.0
                record.pl_tier_spark = 0.0
                record.pl_tier_flow = 0.0
                record.pl_tier_cycle = 0.0
                record.pl_tier_stream = 0.0
                record.pl_tier_source = 0.0
                continue

            # 2. Definir Extras por Tier
            if (0.6 <= record.volume_liters <= 0.8) or (8.0 <= record.volume_liters <= 9.0):
                extras = [0.25, 0.15, 0.10, 0.05]
            elif 3.5 <= record.volume_liters <= 5.0:
                extras = [0.08, 0.06, 0.04, 0.02]
            else:  # 20L y default
                extras = [0.04, 0.03, 0.02, 0.01]

            def calc_tier_data(c, m_eff, m_extra, volume):
                total_margin = m_eff + m_extra

                # SAFETY CAP: Si pasa de 99%, lo topamos a 99%
                if total_margin >= 0.99:
                    total_margin = 0.99

                # Fórmula: Costo / (1 - Margen)
                # Con el tope, el denominador mínimo es 0.01 (Costo * 100)
                price = c / (1.0 - total_margin)

                p_liter = price / volume if volume > 0 else 0.0
                return price, total_margin, p_liter

            # 4. Calcular y Asignar Tiers
            # Spark
            p, m, pl = calc_tier_data(cost, effective_margin, extras[0], vol)
            record.price_tier_spark = p
            record.margin_tier_spark = m
            record.pl_tier_spark = pl

            # Flow
            p, m, pl = calc_tier_data(cost, effective_margin, extras[1], vol)
            record.price_tier_flow = p
            record.margin_tier_flow = m
            record.pl_tier_flow = pl

            # Cycle
            p, m, pl = calc_tier_data(cost, effective_margin, extras[2], vol)
            record.price_tier_cycle = p
            record.margin_tier_cycle = m
            record.pl_tier_cycle = pl

            # Stream
            p, m, pl = calc_tier_data(cost, effective_margin, extras[3], vol)
            record.price_tier_stream = p
            record.margin_tier_stream = m
            record.pl_tier_stream = pl

            # Source (Sin extra)
            p, m, pl = calc_tier_data(cost, effective_margin, 0.0, vol)
            record.price_tier_source = p
            record.margin_tier_source = m
            record.pl_tier_source = pl

    def _compute_ai_predicted_price(self):
        for record in self:
            record.ai_predicted_price = 0.0
            record.ai_predicted_margin = 0.0

            if not record.product_id:
                continue

            suggestion = self.env['product.price.suggestion'].search([
                ('product_id_str', '=', record.product_id)
            ], limit=1, order='last_update_date desc')

            if suggestion:
                record.ai_predicted_price = suggestion.suggested_price

                if suggestion.suggested_price > 0:
                    current_profit = suggestion.suggested_price - record.unit_cost_sar
                    record.ai_predicted_margin = current_profit / suggestion.suggested_price

    _rec_name = 'product_name'

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, order=None, name_get_uid=None):
        if args is None:
            args = []
        domain = args[:]
        if name:
            domain = ['|',
                      '|',
                      ('product_name', operator, name),
                      ('external_id', operator, name),
                      ('product_id', operator, name)
                      ] + domain

        return self._search(domain, limit=limit, order=order, access_rights_uid=name_get_uid)
