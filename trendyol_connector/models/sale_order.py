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

    _sql_constraints = [
        ("trendyol_package_uniq", "unique(trendyol_package_id)",
         "This Trendyol package is already imported."),
    ]

    # ------------------------------------------------------------- import API
    @api.model
    def _create_from_trendyol(self, backend, pkg):
        """Build a draft sale.order from one Trendyol shipment package.
        Returns the order, or False if any line SKU can't be matched (order is
        skipped whole so we never create a half order — it retries next sync)."""
        lines, missing = self._trendyol_order_lines(pkg)
        if missing:
            _logger.warning(
                "Trendyol order %s skipped: unmatched SKU(s) %s",
                pkg.get("orderNumber"), missing)
            return False

        ship_partner = self._trendyol_shipping_partner(backend, pkg)
        order = self.create({
            "partner_id": backend.marketplace_partner_id.id,
            "partner_shipping_id": (ship_partner or backend.marketplace_partner_id).id,
            "company_id": backend.company_id.id,
            "origin": "Trendyol %s" % (pkg.get("orderNumber") or ""),
            "client_order_ref": pkg.get("orderNumber"),
            "date_order": mapping.epoch_ms_to_dt(pkg.get("orderDate")) or fields.Datetime.now(),
            "trendyol_backend_id": backend.id,
            "trendyol_package_id": str(pkg.get("id")),
            "trendyol_order_number": pkg.get("orderNumber"),
            "trendyol_status": pkg.get("status"),
            "order_line": [(0, 0, l) for l in lines],
        })
        return order

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
