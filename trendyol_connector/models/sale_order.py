import logging

from odoo import api, fields, models, _

from . import mapping

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    trendyol_backend_id = fields.Many2one("trendyol.backend", string="Trendyol Backend", readonly=True, copy=False)
    trendyol_package_id = fields.Char(string="Trendyol Package ID", readonly=True, copy=False, index=True)
    trendyol_order_number = fields.Char(string="Trendyol Order #", readonly=True, copy=False)
    trendyol_status = fields.Char(string="Trendyol Status", readonly=True, copy=False)
    trendyol_pushed_status = fields.Char(
        string="Status Pushed to Trendyol", readonly=True, copy=False,
        help="Last status we successfully notified to Trendyol. Makes the push idempotent "
             "and shows at a glance whether Trendyol knows the order is being prepared.",
    )

    _sql_constraints = [
        ("trendyol_package_uniq", "unique(trendyol_package_id)",
         "This Trendyol package is already imported."),
    ]

    # ------------------------------------------------------------- import API
    @api.model
    def _create_from_trendyol(self, backend, pkg):
        """Build a sale.order from one Trendyol shipment package — confirmed when the
        backend says so (Phase 2), otherwise a draft.
        Returns the order, or False if any line SKU can't be matched (order is
        skipped whole so we never create a half order — it retries next sync)."""
        lines, missing = self._trendyol_order_lines(pkg)
        if missing:
            _logger.warning(
                "Trendyol order %s skipped: unmatched SKU(s) %s",
                pkg.get("orderNumber"), missing)
            return False

        ship_partner = self._trendyol_shipping_partner(backend, pkg)
        vals = {
            "partner_id": backend.marketplace_partner_id.id,
            "partner_shipping_id": (ship_partner or backend.marketplace_partner_id).id,
            "company_id": backend.company_id.id,
            # explicit (even when empty) so the default never picks up env.user: the
            # button would stamp whoever clicked it and the webhook the public user.
            "user_id": backend.salesperson_id.id or False,
            "origin": "Trendyol %s" % (pkg.get("orderNumber") or ""),
            "client_order_ref": pkg.get("orderNumber"),
            "date_order": mapping.epoch_ms_to_dt(pkg.get("orderDate")) or fields.Datetime.now(),
            "trendyol_backend_id": backend.id,
            "trendyol_package_id": mapping.package_id(pkg),
            "trendyol_order_number": pkg.get("orderNumber"),
            "trendyol_status": pkg.get("status"),
            "order_line": [(0, 0, l) for l in lines],
        }
        # Ship FBM orders from the backend's location. Only set when it resolves to a
        # warehouse — warehouse_id is required, so leave Odoo's compute to it otherwise.
        warehouse = backend.warehouse_location_id.warehouse_id
        if warehouse:
            vals["warehouse_id"] = warehouse.id
        order = self.create(vals)

        # A Trendyol package is already paid: there is nothing to quote. Same call the
        # reconciliation cron uses, so import and catch-up can never drift apart.
        order._trendyol_apply_status(pkg.get("status"))
        return order

    # ------------------------------------------------------- status (Phase 2)
    def _trendyol_confirm(self):
        """Confirm the order, but never lose it if confirmation fails: a missing route, a
        stock rule or an access error must leave a draft order behind (and a chatter note),
        not roll back the import of a paid marketplace order."""
        self.ensure_one()
        if self.state not in ("draft", "sent"):
            return self.state == "sale"
        try:
            self.action_confirm()
        except Exception as e:
            _logger.exception("Trendyol order %s: auto-confirm failed", self.trendyol_order_number)
            self.message_post(body=_("Trendyol: auto-confirm failed, order left as a "
                                     "quotation. %s") % e)
            return False
        return True

    def _trendyol_push_status(self, status, params=None):
        """Notify Trendyol of a package status. Idempotent (skips what was already pushed)
        and never raises: a marketplace hiccup must not roll back the Odoo transaction that
        triggered it (order confirmation, delivery validation). Failures land in the chatter
        so they are visible on the order, not only in the odoo.sh log."""
        self.ensure_one()
        backend = self.trendyol_backend_id
        if not (backend and backend.push_status and self.trendyol_package_id):
            return False
        if self.trendyol_pushed_status == status:
            return True
        try:
            # inside the try: a non-numeric lineId must degrade like any other push
            # failure, not blow up the delivery validation that called us.
            lines = [{"lineId": int(l.trendyol_line_id), "quantity": int(l.product_uom_qty)}
                     for l in self.order_line if l.trendyol_line_id]
            backend._update_package_status(self.trendyol_package_id, status, lines, params)
        except Exception as e:
            _logger.warning("Trendyol order %s: pushing status %s failed: %s",
                            self.trendyol_order_number, status, e)
            self.message_post(body=_("Trendyol: could not push status %(s)s. %(e)s")
                              % {"s": status, "e": e})
            return False
        self.trendyol_pushed_status = status
        self.message_post(body=_("Trendyol: status %s notified.") % status)
        return True

    def _trendyol_apply_status(self, status):
        """Inbound status, from the webhook or from the reconciliation cron.

        This is the catch-up path: it re-runs the confirm+push that the import already
        tried, which is what recovers an order whose webhook was missed or whose
        auto-confirm failed. Both steps are idempotent, so re-running them is free.
        Phase 2 only moves forward — Cancelled/Returned just refresh the char (Phase 3)."""
        self.ensure_one()
        self.trendyol_status = status or self.trendyol_status
        if not (mapping.should_import(status) and self.trendyol_backend_id.auto_confirm):
            return
        if self._trendyol_confirm() and mapping.map_state(status) == "draft":
            # Only while Trendyol still says Created/Picking: pushing Picking onto an
            # already-Shipped package is rejected.
            self._trendyol_push_status("Picking")
        if mapping.should_lock(status) and self.state == "sale":
            self.locked = True

    @api.model
    def _trendyol_order_lines(self, pkg):
        # active_test=False: import orders for archived products too (never drop a
        # paid order); order="active desc" prefers an active match over an archived
        # duplicate, and a WARNING flags archived ones for cleanup.
        Product = self.env["product.product"].with_context(active_test=False)
        lines, missing = [], []
        for raw in mapping.normalize_lines(pkg):
            product = (Product.search([("default_code", "=", raw["sku"])],
                                      order="active desc", limit=1)
                       if raw["sku"] else Product.browse())
            if not product:
                missing.append(raw["sku"] or "(empty SKU)")
                continue
            if not product.active:
                _logger.warning("Trendyol order %s: product %s is archived in Odoo",
                                pkg.get("orderNumber"), raw["sku"])
            lines.append({
                "product_id": product.id,
                "product_uom_qty": raw["quantity"],
                "price_unit": raw["price"],
                "name": raw["name"] or product.display_name,
                "trendyol_line_id": raw["line_id"],
            })
        return lines, missing

    @api.model
    def _trendyol_shipping_partner(self, backend, pkg):
        """One delivery-type child per order holding the real ship-to address.
        ponytail: a child per order, not a customer per buyer — keeps the CRM clean and
        gives Phase 2 a real address to print labels from. Dedup handled upstream by package_id."""
        addr = pkg.get("shipmentAddress") or {}
        if not addr:
            return False
        name = addr.get("fullName") \
            or " ".join(filter(None, [addr.get("firstName"), addr.get("lastName")])) \
            or pkg.get("orderNumber") or "Trendyol buyer"
        country = self.env["res.country"].search(
            [("code", "=", (addr.get("countryCode") or "").upper())], limit=1)
        return self.env["res.partner"].create({
            "name": name,
            "type": "delivery",
            "parent_id": backend.marketplace_partner_id.id,
            "street": addr.get("address1") or addr.get("fullAddress"),
            "street2": addr.get("address2"),
            "city": addr.get("city"),
            "zip": addr.get("postalCode"),
            "phone": addr.get("phone"),
            "country_id": country.id or False,
        })


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    trendyol_line_id = fields.Char(
        string="Trendyol Line ID", readonly=True, copy=False,
        help="Trendyol's own order-line id. Needed to push a per-line package status "
             "(PUT shipment-packages expects lines[].lineId).",
    )
