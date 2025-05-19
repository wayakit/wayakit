from odoo import models, fields

class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="End Date", required=True)
    open_time = fields.Float(string="Open Time", required=True)
    close_time = fields.Float(string="Close Time", required=True)
