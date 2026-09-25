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
    fin_pi_master_ref = fields.Integer(compute='_compute_financials', groups=FIN_GROUP)
    # PI cost captured when the order is confirmed, so a later change in PI
    # never alters the margin of a sale already made. 0 = nothing captured
    # (no PI cost at the time, or an SO confirmed before this field existed).
    fin_frozen_unit_cost = fields.Monetary(
        string="Frozen Unit Cost", copy=False, groups=FIN_GROUP)

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

    def _financials_pi_masters(self):
        """{line: product.master record} for the counted lines whose SKU
        (default_code) exists in Price Intelligence."""
        lines = self.filtered(lambda l: l._financials_counted() and l.product_id.default_code)
        codes = list(set(lines.mapped('product_id.default_code')))
        if not codes:
            return {}
        # sudo: salespeople have no ACL on product.master; exposure is
        # controlled by FIN_GROUP on the fields that carry the result.
        masters = self.env['product.master'].sudo().search(
            [('product_id', 'in', codes)], order='id desc')
        master_by_code = {}
        # A few SKUs have several master records: stable sort keeps the
        # newest one first, active records ahead of inactive ones.
        for master in masters.sorted(lambda m: m.status != 'active'):
            master_by_code.setdefault(master.product_id, master)
        return {
            line: master_by_code[line.product_id.default_code]
            for line in lines if line.product_id.default_code in master_by_code
        }

    def _financials_unit_costs(self, masters):
        """{line: unit cost in the order currency per product UoM}, lines
        without a known cost are left out.

        Swap point: the cost source is Price Intelligence today
        (product.master.unit_cost_sar, joined on SKU = default_code). When
        PLM/FIFO costs are trusted, only this method changes.
        """
        sar = self.env.ref('base.SAR')
        costs = {}
        for line, master in masters.items():
            cost = master.unit_cost_sar
            if not cost:
                continue
            currency = line.order_id.currency_id
            if currency and currency != sar:
                cost = sar._convert(
                    cost, currency, line.order_id.company_id,
                    line.order_id.date_order or fields.Date.today())
            costs[line] = cost
        return costs

    def _financials_freeze_cost(self):
        """Capture today's PI cost on the lines of confirmed orders."""
        costs = self._financials_unit_costs(self._financials_pi_masters())
        for line in self:
            # sudo: the confirming salesperson usually lacks FIN_GROUP, and
            # writing a group-gated field would raise AccessError.
            line.sudo().fin_frozen_unit_cost = costs.get(line, 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        # Upsell on an already confirmed order: freeze now, or the new line
        # would keep following PI.
        lines.filtered(lambda l: l.order_id.state == 'sale')._financials_freeze_cost()
        return lines

    def action_open_pi_master(self):
        """Open this line's Master Product in Price Intelligence."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.master',
            'res_id': self.fin_pi_master_ref,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.depends('product_id', 'product_uom_qty', 'product_uom', 'price_subtotal',
                 'display_type', 'order_id.currency_id', 'order_id.state',
                 'fin_frozen_unit_cost')
    def _compute_financials(self):
        masters = self._financials_pi_masters()
        costs = self._financials_unit_costs(masters)
        for line in self:
            # A plain id, not a Many2one: rendering a Many2one would make the
            # client read product.master, which users without PI access can't.
            line.fin_pi_master_ref = masters[line].id if line in masters else 0
            if line.order_id.state == 'sale':
                # Confirmed: only the frozen cost counts, never live PI. No
                # fallback on purpose, old SOs stay without cost (ticket call).
                cost = line.sudo().fin_frozen_unit_cost or None
            else:
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
        string="Margin % (PI)", digits=(16, 2), compute='_compute_financials', groups=FIN_GROUP)
    fin_missing_count = fields.Integer(
        string="Lines without PI Cost", compute='_compute_financials', groups=FIN_GROUP)
    fin_missing_amount = fields.Monetary(
        string="Sales without PI Cost", compute='_compute_financials', groups=FIN_GROUP)

    def _action_confirm(self):
        res = super()._action_confirm()
        # Re-confirming (cancel > draft > confirm) refreshes the frozen cost.
        self.order_line._financials_freeze_cost()
        return res

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
