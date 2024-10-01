from odoo import models, fields

class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    open_time = fields.Float(string="Open Time")
    close_time = fields.Float(string="Close Time")
