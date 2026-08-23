# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class Base(models.AbstractModel):
    _inherit = 'base'

    def _wayakit_send_whatsapp(self, template, free_texts):
        """Send an approved whatsapp.template on this record. Never raises, and
        never poisons the transaction.

        On `base` because the caller's model is whatever the template applies to:
        today both review templates (38, 40) live on sale.order, but that has
        already changed once mid-development.

        `self` must be a single record of the TEMPLATE'S OWN model: the composer
        maps `template.phone_field` over it, so handing it a res.partner for a
        sale.order template dies with "'partner_id.mobile' does not seem to be a
        valid field path". Hence the explicit model guard.

        The savepoint is not optional. Catching the exception is not enough: the
        composer's failed `phone` compute stays pending in the transaction and
        blows up later at flush/commit, far from here -- which is how a WhatsApp
        outage would have taken the coupon's own transaction down with it.

        `free_texts` are positional over the template's Free Text variables in
        order, NOT over the {{n}} numbering: template 38's {{2}} is free_text_1.
        """
        self.ensure_one()
        if not template:
            return False
        if template.model != self._name:
            _logger.warning(
                "WhatsApp template %s applies to %s but was called on %s: skipped",
                template.template_name, template.model, self._name,
            )
            return False
        try:
            number = self._find_value_from_field_path(template.phone_field)
        except Exception:  # noqa: BLE001
            number = None
        if not number:
            _logger.info(
                "WhatsApp skipped for %s: no %s", self.display_name, template.phone_field)
            return False
        try:
            with self.env.cr.savepoint():
                composer = self.env['whatsapp.composer'].with_context(
                    active_model=self._name, active_ids=self.ids,
                ).create(dict(
                    {'free_text_%d' % (i + 1): v for i, v in enumerate(free_texts)},
                    wa_template_id=template.id,
                ))
                composer.action_send_whatsapp_template()
            return True
        except Exception:  # noqa: BLE001
            _logger.exception(
                "WhatsApp send failed (template %s, %s %s)",
                template.template_name, self._name, self.id,
            )
            return False
