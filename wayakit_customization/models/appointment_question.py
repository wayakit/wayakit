# -*- coding: utf-8 -*-

from odoo import api, fields, models

class AppointmentQuestion(models.Model):
    _inherit = "appointment.question"

    api_question = fields.Boolean('Api Question')

