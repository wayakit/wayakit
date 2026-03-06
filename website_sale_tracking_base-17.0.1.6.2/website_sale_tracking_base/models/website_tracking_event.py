# Copyright © 2024 Garazd Creation (https://garazd.biz)
# @author: Yurii Razumovskyi (support@garazd.biz)
# @author: Iryna Razumovska (support@garazd.biz)
# License OPL-1 (https://www.odoo.com/documentation/16.0/legal/licenses.html)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from .website import TRACKING_EVENT_TYPES


class WebsiteTrackingEvent(models.Model):
    _name = "website.tracking.event"
    _description = 'Website Tracking Events'

    name = fields.Char(required=True)
    type = fields.Selection(
        selection=TRACKING_EVENT_TYPES,
        required=True,
    )
    service_id = fields.Many2one(
        comodel_name='website.tracking.service',
        ondelete='cascade',
        required=True,
    )
    service_type = fields.Selection(related='service_id.type', string="Service Type")
    active = fields.Boolean(default=True)

    @api.constrains('type', 'service_id', 'active')
    def _check_unique(self):
        for event in self:
            if self.search_count([
                ('type', '=', event.type),
                ('service_id', '=', event.service_id.id),
                ('active', '=', True),
            ]) > 1:
                raise ValidationError(
                    _('The tracking event of a specific type must be unique per tracking service.')
                )
