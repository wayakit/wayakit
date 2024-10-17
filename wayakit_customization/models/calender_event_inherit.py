from odoo import models, fields

class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    vehicle_type_id = fields.Many2one('service.type',string='Service Type', readonly=True)
    service_type_id = fields.Many2one('vehicle.type',string='Service Subtype', readonly=True)
    extra_ids = fields.Many2many('product.product',string='Extra ids', readonly=True)
    total_cost_vat_inclusive = fields.Float(string='Total Cost', readonly=True)
    sale_order_id = fields.Many2one('sale.order', string='Sale order', readonly=True)
    vehicle_use_id = fields.Integer("Vehicle use Id", readonly=True)
    booking_date = fields.Date("Date", readonly=True)
    customer_feedback = fields.Text("Comments", readonly=True)
    customer_rating = fields.Float('Rating')