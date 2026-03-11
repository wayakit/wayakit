from odoo import models, fields
from odoo.exceptions import UserError

class PricingListWizard(models.TransientModel):
    _name = 'pricing.list.wizard'
    _description = 'Wizard to choose tier for pricing PDF'

    tier = fields.Selection([
        ('spark', '⚡ SPARK'),
        ('flow', '💧 FLOW'),
        ('cycle', '♻️ CYCLE'),
        ('stream', '🌊 STREAM'),
        ('source', '🌍 SOURCE'),
    ], string="Tier", required=True)

    def action_print_report(self):
        active_ids = self.env.context.get('active_ids', [])
        if not active_ids:
            raise UserError("No products were selected to print.")

        records = self.env['product.master'].browse(active_ids).exists()
        if not records:
            raise UserError("The selected products could not be found.")

        # Metemos los IDs explícitamente en la 'data' para no perderlos
        data = {
            'tier': self.tier,
            'active_ids': records.ids
        }

        return self.env.ref('price_intelligence.report_pricing_list_action').report_action(
            records.ids, data=data
        )