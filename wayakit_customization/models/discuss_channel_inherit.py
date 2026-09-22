# -*- coding: utf-8 -*-
"""Put the customer phone number back in front of the WhatsApp channel name.

See models/whatsapp_channel_name.py for the why and CLAUDE-customizations.md
section 6 for the full write-up.
"""
import logging

from odoo import api, models
from odoo.addons.whatsapp.tools import phone_validation as wa_phone_validation

from .whatsapp_channel_name import channel_name

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _wayakit_wa_display_number(self, raw):
        """'+966583851020' out of whatever comes in.

        Reuses the whatsapp module's own helper instead of reimplementing phone
        formatting. Never raises: CLAUDE.md (2026-08-24) already burned us with
        a phone validator blowing up inside a business flow.
        """
        raw = (raw or "").strip()
        if not raw:
            return ""

        def fmt(number):
            return wa_phone_validation.wa_phone_format(
                self.env.company,
                number=number,
                force_format="E164",
                raise_exception=False,
            )

        # Prefixing '+' is what core itself does (_get_whatsapp_channel_format_number).
        # The second attempt covers partner mobile/phone typed in local form (05x...).
        base = raw if raw.startswith("+") else "+" + raw
        return fmt(base) or fmt(raw) or base

    def _get_whatsapp_channel_create_values(self, *args, **kwargs):
        """Prepend the number to the name Odoo picked.

        Extension point introduced by enterprise commit 8fe680ab. Confirmed
        signature in production: (identifiers, wa_account_id=None,
        sender_name=False) -- kept as *args/**kwargs because that signature has
        already changed once.

        We read 'whatsapp_number' off the values super() built rather than the
        'identifiers' dict, so this survives the next refactor. It also gives us
        the required behaviour for free: no number (BSUID-only identifiers) means
        the key is absent and the native name goes through untouched.

        The caller appends " (record_name)" after this returns, so the (S02125)
        suffix keeps working.
        """
        vals = super()._get_whatsapp_channel_create_values(*args, **kwargs)
        number = self._wayakit_wa_display_number(vals.get("whatsapp_number"))
        if number:
            vals["name"] = channel_name(number, vals.get("name"))
        return vals

    @api.model
    def _wayakit_backfill_whatsapp_names(self):
        """Rename the channels created between July 2026 and this module.

        Called by data/whatsapp_channel_name_data.xml on every module upgrade.
        Idempotent, so running it N times equals running it once.

        @api.model is mandatory, not decoration: <function> goes through
        api.call_kw, which routes anything without _api == 'model' to
        _call_kw_multi, and that one reads args[0] as the id list. With no ids to
        pass it blows up with "IndexError: list index out of range" and takes the
        whole build down.
        """
        channels = self.sudo().search([("channel_type", "=", "whatsapp")])
        renamed = 0
        for channel in channels:
            partner = channel.whatsapp_partner_id
            raw = channel.whatsapp_number or partner.mobile or partner.phone
            # No number anywhere -> display number is '' -> channel_name gives the
            # label back unchanged -> the channel skips itself.
            new_name = channel_name(self._wayakit_wa_display_number(raw), channel.name)
            if new_name and new_name != channel.name:
                channel.name = new_name
                renamed += 1
        _logger.info(
            "WhatsApp channel names: %s renamed out of %s channels", renamed, len(channels))
        return renamed
