import logging

from odoo import models, _

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _action_done(self):
        res = super()._action_done()
        for picking in self.filtered(lambda p: p.picking_type_code == "outgoing"):
            picking._trendyol_push_tracking()
        return res

    def _trendyol_push_tracking(self):
        """Send our waybill number to Trendyol once the delivery is validated.

        FBM: Wayakit ships with its own courier, so Trendyol only learns the tracking
        number from us — and that is what flips the package to Shipped on their side
        (the seller cannot set Shipped directly).

        No-ops with an INFO log when anything is missing (no tracking reference typed, or
        no providerCode mapped on the carrier yet) — validating a delivery must never fail
        because of Trendyol."""
        self.ensure_one()
        order = self.sale_id
        backend = order.trendyol_backend_id
        if not (backend and order.trendyol_package_id):
            return False
        provider_code = self.carrier_id.trendyol_provider_code
        if not (self.carrier_tracking_ref and provider_code):
            _logger.info(
                "Trendyol %s: tracking not pushed (tracking ref %r, carrier %r, provider "
                "code %r)", order.trendyol_order_number, self.carrier_tracking_ref,
                self.carrier_id.name, provider_code)
            return False
        # Trendyol rejects tracking-details unless the package is already in Picking.
        order._trendyol_push_status("Picking")
        try:
            backend._update_tracking(
                order.trendyol_package_id, self.carrier_tracking_ref, provider_code)
        except Exception as e:
            _logger.warning("Trendyol order %s: pushing tracking %s failed: %s",
                            order.trendyol_order_number, self.carrier_tracking_ref, e)
            order.message_post(body=_("Trendyol: could not push tracking %(t)s (%(p)s). %(e)s")
                               % {"t": self.carrier_tracking_ref, "p": provider_code, "e": e})
            return False
        order.message_post(body=_("Trendyol: tracking %(t)s sent (%(p)s).")
                           % {"t": self.carrier_tracking_ref, "p": provider_code})
        return True
