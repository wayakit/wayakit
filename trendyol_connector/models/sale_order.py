import logging

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.tools import html_escape

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
    trendyol_alerted_status = fields.Char(
        string="Status Alerted in Chatter", readonly=True, copy=False,
        help="Last Cancelled/Returned-type status we posted a chatter notice about. "
             "Keeps the notice idempotent when Trendyol redelivers a webhook or sends "
             "them out of order.",
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

        # The buyer is both the customer and the ship-to: one flat contact, no delivery
        # child. Falls back to the generic marketplace partner only when Trendyol sent
        # no name at all.
        partner = self._trendyol_buyer_partner(backend, pkg) or backend.marketplace_partner_id
        vals = {
            "partner_id": partner.id,
            "partner_shipping_id": partner.id,
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
        # Before _trendyol_apply_status on purpose: that call confirms the order, which
        # reserves stock, which decrements free_qty by this very order's quantity. Read
        # availability first or every order reports itself as short.
        order._trendyol_notify_new_order()
        order._trendyol_apply_status(pkg.get("status"))
        return order

    def _trendyol_notify_new_order(self):
        """Ping the backend's notify list once, when the order is first created.

        Idempotent by construction: creation happens exactly once per package (the
        trendyol_package_uniq constraint guarantees it), so there is no "already
        notified" flag to keep.

        The body names each product with its ordered vs available quantity because a bare
        "new order arrived" ping is useless here: Wayakit KSA regularly sits at zero free
        stock, and whoever reads this has to know whether the item must be manufactured
        before the warehouse can pick it (see the Guayaquil/Wayakit question on the
        ticket — WH/OUT/02005 sat unshipped for a week for exactly this reason)."""
        self.ensure_one()
        backend = self.trendyol_backend_id
        partners = backend.notify_user_ids.partner_id
        if not partners:
            return False
        location = backend.warehouse_location_id
        rows, short = [], False
        for line in self.order_line.filtered(lambda l: not l.display_type):
            product = (line.product_id.with_context(location=location.id) if location
                       else line.product_id)
            free = product.free_qty
            # only storables have a meaningful free_qty; a service is never "short"
            missing = (line.product_uom_qty - free) if line.product_id.type == "product" else 0
            short = short or missing > 0
            rows.append("<li>%s — %s ordered, %s available%s</li>" % (
                html_escape(line.product_id.display_name), line.product_uom_qty, free,
                " <b>&#9888; must be manufactured</b>" if missing > 0 else ""))
        body = Markup(
            "<p>New Trendyol order <b>%s</b>%s.</p><ul>%s</ul>%s" % (
                html_escape(self.trendyol_order_number or ""),
                " — <b>stock is short</b>" if short else "",
                "".join(rows),
                "<p>Manufacturing has to produce the missing quantity before the delivery "
                "can be picked and shipped.</p>" if short else ""))
        # subscribe as well as notify: they then also get the Cancelled/Returned notices
        # this order may post later.
        self.message_subscribe(partner_ids=partners.ids)
        self.message_post(body=body, partner_ids=partners.ids,
                          subtype_xmlid="mail.mt_comment")
        return True

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
            if not lines:
                # Trendyol answers a lines-less body with an opaque 404. Orders imported
                # before the lineId fix have none; they can only be pushed by re-importing.
                raise ValueError(
                    "no Trendyol line id on this order — re-import it to push its status")
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
        Only moves forward: Cancelled/Returned are handed to a human (see below)."""
        self.ensure_one()
        self.trendyol_status = status or self.trendyol_status
        if (status and not mapping.should_import(status)
                and self.trendyol_alerted_status != status):
            # Cancelled / Returned / UnDelivered / UnSupplied. ponytail: no automation —
            # Wayakit sees roughly one cancellation a year, so cancelling the SO or
            # building the stock return in code would be more maintenance than the two
            # clicks it replaces. Just make sure a human hears about it: the chatter
            # reaches the salesperson, who follows the order.
            # Guarded on what we ALREADY announced, not on "the status changed": Trendyol
            # redelivers webhooks and sends them out of order (stage sent Delivered and
            # Returned 6 s apart and the notice fired twice), so comparing against the
            # previous status is not idempotent.
            self.trendyol_alerted_status = status
            self.message_post(body=_(
                "Trendyol: package is now %s. This order needs manual handling in Odoo "
                "(cancel it, or process the return).") % status)
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
    def _trendyol_buyer_partner(self, backend, pkg):
        """One res.partner per real buyer, reused on repeat orders.

        Reverses the original design (generic partner + a delivery child per order):
        Wayakit wants the buyer's own contact, which is also what ops already creates by
        hand in production under the name "Trendyol - <name>". Returns False when the
        payload carries no name at all — the caller then falls back to the generic
        marketplace partner rather than creating an anonymous contact per order."""
        info = mapping.buyer(pkg)
        if not info["name"]:
            return False
        Partner = self.env["res.partner"]
        name = "Trendyol - %s" % info["name"]

        # 1. the customer id is the real dedup key (same lesson as trendyol_package_id:
        #    match on an id we stored, never on a value that can drift).
        partner = (Partner.search([("trendyol_customer_ref", "=", info["ref"])], limit=1)
                   if info["ref"] else Partner.browse())
        # 2. no id (Trendyol masks buyer data on MENA) -> fall back to the name, which is
        #    also what picks up the contacts ops created by hand before this module.
        if not partner:
            partner = Partner.search([("name", "=ilike", name)], limit=1)

        country = self.env["res.country"].search(
            [("code", "=", info["country_code"] or (backend.store_front_code or "").upper())],
            limit=1)
        # whatsapp_sale (Enterprise) sends a WhatsApp message off partner_id.mobile/phone on
        # every order confirmation. That never used to run — the customer was the generic
        # "Trendyol Marketplace" partner, which has no phone. Now that a real buyer is the
        # customer, a malformed number (seen on Trendyol's own stage sandbox test data)
        # reaches that automation and raises INSIDE action_confirm(), which _trendyol_confirm
        # correctly catches — but it means the order silently never auto-confirms. Validate
        # with Odoo's own formatter (reused, not reimplemented) and drop what doesn't parse
        # rather than write a value another module's automation will choke on later.
        phone = (Partner._phone_format(number=info["phone"], country=country,
                                       raise_exception=False)
                 if info["phone"] and country else False)
        if info["phone"] and not phone:
            _logger.warning("Trendyol order %s: buyer phone %r did not validate for %s, dropped",
                            pkg.get("orderNumber"), info["phone"], country.code)
        # Only the fields Trendyol actually sent. The address usually travels on Trendyol's
        # shipping label, not the API, so most of these stay empty on MENA payloads.
        addr = {k: v for k, v in (("street", info["street"]), ("street2", info["street2"]),
                                  ("city", info["city"]), ("zip", info["zip"]),
                                  ("phone", phone)) if v}
        # country_id is NOT optional: it drives the fiscal position, and with it the tax on
        # the order. Getting it wrong silently breaks the "total == Trendyol gross" invariant.
        if country:
            addr["country_id"] = country.id

        if partner:
            # Never overwrite what a human typed — only fill the blanks, and stamp the
            # customer id so the next order matches on the id instead of the name.
            fill = {k: v for k, v in addr.items() if not partner[k]}
            if info["ref"] and not partner.trendyol_customer_ref:
                fill["trendyol_customer_ref"] = info["ref"]
            if fill:
                partner.write(fill)
            return partner

        return Partner.create(dict(addr, **{
            "name": name,
            "type": "contact",
            "customer_rank": 1,
            "trendyol_customer_ref": info["ref"] or False,
        }))


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    trendyol_line_id = fields.Char(
        string="Trendyol Line ID", readonly=True, copy=False,
        help="Trendyol's own order-line id. Needed to push a per-line package status "
             "(PUT shipment-packages expects lines[].lineId).",
    )
