# -*- coding: utf-8 -*-
from odoo import fields, models


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

        Also covers the manual "Send by Email" button on a confirmed order,
        which routes here through _find_mail_template().
        """
        self.ensure_one()
        b2b_medium = self.env.ref('wayakit_customization.utm_medium_b2b', raise_if_not_found=False)
        if b2b_medium and self.medium_id == b2b_medium:
            template = self.env.ref(
                'wayakit_customization.mail_template_sale_confirmation_b2b',
                raise_if_not_found=False,
            )
            if template:
                return template
        # ponytail: a missing/deleted record degrades to B2C, never blocks confirmation.
        return super()._get_confirmation_template()