# -*- coding: utf-8 -*-
from odoo import api, fields, models

# Costs and margins are confidential: every financials field is gated here,
# which also hides them from RPC reads and exports, not just from the view.
FIN_GROUP = 'wayakit_customization.group_quotation_financials'


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    fin_unit_cost = fields.Monetary(
        string="Unit Cost (PI)", compute='_compute_financials', groups=FIN_GROUP)
    fin_total_cost = fields.Monetary(
        string="Total Cost", compute='_compute_financials', groups=FIN_GROUP)
    fin_profit = fields.Monetary(
        string="Profit", compute='_compute_financials', groups=FIN_GROUP)
    fin_cost_missing = fields.Boolean(
        string="No PI Cost", compute='_compute_financials', groups=FIN_GROUP)

    def _financials_counted(self):
        """Product lines only: sections/notes, down payments and shipping
        have no Price Intelligence cost and must not read as "missing"."""
        self.ensure_one()
        return bool(
            self.product_id
            and not self.display_type
            and not self.is_downpayment
            # is_delivery comes from the delivery module, not a dependency here.
            and not getattr(self, 'is_delivery', False)
        )

    def _financials_unit_costs(self):
        """{line: unit cost in the order currency per product UoM}, lines
        without a known cost are left out.

        Swap point: the cost source is Price Intelligence today
        (product.master.unit_cost_sar, joined on SKU = default_code). When
        PLM/FIFO costs are trusted, only this method changes.
        """
        lines = self.filtered(lambda l: l._financials_counted() and l.product_id.default_code)
        codes = list(set(lines.mapped('product_id.default_code')))
        if not codes:
            return {}
        # sudo: salespeople have no ACL on product.master; exposure is
        # controlled by FIN_GROUP on the fields that carry the result.
        masters = self.env['product.master'].sudo().search(
            [('product_id', 'in', codes)], order='id desc')
        cost_by_code = {}
        # A few SKUs have several master records: stable sort keeps the
        # newest one first, active records ahead of inactive ones.
        for master in masters.sorted(lambda m: m.status != 'active'):
            cost_by_code.setdefault(master.product_id, master.unit_cost_sar)

        sar = self.env.ref('base.SAR')
        costs = {}
        for line in lines:
            cost = cost_by_code.get(line.product_id.default_code)
            if not cost:
                continue
            currency = line.order_id.currency_id
            if currency and currency != sar:
                cost = sar._convert(
                    cost, currency, line.order_id.company_id,
                    line.order_id.date_order or fields.Date.today())
            costs[line] = cost
        return costs

    @api.depends('product_id', 'product_uom_qty', 'product_uom', 'price_subtotal',
                 'display_type', 'order_id.currency_id')
    def _compute_financials(self):
        costs = self._financials_unit_costs()
        for line in self:
            cost = costs.get(line)
            line.fin_cost_missing = cost is None and line._financials_counted()
            if cost is None:
                line.fin_unit_cost = line.fin_total_cost = line.fin_profit = 0.0
                continue
            qty = line.product_uom._compute_quantity(line.product_uom_qty, line.product_id.uom_id)
            line.fin_unit_cost = cost
            line.fin_total_cost = cost * qty
            # price_subtotal is already net of discount and excludes VAT.
            line.fin_profit = line.price_subtotal - line.fin_total_cost


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_b2b = fields.Boolean(compute='_compute_is_b2b')

    fin_line_ids = fields.Many2many(
        'sale.order.line', string="Financials Lines",
        compute='_compute_financials', groups=FIN_GROUP)
    fin_amount_untaxed = fields.Monetary(
        string="Sales (excl. VAT)", compute='_compute_financials', groups=FIN_GROUP)
    fin_covered_amount = fields.Monetary(
        string="Sales with PI Cost", compute='_compute_financials', groups=FIN_GROUP)
    fin_total_cost = fields.Monetary(
        string="Total Cost", compute='_compute_financials', groups=FIN_GROUP)
    fin_total_profit = fields.Monetary(
        string="Total Profit", compute='_compute_financials', groups=FIN_GROUP)
    fin_margin_pct = fields.Float(
        string="Margin (%)", digits=(16, 2), compute='_compute_financials', groups=FIN_GROUP)
    fin_missing_count = fields.Integer(
        string="Lines without PI Cost", compute='_compute_financials', groups=FIN_GROUP)
    fin_missing_amount = fields.Monetary(
        string="Sales without PI Cost", compute='_compute_financials', groups=FIN_GROUP)

    @api.depends(lambda self: ['x_studio_channel'] if 'x_studio_channel' in self._fields else [])
    def _compute_is_b2b(self):
        # x_studio_channel is a Studio field (DB only, never in git), hence
        # the guard: see _get_confirmation_template in sale_order_inherit.py.
        has_channel = 'x_studio_channel' in self._fields
        for order in self:
            order.is_b2b = has_channel and order.x_studio_channel == 'B2B'

    @api.depends('amount_untaxed', 'order_line.price_subtotal', 'order_line.fin_total_cost',
                 'order_line.fin_cost_missing', 'order_line.display_type')
    def _compute_financials(self):
        for order in self:
            counted = order.order_line.filtered(lambda l: l._financials_counted())
            missing = counted.filtered('fin_cost_missing')
            # Lines without a PI cost are excluded from profit and margin so
            # they cannot inflate it; the warning in the tab shows what's out.
            covered = counted - missing
            covered_amount = sum(covered.mapped('price_subtotal'))
            total_cost = sum(covered.mapped('fin_total_cost'))
            profit = covered_amount - total_cost
            order.fin_line_ids = counted
            order.fin_amount_untaxed = order.amount_untaxed
            order.fin_covered_amount = covered_amount
            order.fin_total_cost = total_cost
            order.fin_total_profit = profit
            order.fin_margin_pct = profit / covered_amount * 100 if covered_amount else 0.0
            order.fin_missing_count = len(missing)
            order.fin_missing_amount = sum(missing.mapped('price_subtotal'))
