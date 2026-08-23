import logging
import re

from odoo import models, fields,api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    customer_kaust_id = fields.Char(string="Customer KAUST ID")

    x_national_short_code = fields.Char(
        string="National Address Short Code",
        size=8,
        help="Saudi National Address short code (8 chars: 4 letters + 4 digits, e.g. RRRD2929). "
             "Found in the Absher or Saudi Post | SPL app.",
    )

    @api.constrains('customer_kaust_id')
    def _check_customer_kaust_id(self):
        for record in self:
            if record.customer_kaust_id and self.search_count(
                    [('customer_kaust_id', '=', record.customer_kaust_id)]) > 1:
                raise ValidationError('The KAUST ID must be unique.')

    @api.constrains('x_national_short_code')
    def _check_national_short_code(self):
        for record in self:
            code = record.x_national_short_code
            if code and not re.match(r'^[A-Za-z]{4}\d{4}$', code):
                raise ValidationError(
                    'The National Address Short Code must be exactly 4 letters '
                    'followed by 4 digits (e.g. RRRD2929).'
                )

    @api.onchange('x_national_short_code')
    def _onchange_national_short_code(self):
        if self.x_national_short_code:
            self.x_national_short_code = self.x_national_short_code.upper()

    def _wayakit_send_whatsapp(self, template, free_texts):
        """Send an approved whatsapp.template to this contact. NEVER raises.

        Single send point for the post-purchase review flow: both templates
        (feedback_ecommerce_2 id 38 and customer_coupon_code_2 id 40) apply to
        res.partner and read phone_field = mobile, so the guard is `mobile` alone.

        A WhatsApp failure must not roll back the transaction that triggered it:
        when loyalty_card calls this, the coupon and its email already exist.

        `free_texts` are positional over the template's Free Text variables in
        order, NOT over the {{n}} numbering -- template 38's {{2}} is free_text_1.
        """
        self.ensure_one()
        if not template or not self.mobile:
            _logger.info(
                "WhatsApp skipped for %s: template=%s, has mobile=%s",
                self.display_name, template, bool(self.mobile),
            )
            return False
        try:
            composer = self.env['whatsapp.composer'].with_context(
                active_model='res.partner', active_ids=self.ids,
            ).create(dict(
                {'free_text_%d' % (i + 1): v for i, v in enumerate(free_texts)},
                wa_template_id=template.id,
            ))
            composer.action_send_whatsapp_template()
            return True
        except Exception:  # noqa: BLE001
            _logger.exception(
                "WhatsApp send failed (template %s, partner %s)",
                template.template_name, self.id,
            )
            return False
