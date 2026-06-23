# -*- coding: utf-8 -*-
import logging
import re

from markupsafe import Markup

from odoo import api, models
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

# Saudi National Address short code: 4 letters followed by 4 digits (e.g. RRRD2929).
_SHORT_CODE_RE = re.compile(r'\b([A-Za-z]{4}\d{4})\b')


class WhatsappMessage(models.Model):
    _inherit = 'whatsapp.message'

    @api.model_create_multi
    def create(self, vals_list):
        messages = super().create(vals_list)
        # Capture is best-effort: a parsing problem must never block message creation.
        try:
            messages._wayakit_capture_national_short_code()
        except Exception:  # noqa: BLE001
            _logger.exception("Failed to capture National Address short code from WhatsApp message")
        return messages

    def _wayakit_capture_national_short_code(self):
        """Scan inbound WhatsApp messages for a Saudi National Address short code
        and store it on the related customer if not already set."""
        for msg in self:
            if msg.message_type != 'inbound':
                continue

            plain = html2plaintext(msg.body or '').strip()
            if not plain:
                continue

            match = _SHORT_CODE_RE.search(plain)
            if not match:
                continue

            short_code = match.group(1).upper()

            partner = msg._wayakit_resolve_partner()
            if not partner:
                _logger.info(
                    "WhatsApp short code %s found but no partner could be resolved (message %s)",
                    short_code, msg.id,
                )
                continue

            # Write only if the partner doesn't already have a code. If they
            # already have one, the reply is a duplicate and we leave it as-is.
            if not partner.x_national_short_code:
                partner.sudo().write({'x_national_short_code': short_code})
                partner.message_post(
                    body=Markup("✅ National Address short code captured via WhatsApp: <b>%s</b>") % short_code,
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )

    def _wayakit_resolve_partner(self):
        """Resolve the customer this inbound message belongs to.

        Resolution order, most reliable first:
          1. The customer of the originating document (the sale order the
             WhatsApp conversation was started from). This is the stable
             account that is reused across orders, so the captured code is
             available next time and the customer is not asked again.
          2. The WhatsApp contact tied to the channel (``author_id``).
          3. A phone-number lookup as a last resort.
        """
        self.ensure_one()
        mail_msg = self.mail_message_id

        # 1) Anchor on the originating document via the channel.
        if mail_msg and mail_msg.model == 'discuss.channel' and mail_msg.res_id:
            channel = self.env['discuss.channel'].browse(mail_msg.res_id).exists()
            source_msg = channel.whatsapp_mail_message_id if channel else False
            if source_msg and source_msg.model and source_msg.res_id:
                source = self.env[source_msg.model].browse(source_msg.res_id).exists()
                if source and 'partner_id' in source._fields and source.partner_id:
                    return source.partner_id

        # 2) The WhatsApp contact for this conversation.
        if mail_msg and mail_msg.author_id:
            _logger.info(
                "WhatsApp short code: using channel contact (no source document) for message %s",
                self.id,
            )
            return mail_msg.author_id

        # 3) Phone-number fallback.
        if self.mobile_number_formatted:
            partner = self.env['res.partner'].search([
                '|',
                ('phone', 'like', self.mobile_number_formatted),
                ('mobile', 'like', self.mobile_number_formatted),
            ], limit=1)
            if partner:
                _logger.info(
                    "WhatsApp short code: resolved partner by phone fallback for message %s",
                    self.id,
                )
            return partner

        return self.env['res.partner']