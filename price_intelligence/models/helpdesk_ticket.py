# -*- coding: utf-8 -*-
from odoo import fields, models, api, _


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    sampling_cost_calculator_ids = fields.One2many(
        'sampling.cost.calculator', 'helpdesk_ticket_id',
        string='Sampling Cost Calculators')

    sampling_cost_calculator_count = fields.Integer(
        compute='_compute_sampling_cost_count',
        string='Sampling Costs')

    def _compute_sampling_cost_count(self):
        """Cuenta el número de cálculos de muestreo para el botón inteligente."""
        for ticket in self:
            ticket.sampling_cost_calculator_count = len(ticket.sampling_cost_calculator_ids)

    def action_view_sampling_cost_calculators(self):
        """Acción del botón inteligente para ver los cálculos."""
        self.ensure_one()
        return {
            'name': _('Sampling Cost Calculators'),
            'type': 'ir.actions.act_window',
            'res_model': 'sampling.cost.calculator',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.sampling_cost_calculator_ids.ids)],
            'context': {
                'default_helpdesk_ticket_id': self.id,
            }
        }