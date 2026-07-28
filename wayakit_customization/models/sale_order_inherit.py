# -*- coding: utf-8 -*-
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_national_short_code = fields.Char(
        related='partner_id.x_national_short_code',
        string="National Address Short Code",
        readonly=False,
        store=False,
        help="Saudi National Address short code of the customer (captured via WhatsApp). "
             "Editing it here writes back to the customer record and is reused across orders.",
    )

    def _get_confirmation_template(self):
        """Send the B2B confirmation template when the channel is B2B.

        "Channel" on the SO form is the Studio field x_studio_channel ('B2B'/'B2C'),
        NOT the UTM medium_id: 1047 orders carry x_studio_channel, only 6 carry
        medium_id. Studio fields live in the DB and never reach git, hence the
        _fields guard.

        Also covers the manual "Send by Email" button on a confirmed order,
        which routes here through _find_mail_template().
        """
        self.ensure_one()
        template = self.env.ref(
            'wayakit_customization.mail_template_sale_confirmation_b2b',
            raise_if_not_found=False,
        )
        if not template or 'x_studio_channel' not in self._fields:
            # Data file never loaded, or the Studio field was renamed/dropped.
            # Without this log the B2C fallback below is silent.
            _logger.warning(
                "B2B confirmation template disabled on %s: template=%s, has x_studio_channel=%s",
                self.name, template, 'x_studio_channel' in self._fields,
            )
        elif self.x_studio_channel == 'B2B':
            return template
        else:
            _logger.info(
                "%s: channel %r is not B2B, using default confirmation template",
                self.name, self.x_studio_channel,
            )
        # ponytail: a missing/deleted record degrades to B2C, never blocks confirmation.
        return super()._get_confirmation_template()