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
    marketplace_partner_id = fields.Many2one(
        "res.partner", string="Marketplace Partner", required=True,
        default=lambda self: self.env.ref(
            "trendyol_connector.partner_trendyol_marketplace", raise_if_not_found=False),
        help="Generic customer used on every imported order. Real buyer address is stored "
             "as a per-order delivery child of this partner.",
    )

    last_sync_date = fields.Datetime(
        string="Last Order Sync (UTC)", readonly=True, copy=False,
        help="Cursor: next sync pulls packages modified after this instant.",
    )

    # --- Webhook (real-time inbound; cron stays as reconciliation) ---
    webhook_id = fields.Char(string="Trendyol Webhook ID", readonly=True, copy=False)
    webhook_api_key = fields.Char(
        string="Webhook API Key", copy=False,
        default=lambda self: secrets.token_urlsafe(32),
        help="Shared secret Trendyol sends back as x-api-key on every webhook call. "
             "Auto-generated; regenerating requires re-registering the webhook.",
    )
    webhook_url = fields.Char(compute="_compute_webhook_url", string="Webhook URL")

    def _compute_webhook_url(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for rec in self:
            rec.webhook_url = base.rstrip("/") + "/trendyol/webhook"

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
            pkg_id = str(pkg.get("id") or pkg.get("shipmentPackageId") or "")
            if not pkg_id:
                continue
            order = SaleOrder.search([("trendyol_package_id", "=", pkg_id)], limit=1)
            if order:
                order.trendyol_status = pkg.get("status") or order.trendyol_status
                handled += 1
            elif mapping.should_import(pkg.get("status")) and SaleOrder._create_from_trendyol(self, pkg):
                handled += 1
        return handled

    def action_check_products(self):
        """Reconcile Trendyol approved products vs Odoo SKUs (default_code).
        The Odoo SKU can live in Trendyol's Model code (productMainId), Stock code
        (stockCode) or barcode. Reports variants that match no product.product."""
        self.ensure_one()
        # active_test=False so archived products are diagnosed as "archived", not "missing".
        Product = self.env["product.product"].with_context(active_test=False)
        path = "/integration/product/sellers/%s/products/approved" % self.seller_id
        page, total, missing = 0, 0, []
        while True:
            data = self._request("GET", path, params={"page": page, "size": 100})
            for content in data.get("content") or []:
                model_code = content.get("productMainId")  # Trendyol "Model code"
                title = content.get("title", "")[:40]
                for var in content.get("variants") or []:
                    total += 1
                    codes = [c for c in (model_code, content.get("stockCode"),
                                         var.get("stockCode"), var.get("barcode")) if c]
                    # order="active desc" -> prefer an active match over an archived duplicate
                    match = (Product.search([("default_code", "in", codes)],
                                            order="active desc", limit=1)
                             if codes else Product.browse())
                    label = model_code or var.get("stockCode") or "?"
                    if not match:
                        missing.append("%s (%s) — not in Odoo" % (label, title))
                    elif not match.active:
                        missing.append("%s (%s) — ARCHIVED in Odoo" % (label, title))
            page += 1
            if page >= (data.get("totalPages") or 1):
                break
        if missing:
            _logger.warning("Trendyol SKU check: %s unmatched of %s: %s", len(missing), total, missing)
        msg = (_("%s of %s Trendyol variants have no matching Odoo SKU:\n%s") % (
            len(missing), total, "\n".join(missing[:20]) + ("\n…" if len(missing) > 20 else ""))
            if missing else _("All %s Trendyol variants match an Odoo SKU.") % total)
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
        page, created = 0, 0
        while True:
            data = self._request("GET", path, params=dict(base_params, page=page))
            content = data.get("content") or []
            for pkg in content:
                if not mapping.should_import(pkg.get("status")):
                    continue
                pkg_id = str(pkg.get("id"))
                if SaleOrder.search_count([("trendyol_package_id", "=", pkg_id)]):
                    continue
                if SaleOrder._create_from_trendyol(self, pkg):
                    created += 1
            page += 1
            if page >= (data.get("totalPages") or 1) or not content:
                break
        self.last_sync_date = now
        _logger.info("Trendyol backend %s: imported %s new order(s)", self.name, created)
        return created
