from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    related_fields_ids = fields.Many2many('ir.model.fields', string='Related Fields',
                                          domain=lambda self: [('model', '=', self._name)])

    working_schedule_id = fields.Many2one('resource.calendar', string='Working Schedule',domain="[('company_id', '=', id)]" )
    working_schedule_specialdays_id = fields.Many2one('resource.calendar', string='Working Schedule special days')
    is_service_provider = fields.Boolean(string="Is Service Provider", default=False)

