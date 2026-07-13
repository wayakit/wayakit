import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class TrendyolWebhookController(http.Controller):

    # type="http" (not "json"): Trendyol POSTs plain JSON, not JSON-RPC.
    @http.route("/trendyol/webhook", type="http", auth="public",
                methods=["POST"], csrf=False)
    def trendyol_webhook(self, **kwargs):
        key = request.httprequest.headers.get("x-api-key")
        backend = key and request.env["trendyol.backend"].sudo().search(
            [("webhook_api_key", "=", key), ("active", "=", True)], limit=1)
        if not backend:
            return request.make_response("unauthorized", status=401)

        raw = request.httprequest.get_data(as_text=True) or "{}"
        try:
            payload = json.loads(raw)
        except ValueError:
            _logger.warning("Trendyol webhook: unparseable body: %s", raw[:1000])
            return request.make_response("bad json", status=400)
        try:
            handled = backend._process_webhook_payload(payload)
            return request.make_response("ok:%s" % handled, status=200)
        except Exception:
            # 500 so Trendyol retries if it does; the sync cron reconciles regardless.
            _logger.exception("Trendyol webhook processing failed; body: %s", raw[:2000])
            return request.make_response("error", status=500)