from odoo import models, fields

class AppointmentType(models.Model):
    _inherit = 'appointment.type'

    service_type = fields.Many2many('service.type' ,string="Service Type")
