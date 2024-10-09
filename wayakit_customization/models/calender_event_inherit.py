from odoo import models, fields

class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    vehicle_type_id = fields.Many2one('service.type',string='Service Type')
    service_type_id = fields.Many2one('vehicle.type',string='Service Subtype')
    extra_ids = fields.Many2many('product.product',string='Extra ids')
    total_cost_vat_inclusive = fields.Float(string='Total Cost')