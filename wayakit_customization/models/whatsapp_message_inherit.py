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
        """Scan inbound WhatsApp messages for a Saudi National Address short code,
        store it on the related customer, and confirm back over WhatsApp.

        A reply always reflects the customer's latest intent, so a new valid code
        overwrites whatever was stored before (this is how the customer corrects a
        wrong code). On every valid code we send an automatic WhatsApp confirmation
        stating the stored value and how to correct it."""
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

            # Overwrite on every reply: the latest code the customer sends wins
            # (this is how the customer corrects a wrong code).
            if partner.x_national_short_code != short_code:
                partner.sudo().write({'x_national_short_code': short_code})
                partner.message_post(
                    body=Markup("✅ National Address short code captured via WhatsApp: <b>%s</b>") % short_code,
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )

            # Confirm back to the customer over WhatsApp (within the 24h window).
            msg._wayakit_send_short_code_confirmation(short_code)

    def _wayakit_send_short_code_confirmation(self, short_code):
        """Send an automatic WhatsApp reply confirming the stored short code.

        Best-effort: a send failure must never break capture. Only valid inside
        WhatsApp's 24h customer-service window, which always holds here because the
        customer just messaged us. Posting to the channel with message_type
        ``whatsapp_message`` creates an outbound message and triggers the send
        (see ``discuss.channel.message_post``). The outbound reply is never
        re-captured because capture only processes inbound messages."""
        self.ensure_one()
        mail_msg = self.mail_message_id
        if not (mail_msg and mail_msg.model == 'discuss.channel' and mail_msg.res_id):
            return
        channel = self.env['discuss.channel'].browse(mail_msg.res_id).exists()
        if not channel or channel.channel_type != 'whatsapp':
            return
        body = Markup(
            "✅ We saved your National Address short code: <b>%s</b>.<br/><br/>"
            "If this is correct, no need to reply. If it is wrong, just send the "
            "correct code again (4 letters + 4 numbers, e.g. RRRD2929)."
        ) % short_code
        try:
            channel.sudo().message_post(body=body, message_type='whatsapp_message')
        except Exception:  # noqa: BLE001
            _logger.exception(
                "Failed to send WhatsApp short code confirmation (message %s)", self.id,
            )

    def _wayakit_resolve_partner(self):
        """Resolve the customer this inbound message belongs to.

        Resolution order, most reliable first:
          1. The customer of the order the conversation was started from. The
             real WhatsApp flow does NOT anchor the channel to the source
             document, but the *outbound* message that "Send WhatsApp" creates
             from a sale order keeps ``mail_message_id.model == 'sale.order'``.
             Inbound replies share the same ``mobile_number_formatted``, so we
             walk the most recent outbound messages for that number and take
             the customer of the originating document. This is the stable
             account reused across orders, so the customer is not asked again.
          2. The originating document via the channel (kept for flows where the
             channel *is* anchored to the source record).
          3. The WhatsApp contact tied to the channel (``author_id``).
          4. A phone-number lookup as a last resort.
        """
        self.ensure_one()
        mail_msg = self.mail_message_id

        # 1) Anchor on the most recent outbound WhatsApp for this number that
        #    was sent from a document carrying a customer (e.g. a sale order).
        if self.mobile_number_formatted:
            outbound = self.search([
                ('message_type', '=', 'outbound'),
                ('mobile_number_formatted', '=', self.mobile_number_formatted),
            ], order='id desc')
            for out in outbound:
                src_msg = out.mail_message_id
                if (src_msg and src_msg.model and src_msg.res_id
                        and src_msg.model != 'discuss.channel'):
                    source = self.env[src_msg.model].browse(src_msg.res_id).exists()
                    if source and 'partner_id' in source._fields and source.partner_id:
                        _logger.info(
                            "WhatsApp short code: resolved partner from outbound %s -> %s(%s) for message %s",
                            out.id, src_msg.model, src_msg.res_id, self.id,
                        )
                        return source.partner_id

        # 2) Anchor on the originating document via the channel.
        if mail_msg and mail_msg.model == 'discuss.channel' and mail_msg.res_id:
            channel = self.env['discuss.channel'].browse(mail_msg.res_id).exists()
            source_msg = channel.whatsapp_mail_message_id if channel else False
            if source_msg and source_msg.model and source_msg.res_id:
                source = self.env[source_msg.model].browse(source_msg.res_id).exists()
                if source and 'partner_id' in source._fields and source.partner_id:
                    return source.partner_id

        # 3) The WhatsApp contact for this conversation.
        if mail_msg and mail_msg.author_id:
            _logger.info(
                "WhatsApp short code: using channel contact (no source document) for message %s",
                self.id,
            )
            return mail_msg.author_id

        # 4) Phone-number fallback.
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
