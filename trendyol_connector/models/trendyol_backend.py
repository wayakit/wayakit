import logging
import secrets
import time
from datetime import timedelta

import requests
from requests.auth import HTTPBasicAuth

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from . import mapping

_logger = logging.getLogger(__name__)

MAX_RETRIES = 3
PAGE_SIZE = 200               # Trendyol max page size for orders
DEFAULT_LOOKBACK_DAYS = 7     # first sync window when no cursor yet (API allows up to 3 months back)
REQUEST_TIMEOUT = 30


class TrendyolBackend(models.Model):
    _name = "trendyol.backend"
    _description = "Trendyol MENA Backend"

    name = fields.Char(required=True, default="Trendyol MENA")
    active = fields.Boolean(default=True)

    # --- Auth (Seller Center -> Integration Information) ---
    seller_id = fields.Char(string="Supplier / Seller ID", required=True)
    api_key = fields.Char(string="API Key", required=True)
    api_secret = fields.Char(string="API Secret", required=True)

    environment = fields.Selection(
        [("prod", "Production"), ("stage", "Stage")],
        default="prod", required=True,
        help="Stage requires IP authorization by Trendyol and uses separate credentials.",
    )
    base_url = fields.Char(
        required=True,
        default="https://apigw.trendyol.com",
        help="Trendyol International API gateway. Prod: https://apigw.trendyol.com — "
             "Stage: https://stageapigw.trendyol.com",
    )
    store_front_code = fields.Char(
        string="StoreFront Code", required=True, default="SA",
        help="Required header on every order call. GULF region: SA = Saudi Arabia.",
    )

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
    )
    warehouse_location_id = fields.Many2one(
        "stock.location", string="FBM Stock Location",
        default=lambda self: self.env.ref("stock.stock_location_stock", raise_if_not_found=False),
        help="Location Wayakit ships FBM orders from (KSA WH/Stock). Used from Phase 2 on.",
    )
    salesperson_id = fields.Many2one(
        "res.users", string="Salesperson", domain=[("share", "=", False)],
        help="Salesperson set on every imported order. Leave empty for no salesperson. "
             "Set explicitly so cron, webhook and the manual button all produce the same "
             "thing — otherwise the order inherits whoever happened to click the button.",
    )
    marketplace_partner_id = fields.Many2one(
        "res.partner", string="Marketplace Partner", required=True,
        default=lambda self: self.env.ref(
            "trendyol_connector.partner_trendyol_marketplace", raise_if_not_found=False),
        help="Generic customer used on every imported order. Real buyer address is stored "
             "as a per-order delivery child of this partner.",
    )

    # --- Phase 2: shipping & stock ---
    auto_confirm = fields.Boolean(
        string="Confirm Imported Orders", default=True,
        help="Confirm every imported order (draft -> sales order) so the delivery is created "
             "from the FBM stock location. A Trendyol package is already paid, there is "
             "nothing to quote. Turn off to go back to Phase 1 behaviour (draft only).",
    )
    push_status = fields.Boolean(
        string="Push Status to Trendyol", default=True,
        help="Notify Trendyol that the package is being prepared (status Picking) when the "
             "order is confirmed. Shipped/Delivered cannot be set by the seller — Trendyol "
             "derives them from the tracking number.",
    )
    push_stock = fields.Boolean(
        string="Push Stock Levels", default=True,
        help="Include this backend in the 'Trendyol: Push Stock' cron. Quantities only — "
             "prices stay owned by Seller Center.",
    )
    stock_last_push = fields.Datetime(string="Last Stock Push", readonly=True, copy=False)

    last_sync_date = fields.Datetime(
        string="Last Order Sync", copy=False,
        help="Cursor: next sync pulls packages modified after this instant. Stored in UTC but "
             "shown and typed in YOUR timezone, like every Odoo datetime — the import log "
             "prints the raw UTC window. Editable on purpose: set it back to re-pull orders "
             "Trendyol will not touch again, or clear it to fall back to the last 7 days.",
    )

    # --- Webhook (real-time inbound; cron stays as reconciliation) ---
    webhook_id = fields.Char(string="Trendyol Webhook ID", readonly=True, copy=False)
    webhook_api_key = fields.Char(
        string="Webhook API Key", copy=False,
        default=lambda self: secrets.token_urlsafe(32),
        help="Shared secret Trendyol sends back as x-api-key on every webhook call. "
             "Auto-generated; regenerating requires re-registering the webhook.",
    )
    webhook_url = fields.Char(
        string="Webhook URL", copy=False,
        default=lambda self: self._default_webhook_url(),
        help="Endpoint Trendyol POSTs to. Defaults to web.base.url + /trendyol/webhook, but "
             "editable on purpose: on odoo.sh web.base.url often points at a custom domain "
             "or a restored dump, not at the build actually serving this database. Whatever "
             "is here is what gets registered on Trendyol — it must be publicly reachable.",
    )

    @api.model
    def _default_webhook_url(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        return base.rstrip("/") + "/trendyol/webhook"

    @api.onchange("environment")
    def _onchange_environment(self):
        self.base_url = ("https://stageapigw.trendyol.com" if self.environment == "stage"
                         else "https://apigw.trendyol.com")

    # ------------------------------------------------------------------ HTTP
    def _request(self, method, path, params=None, payload=None):
        """Basic-auth request with retry on 429/5xx, hard fail on 401/403."""
        self.ensure_one()
        url = self.base_url.rstrip("/") + path
        auth = HTTPBasicAuth(self.api_key or "", self.api_secret or "")
        headers = {
            "User-Agent": "%s - SelfIntegration" % (self.seller_id or ""),
            "storeFrontCode": self.store_front_code or "SA",
            "Content-Type": "application/json",
        }
        last_err = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.request(
                    method, url, auth=auth, headers=headers,
                    params=params, json=payload, timeout=REQUEST_TIMEOUT,
                )
            except requests.RequestException as e:
                last_err = str(e)
                time.sleep(2 ** attempt)
                continue

            if resp.status_code == 429:
                wait = resp.headers.get("Retry-After")
                time.sleep(min(int(wait) if wait and wait.isdigit() else 2 ** attempt, 30))
                last_err = "rate limited (429)"
                continue
            if resp.status_code in (401, 403):
                raise UserError(_(
                    "Trendyol authentication failed (%s). Check Seller ID / API Key / API Secret."
                ) % resp.status_code)
            if resp.status_code >= 500:
                last_err = "server error %s" % resp.status_code
                time.sleep(2 ** attempt)
                continue
            if not resp.ok:
                raise UserError(_("Trendyol API error %s: %s") % (resp.status_code, resp.text[:500]))
            try:
                return resp.json()
            except ValueError:  # webhook delete/activate answer text/plain "200 OK"
                return resp.text
        raise UserError(_("Trendyol request failed after %s retries: %s") % (MAX_RETRIES, last_err))

    def _orders_path(self):
        return "/integration/order/sellers/%s/orders" % self.seller_id

    def _package_path(self, package_id, suffix=""):
        return "/integration/order/sellers/%s/shipment-packages/%s%s" % (
            self.seller_id, package_id, suffix)

    # ------------------------------------------------------- outbound (Phase 2)
    def _update_package_status(self, package_id, status, lines=None, params=None):
        """Notify Trendyol of a package status. Only "Picking" and "Invoiced" are
        settable by the seller: "Shipped"/"Delivered" are derived by Trendyol from the
        tracking number and are rejected here."""
        self.ensure_one()
        payload = {"status": status}
        if lines:
            payload["lines"] = lines
        if params:
            payload["params"] = params
        return self._request("PUT", self._package_path(package_id), payload=payload)

    def _update_tracking(self, package_id, sender_number, provider_code):
        """Send our own waybill number (FBM: Wayakit ships, so Trendyol only learns the
        tracking number from us). Requires the package to be in Picking already."""
        self.ensure_one()
        return self._request(
            "PUT", self._package_path(package_id, "/tracking-details"),
            payload={"cargoSenderNumber": sender_number, "providerCode": provider_code})

    # --------------------------------------------------------------- actions
    def action_test_connection(self):
        """Lightweight call to validate credentials/host."""
        self.ensure_one()
        self._request("GET", self._orders_path(), params={"size": 1, "page": 0})
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "title": _("Trendyol"),
                "message": _("Connection OK for seller %s.") % self.seller_id,
                "sticky": False,
            },
        }

    # ------------------------------------------------------------- webhooks
    # Webhook enum spells statuses CREATED / AT_COLLECTION_POINT etc.
    # Importables + CANCELLED (to reflect the status on already-imported orders).
    WEBHOOK_STATUSES = ["CREATED", "PICKING", "INVOICED", "SHIPPED",
                        "AT_COLLECTION_POINT", "DELIVERED", "CANCELLED"]

    def _webhook_path(self, suffix=""):
        return "/integration/webhook/sellers/%s/webhooks%s" % (self.seller_id, suffix)

    def action_register_webhook(self):
        """Create (or update, if already registered) the webhook on Trendyol."""
        self.ensure_one()
        payload = {
            "url": self.webhook_url,
            "authenticationType": "API_KEY",
            "apiKey": self.webhook_api_key,
            "subscribedStatuses": self.WEBHOOK_STATUSES,
        }
        if self.webhook_id:
            self._request("PUT", self._webhook_path("/%s" % self.webhook_id), payload=payload)
        else:
            res = self._request("POST", self._webhook_path(), payload=payload)
            self.webhook_id = isinstance(res, dict) and res.get("id") or False
            if not self.webhook_id:
                raise UserError(_("Trendyol did not return a webhook id: %s") % res)
        return self._notify(_("Webhook registered: %s") % self.webhook_id)

    def action_unregister_webhook(self):
        self.ensure_one()
        if self.webhook_id:
            self._request("DELETE", self._webhook_path("/%s" % self.webhook_id))
            self.webhook_id = False
        return self._notify(_("Webhook deleted."))

    def _notify(self, message, warning=False):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "warning" if warning else "success",
                "title": _("Trendyol"),
                "message": message,
                "sticky": warning,
            },
        }

    def _process_webhook_payload(self, payload):
        """Handle one inbound webhook call. New importable package -> create order;
        known package -> refresh its status. Anything else is ignored (cron catches up)."""
        self.ensure_one()
        SaleOrder = self.env["sale.order"]
        handled = 0
        for pkg in mapping.extract_packages(payload):
            pkg_id = mapping.package_id(pkg)
            if not pkg_id:
                continue
            order = SaleOrder.search([("trendyol_package_id", "=", pkg_id)], limit=1)
            if order:
                order._trendyol_apply_status(pkg.get("status"))
                handled += 1
            elif mapping.should_import(pkg.get("status")) and SaleOrder._create_from_trendyol(self, pkg):
                handled += 1
        return handled

    def _iter_approved_variants(self):
        """Yield (content, variant) for every approved Trendyol variant, paging the catalog.
        Shared by the SKU report and the stock push so both see exactly the same catalog."""
        self.ensure_one()
        path = "/integration/product/sellers/%s/products/approved" % self.seller_id
        page = 0
        while True:
            data = self._request("GET", path, params={"page": page, "size": 100})
            for content in data.get("content") or []:
                for var in content.get("variants") or []:
                    yield content, var
            page += 1
            if page >= (data.get("totalPages") or 1):
                break

    @api.model
    def _variant_codes(self, content, var):
        """Candidate Odoo default_codes for a Trendyol variant. Wayakit keeps its SKU in the
        Model code (productMainId); stockCode/barcode are the fallbacks."""
        return [c for c in (content.get("productMainId"), content.get("stockCode"),
                            var.get("stockCode"), var.get("barcode")) if c]

    def action_check_products(self):
        """Reconcile Trendyol approved products vs Odoo SKUs (default_code).
        The Odoo SKU can live in Trendyol's Model code (productMainId), Stock code
        (stockCode) or barcode. Reports variants that match no product.product, plus the
        ones with no Trendyol barcode — those can never be stock-synced (the
        price-and-inventory endpoint keys on barcode and nothing else)."""
        self.ensure_one()
        # active_test=False so archived products are diagnosed as "archived", not "missing".
        Product = self.env["product.product"].with_context(active_test=False)
        total, missing = 0, []
        for content, var in self._iter_approved_variants():
            total += 1
            model_code = content.get("productMainId")  # Trendyol "Model code"
            title = content.get("title", "")[:40]
            codes = self._variant_codes(content, var)
            # order="active desc" -> prefer an active match over an archived duplicate
            match = (Product.search([("default_code", "in", codes)],
                                    order="active desc", limit=1)
                     if codes else Product.browse())
            label = model_code or var.get("stockCode") or "?"
            if not match:
                missing.append("%s (%s) — not in Odoo" % (label, title))
            elif not match.active:
                missing.append("%s (%s) — ARCHIVED in Odoo" % (label, title))
            elif not var.get("barcode"):
                missing.append("%s (%s) — no barcode on Trendyol (stock cannot be pushed)"
                               % (label, title))
        if missing:
            _logger.warning("Trendyol SKU check: %s issues of %s: %s", len(missing), total, missing)
        msg = (_("%s of %s Trendyol variants need attention:\n%s") % (
            len(missing), total, "\n".join(missing[:20]) + ("\n…" if len(missing) > 20 else ""))
            if missing else _("All %s Trendyol variants match an active Odoo SKU and have a "
                              "barcode.") % total)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "warning" if missing else "success",
                "title": _("Trendyol Product Check"),
                "message": msg,
                "sticky": bool(missing),
            },
        }

    def action_import_orders(self):
        """Button handler: import just the selected backend(s) now.
        Reports the full breakdown, not just the created count — "0 imported" has four
        very different causes and the notification is the only thing the user ever sees."""
        totals, window, skus = {}, "", set()
        for backend in self:
            res = backend._import_orders()
            window = res.pop("window")
            skus.update(res.pop("missing_skus"))
            for key, val in res.items():
                totals[key] = totals.get(key, 0) + val
        # ponytail: one flat line — display_notification does not honour newlines.
        msg = _(
            "Window %(window)s UTC — Trendyol returned %(seen)s package(s): "
            "%(created)s imported · %(dup)s already in Odoo · "
            "%(not_importable)s not importable (status) · %(unmatched)s unmatched SKU"
        ) % dict(totals, window=window)
        if skus:
            msg += _(" → no product.product has default_code: %s") % ", ".join(sorted(skus))
        return self._notify(msg, warning=not totals.get("created"))

    # ---------------------------------------------------------- stock (Phase 2)
    def _inventory_path(self):
        return "/integration/inventory/sellers/%s/products/price-and-inventory" % self.seller_id

    def push_stock_levels(self):
        """Send the free quantity of every approved Trendyol variant we can match in Odoo.

        Quantity only, never prices: Seller Center keeps owning pricing/promos, and the
        endpoint would happily overwrite them.
        ponytail: pushes the whole catalog every run — that is one request per 1000 variants
        and Wayakit's catalog is in the hundreds. If it grows, diff against the last pushed
        quantity (store it) instead of adding a second cron."""
        self.ensure_one()
        # Active products only (unlike the diagnostic): pushing stock for an archived
        # product is meaningless — it is reported by action_check_products instead.
        Product = self.env["product.product"]
        location = self.warehouse_location_id
        items, skipped = [], []
        for content, var in self._iter_approved_variants():
            label = content.get("productMainId") or var.get("stockCode") or "?"
            barcode = var.get("barcode")
            codes = self._variant_codes(content, var)
            product = (Product.search([("default_code", "in", codes)], limit=1)
                       if codes else Product.browse())
            if not product:
                skipped.append("%s (no Odoo product)" % label)
                continue
            if not barcode:
                skipped.append("%s (no Trendyol barcode)" % label)
                continue
            qty = (product.with_context(location=location.id).free_qty if location
                   else product.free_qty)
            items.append({"barcode": barcode, "quantity": max(int(qty), 0)})

        batches = []
        for batch in mapping.chunks(items):
            res = self._request("POST", self._inventory_path(), payload={"items": batch})
            batches.append(res.get("batchRequestId") if isinstance(res, dict) else res)
        self.stock_last_push = fields.Datetime.now()
        _logger.info("Trendyol backend %s: stock push -> %s item(s) in %s batch(es) %s; "
                     "skipped %s: %s", self.name, len(items), len(batches), batches,
                     len(skipped), skipped)
        return {"pushed": len(items), "skipped": skipped, "batches": batches}

    def action_push_stock(self):
        """Button: push stock for the selected backend(s) now."""
        pushed, skipped, batches = 0, [], []
        for backend in self:
            res = backend.push_stock_levels()
            pushed += res["pushed"]
            skipped += res["skipped"]
            batches += res["batches"]
        msg = _("%(pushed)s quantity(ies) sent in %(n)s batch(es): %(batches)s") % {
            "pushed": pushed, "n": len(batches), "batches": ", ".join(map(str, batches)) or "—"}
        if skipped:
            msg += _(" · %s variant(s) skipped: %s") % (
                len(skipped), ", ".join(skipped[:20]) + ("…" if len(skipped) > 20 else ""))
        return self._notify(msg, warning=not pushed)

    @api.model
    def cron_push_stock(self):
        for backend in self.search([("active", "=", True), ("push_stock", "=", True)]):
            try:
                backend.push_stock_levels()
            except Exception as e:  # never let one backend kill the cron
                _logger.exception("Trendyol stock push failed for backend %s: %s", backend.name, e)

    @api.model
    def cron_import_orders(self):
        for backend in self.search([("active", "=", True)]):
            try:
                backend._import_orders()
            except Exception as e:  # never let one backend kill the cron
                _logger.exception("Trendyol import failed for backend %s: %s", backend.name, e)

    def _import_orders(self):
        """Paginate getShipmentPackages over the [last_sync, now] window and create orders.
        ponytail: standard paginated GET. Trendyol recommends getShipmentPackagesStream for
        large-scale sync — swap _request loop for the stream endpoint if volume outgrows this."""
        self.ensure_one()
        SaleOrder = self.env["sale.order"]
        now = fields.Datetime.now()
        start = self.last_sync_date or (now - timedelta(days=DEFAULT_LOOKBACK_DAYS))
        base_params = {
            "startDate": int(start.timestamp() * 1000),
            "endDate": int(now.timestamp() * 1000),
            "orderByField": "PackageLastModifiedDate",
            "orderByDirection": "ASC",
            "size": PAGE_SIZE,
        }
        path = self._orders_path()
        page, seen, created, dup, not_importable, unmatched = 0, 0, 0, 0, 0, 0
        missing_skus = set()
        while True:
            data = self._request("GET", path, params=dict(base_params, page=page))
            content = data.get("content") or []
            for pkg in content:
                seen += 1
                if not mapping.should_import(pkg.get("status")):
                    not_importable += 1
                    continue
                pkg_id = mapping.package_id(pkg)
                if not pkg_id:
                    _logger.warning("Trendyol order %s has no package id, skipped: %s",
                                    pkg.get("orderNumber"), pkg)
                    unmatched += 1
                    continue
                known = SaleOrder.search([("trendyol_package_id", "=", pkg_id)], limit=1)
                if known:
                    # Reconcile, don't just count: this is the path that catches up an order
                    # whose webhook was missed or whose auto-confirm had failed.
                    known._trendyol_apply_status(pkg.get("status"))
                    dup += 1
                    continue
                if SaleOrder._create_from_trendyol(self, pkg):
                    created += 1
                else:
                    unmatched += 1
                    # cheap re-run (failures only) so the notification can name the SKUs
                    missing_skus.update(SaleOrder._trendyol_order_lines(pkg)[1])
            page += 1
            if page >= (data.get("totalPages") or 1) or not content:
                break
        # Hold the cursor when an order was skipped for an unmatched SKU: the window is
        # on PackageLastModifiedDate, so a package Trendyol never touches again would be
        # lost forever if we advanced past it. Retries every sync until the SKU exists.
        if not unmatched:
            self.last_sync_date = now
        counters = {"seen": seen, "created": created, "dup": dup,
                    "not_importable": not_importable, "unmatched": unmatched}
        _logger.info(
            "Trendyol backend %s: window [%s .. %s] -> %s; cursor %s",
            self.name, start, now, counters,
            "advanced" if not unmatched else "held at %s" % self.last_sync_date)
        counters["window"] = "%s → %s" % (start, now)
        counters["missing_skus"] = sorted(missing_skus)
        return counters
