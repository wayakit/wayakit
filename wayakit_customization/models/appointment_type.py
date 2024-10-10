from odoo import models, fields

class AppointmentType(models.Model):
    _inherit = 'appointment.type'

    api_service = fields.Boolean(string="Api Service")
    api_description = fields.Text(string="Description")
    service_type = fields.Many2many('service.type' , string="Service Types")
