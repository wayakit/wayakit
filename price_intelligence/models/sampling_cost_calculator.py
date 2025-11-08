# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


# NOTA: Los campos related ya han sido corregidos
# según tu archivo product_master.py

class SamplingCostCalculator(models.Model):
    _name = 'sampling.cost.calculator'
    _description = 'Sampling Cost Calculator'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        'Calculation Reference', required=True, copy=False, readonly=True,
        index=True, default=lambda self: _('New'))

    helpdesk_ticket_id = fields.Many2one(
        'helpdesk.ticket', 'Helpdesk Ticket', required=True, ondelete='restrict')

    date = fields.Date(
        'Date', required=True, default=fields.Date.context_today)

    calculator_line_ids = fields.One2many(
        'sampling.cost.calculator.line', 'calculator_id', 'Product Lines',
        copy=True)

    # --- CAMPOS CALCULADOS (TOTALES) ---

    total_volume_sample_l = fields.Float(
        'Total Sample Volume [L]', compute='_compute_totals',
        store=True, readonly=True)

    total_lines_cost = fields.Float(
        'Total Lines Cost', compute='_compute_totals',
        store=True, readonly=True)

    shipping_cost = fields.Float(
        'Shipping Cost', compute='_compute_totals',
        store=True, readonly=True,
        help="Calculated with the formula: (2.148 * Total Sample Volume) + 15.204")

    grand_total_cost = fields.Float(
        'Grand Total Cost', compute='_compute_totals',
        store=True, readonly=True)

    @api.depends('calculator_line_ids.line_total_cost', 'calculator_line_ids.volume_sample_l')
    def _compute_totals(self):
        """Calcula todos los totales del encabezado."""
        for calc in self:
            total_volume = sum(line.volume_sample_l for line in calc.calculator_line_ids)
            total_lines = sum(line.line_total_cost for line in calc.calculator_line_ids)

            # Fórmula de envío: =(2.148*Volume sample)+15.204
            shipping = (2.148 * total_volume) + 15.204 if total_volume > 0 else 0

            calc.total_volume_sample_l = total_volume
            calc.total_lines_cost = total_lines
            calc.shipping_cost = shipping
            calc.grand_total_cost = total_lines + shipping

    @api.model_create_multi
    def create(self, vals_list):
        """Asigna la secuencia al crear."""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sampling.cost.calculator') or _('New')
        return super(SamplingCostCalculator, self).create(vals_list)


class SamplingCostCalculatorLine(models.Model):
    _name = 'sampling.cost.calculator.line'
    _description = 'Sampling Cost Calculator Line'

    calculator_id = fields.Many2one(
        'sampling.cost.calculator', 'Calculator', required=True, ondelete='cascade')

    sequence = fields.Integer(string='Sequence', default=10)

    product_id = fields.Many2one(
        'product.master', 'Product (Code)', required=True)

    # --- CAMPOS RELACIONADOS (CORREGIDOS) ---
    product_name = fields.Char(
        related='product_id.product_name',  # CORREGIDO (antes 'product_id.name')
        string="Product Name", readonly=True)

    volume_product_reference_l = fields.Float(
        related='product_id.volume_liters',  # CORREGIDO (antes 'product_id.x_reference_volume')
        string="Reference Volume [L]", readonly=True)

    liquid_base_cost_related = fields.Float(
        related='product_id.liquid_cost',  # CORREGIDO (antes 'product_id.x_liquid_cost')
        string="Liquid Base Cost (from Master)", readonly=True)

    # --- CAMPOS DE ENTRADA (USUARIO) ---
    volume_sample_l = fields.Float(
        'Volume of Sample [L]', required=True, default=0.0,
        digits='Product Unit of Measure')

    bottle = fields.Float('Bottle', default=1.5)
    label = fields.Float('Label', default=1.5)
    labor = fields.Float('Labor', default=1.0)

    microfibers = fields.Float('Microfibers', default=0.0)
    plastic_bag = fields.Float('Plastic Bag', default=0.0)
    other_costs = fields.Float('Other Costs', default=0.0)

    # --- CAMPOS CALCULADOS (LÍNEA) ---
    liquid_cost = fields.Float(
        compute='_compute_line_costs', string='Liquid Cost',
        store=True, readonly=True,
        help="Liquid Cost * Volume of Sample [L]")

    line_total_cost = fields.Float(
        compute='_compute_line_costs', string='Line Total Cost',
        store=True, readonly=True)

    @api.depends(
        'volume_sample_l', 'liquid_base_cost_related', 'volume_product_reference_l',
        # <-- AÑADIMOS 'volume_product_reference_l'
        'bottle', 'label', 'labor',
        'microfibers', 'plastic_bag', 'other_costs'
    )
    def _compute_line_costs(self):
        for line in self:

            liquid_cost_per_liter = 0.0
            if line.volume_product_reference_l > 0:
                liquid_cost_per_liter = line.liquid_base_cost_related / line.volume_product_reference_l

            liquid_cost_calc = liquid_cost_per_liter * line.volume_sample_l

            line.liquid_cost = liquid_cost_calc

            line.line_total_cost = (
                    line.bottle +
                    line.label +
                    line.labor +
                    liquid_cost_calc +
                    line.microfibers +
                    line.plastic_bag +
                    line.other_costs
            )