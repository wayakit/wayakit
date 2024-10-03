from odoo import models, fields

class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    vehicle_type_id = fields.Many2one('service.type',string='Vehicle Type')
    service_type_id = fields.Many2one('vehicle.type',string='Vehicle Subtype')