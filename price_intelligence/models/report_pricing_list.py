from odoo import models, api, fields

class ReportPricingList(models.AbstractModel):
    _name = 'report.price_intelligence.pricing_list_template'
    _description = 'Pricing List Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        if not docids and data and data.get('active_ids'):
            docids = data.get('active_ids')

        docs = self.env['product.master'].browse(docids)
        selected_tier = (data or {}).get('tier')

        return {
            'doc_ids': docids,
            'doc_model': 'product.master',
            'docs': docs,
            'data': data or {},
            'selected_tier': selected_tier,
            # Agregamos la fecha exacta en la que se genera el reporte
            'print_date': fields.Date.context_today(self),
        }