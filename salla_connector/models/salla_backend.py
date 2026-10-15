import logging
import time
from datetime import timedelta

import requests
from psycopg2 import errors as pg_errors

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from . import mapping

_logger = logging.getLogger(__name__)

MAX_RETRIES = 3
REQUEST_TIMEOUT = 30
# (connect, read): requests applies each one separately, so a bare 15 meant up to
# ~30 s holding the refresh lock. 5 + 10 keeps the worst case at 15 s.
TOKEN_TIMEOUT = (5, 10)
PER_PAGE = 60                 # Salla max page size
MAX_PAGES = 200               # hard cap: 12 000 products, far above the catalog
# Refresh while the access token (14 days) still has a day left. The daily cron then
# always refreshes before expiry, which also renews the 1-month refresh token.
TOKEN_REFRESH_MARGIN = timedelta(days=1)
# Documented access-token lifetime. Assumed when Salla answers without a readable
# expiry: leaving token_expires_at empty would make EVERY _request refresh again.
DEFAULT_TOKEN_LIFETIME = timedelta(days=14)
# Waiting for another worker that holds the refresh lock: its token POST is bounded
# by TOKEN_TIMEOUT (15 s worst case), so 6 x 3 s covers it without hanging a request
# for long.
LOCK_ATTEMPTS = 6
LOCK_WAIT = 3
# The authorize/revoke write waits for the lock instead of NOWAIT, bounded per attempt;
# 2 x 12 s outlasts a refresh (15 s worst case) and stays under Salla's ~30 s webhook
# timeout. Past that the webhook answers 500 and Salla retries it.
WRITE_LOCK_TIMEOUT = "12s"
WRITE_ATTEMPTS = 2

# Secret fields are restricted IN PYTHON, not only in the view: field groups are what
# blocks a salesman reading them over RPC (read/search_read/export).
SECRET_GROUP = "base.group_system"
# Readable by the sales team, writable only by system: changing them rebinds the
# backend to another store / app, or (expiry) forces/suppresses token refreshes.
SYSTEM_WRITE_FIELDS = ("store_id", "client_id", "token_expires_at")
# Columns the dedicated token cursor may write. Column names are interpolated into the
# UPDATE from THIS tuple only, never from caller input.
TOKEN_COLUMNS = ("access_token", "refresh_token", "token_expires_at", "token_scope", "store_id")


class SallaBackend(models.Model):
    _name = "salla.backend"
    _description = "Salla Store Backend"

    name = fields.Char(required=True, default="Salla KSA")
    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse", string="Warehouse",
        domain="[('company_id', '=', company_id)]",
        default=lambda self: self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1),
        help="Warehouse Salla orders ship from and whose stock is pushed (F2+).",
    )

    # --- Salla app (Partners Portal -> App -> App Keys) ---
    store_id = fields.Char(
        string="Salla Store ID", copy=False,
        help="Salla merchant id. Filled by the app.store.authorize webhook; editable by "
             "an administrator as the recovery lever if that webhook was missed or the "
             "backend has to be re-bound. Webhooks for another store never touch it.",
    )
    client_id = fields.Char(string="Client ID", copy=False)
    client_secret = fields.Char(string="Client Secret", copy=False, groups=SECRET_GROUP)
    webhook_secret = fields.Char(
        string="Webhook Secret", copy=False, groups=SECRET_GROUP,
        help="Salla signs every webhook with this (HMAC-SHA256 of the raw body, header "
             "X-Salla-Signature). It belongs to the Salla app, so a demo store and the "
             "real store installed on the same app share it.",
    )

    # --- OAuth tokens (Easy Mode: delivered by the app.store.authorize webhook) ---
    access_token = fields.Char(copy=False, groups=SECRET_GROUP)
    refresh_token = fields.Char(
        copy=False, groups=SECRET_GROUP,
        help="SINGLE-USE. Reusing a spent one can force reinstalling the app on the "
             "store, which is why the refresh runs under a row lock.",
    )
    token_expires_at = fields.Datetime(
        string="Access Token Expires", copy=False,
        help="UTC. The daily cron refreshes the token a day before this.",
    )
    token_scope = fields.Char(
        string="Granted Scopes", copy=False, readonly=True,
        help="Scopes the store owner granted. A 403 from Salla usually means one is missing.",
    )

    # System-only: whatever host these name receives the client secret, the refresh
    # token and the Bearer token. A sale manager could otherwise point them at a server
    # of their own and collect the credentials on the next refresh.
    base_url = fields.Char(required=True, default="https://api.salla.dev/admin/v2",
                           groups=SECRET_GROUP)
    token_url = fields.Char(required=True, default="https://accounts.salla.sa/oauth2/token",
                            groups=SECRET_GROUP)
    webhook_url = fields.Char(
        string="Webhook URL", copy=False,
        default=lambda self: self._default_webhook_url(),
        help="Endpoint to paste in the Salla app's webhook settings. Defaults to "
             "web.base.url + /sl/webhook, editable because on odoo.sh web.base.url often "
             "points at another build. Use the domain, and on a Cloudflare-fronted domain "
             "add the Skip rule for /sl/webhook first (same trap as Trendyol).",
    )
    log_payloads = fields.Boolean(
        string="Log Full Webhook Payloads", groups=SECRET_GROUP,
        help="Off: webhooks log only their key structure. On: the full body, with "
             "credentials and customer data masked. Turn on only to check field names "
             "against the first real payloads, then off again.",
    )

    @api.model
    def _default_webhook_url(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        return base.rstrip("/") + "/sl/webhook"

    @api.constrains("base_url", "token_url")
    def _check_salla_urls(self):
        for backend in self.sudo():
            for fname in ("base_url", "token_url"):
                if not mapping.is_allowed_salla_url(backend[fname]):
                    raise ValidationError(_(
                        "%s must be an https URL on a Salla host (accounts.salla.sa or "
                        "*.salla.dev).") % self._fields[fname].string)

    def _check_system_write(self, vals):
        if self.env.is_superuser() or self.env.user.has_group(SECRET_GROUP):
            return
        touched = [f for f in SYSTEM_WRITE_FIELDS if f in vals]
        if touched:
            raise AccessError(_("Only an administrator can change %s on a Salla backend.")
                              % ", ".join(touched))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_system_write(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._check_system_write(vals)
        return super().write(vals)

    # ------------------------------------------------------------------ tokens
    # Transaction rules for every caller (F2+ included):
    # - Never write the salla_backend row in a transaction that may also refresh, nor
    #   before calling _request: the row lock that write holds makes the refresh's
    #   NOWAIT fail until that transaction commits. Cursors/counters that sync code needs
    #   (last_sync_date & co.) go on their own cursor or after the API calls.
    # - Token fields are written ONLY through _write_token_row on a dedicated cursor.
    # - Webhook handlers must not call the Salla API inline (Salla waits ~30 s, a 429
    #   alone may sleep 30 s): queue the work, e.g. ir.cron._trigger() on a sync cron.
    def _set_token_cache(self, values):
        """Make the caller's environment see token values committed by another cursor.

        Not invalidate(): the caller's transaction runs in REPEATABLE READ, so a re-read
        after invalidation would return its OLD snapshot — the spent refresh token. The
        values go straight into the cache instead (not marked dirty, so nothing is ever
        written back from this transaction)."""
        rec = self.sudo()
        for fname, value in values.items():
            if fname in TOKEN_COLUMNS:
                self.env.cache.set(rec, self._fields[fname], value or False)

    def _update_token_row(self, cr, values):
        """UPDATE the token columns on `cr`. log_exceptions=False: on a failed execute
        Odoo logs the query WITH its parameters filled in, i.e. the tokens."""
        cols = [c for c in TOKEN_COLUMNS if c in values]
        if not cols:
            return
        assignments = ", ".join("%s = %%s" % c for c in cols)   # names from TOKEN_COLUMNS only
        cr.execute(
            "UPDATE salla_backend SET %s, write_date = (now() at time zone 'UTC') "
            "WHERE id = %%s" % assignments,
            [values[c] or None for c in cols] + [self.id],
            log_exceptions=False)

    def _write_token_row(self, values):
        """Write token columns on a dedicated cursor and commit at once.

        Same reasons as the refresh: the tokens must survive a rollback of the caller's
        transaction, and the caller must not end up holding the row lock (which would
        make every later NOWAIT refresh fail).

        What actually happens on a collision with a refresh in flight: FOR UPDATE waits
        (bounded by WRITE_LOCK_TIMEOUT). When the refresh commits, Postgres does NOT hand
        us the row — under Odoo's REPEATABLE READ a row changed after our snapshot raises
        SerializationFailure. If the refresh outlasts the timeout we get LockNotAvailable.
        Either way the cursor is closed and the write retried on a FRESH cursor (new
        snapshot), which then takes the lock at once. The authorize values win over what
        the refresh wrote: they are the newer grant."""
        self.ensure_one()
        for attempt in range(WRITE_ATTEMPTS):
            cr = self.env.registry.cursor()
            try:
                cr.execute("SET LOCAL lock_timeout = %s", (WRITE_LOCK_TIMEOUT,))
                cr.execute("SELECT id FROM salla_backend WHERE id = %s FOR UPDATE",
                           (self.id,), log_exceptions=False)
                self._update_token_row(cr, values)
                cr.commit()
            except (pg_errors.SerializationFailure, pg_errors.LockNotAvailable):
                cr.rollback()
                if attempt == WRITE_ATTEMPTS - 1:
                    raise
                _logger.info("Salla backend %s: token row busy, retrying the write on a "
                             "fresh cursor.", self.name)
                continue
            finally:
                cr.close()
            self._set_token_cache(values)
            return

    def _refresh_token(self, stale_access_token=None, force=False):
        """Refresh the OAuth token pair safely and return the current tokens dict
        {access_token, refresh_token, token_expires_at}.

        Salla's refresh token is single-use, so two workers refreshing at once would burn
        it. Hence: a SEPARATE cursor, SELECT ... FOR UPDATE NOWAIT on the row, re-check
        inside the lock, and an immediate COMMIT on that cursor — the new refresh token
        must survive a rollback of the caller's transaction.

        `stale_access_token` = the token the caller just saw fail/expire. If the row
        already holds a different one, another worker refreshed in the meantime: use it.
        """
        self.ensure_one()
        for attempt in range(LOCK_ATTEMPTS):
            busy = False
            cr = self.env.registry.cursor()
            try:
                try:
                    cr.execute(
                        "SELECT client_id, client_secret, token_url, access_token, "
                        "refresh_token, token_expires_at FROM salla_backend "
                        "WHERE id = %s FOR UPDATE NOWAIT", (self.id,), log_exceptions=False)
                except (pg_errors.LockNotAvailable, pg_errors.SerializationFailure):
                    # Locked by another refresher, or changed under our snapshot: either
                    # way the next attempt, on a fresh cursor, sees the outcome.
                    cr.rollback()
                    busy = True
                if not busy:
                    return self._refresh_locked(cr, stale_access_token, force)
            finally:
                cr.close()
            # Sleep only after closing: no idle connection held while waiting.
            if attempt < LOCK_ATTEMPTS - 1:
                time.sleep(LOCK_WAIT)
        raise UserError(_(
            "Salla backend %s: another process kept the token refresh lock for over %s s. "
            "Try again in a minute.") % (self.name, LOCK_ATTEMPTS * LOCK_WAIT))

    def _refresh_locked(self, cr, stale_access_token, force):
        """Body of _refresh_token, run while `cr` holds the row lock."""
        row = cr.fetchone()
        if not row:
            raise UserError(_("Salla backend %s no longer exists.") % self.id)
        client_id, client_secret, token_url, access, refresh, expires = row
        current = {"access_token": access, "refresh_token": refresh,
                   "token_expires_at": expires}
        now = fields.Datetime.now()
        someone_refreshed = bool(stale_access_token) and access != stale_access_token
        if someone_refreshed or (
                not force and not mapping.token_needs_refresh(expires, now, TOKEN_REFRESH_MARGIN)):
            cr.rollback()
            self._set_token_cache(current)
            return current
        if not refresh:
            raise UserError(_(
                "Salla backend %s has no refresh token. Install (or reinstall) the app on "
                "the store so Salla sends app.store.authorize.") % self.name)

        # The point of no return: once Salla answers, the old refresh token is spent.
        # Deliberately no retry here — resending a spent token is exactly what can
        # revoke the app.
        tokens = self._post_token_refresh(token_url, client_id, client_secret, refresh, now)
        if not tokens["refresh_token"]:
            _logger.warning("Salla backend %s: token refresh answered without a refresh "
                            "token; keeping the previous one, which may now be spent.",
                            self.name)
        if not tokens["expires_at"]:
            tokens["expires_at"] = now + DEFAULT_TOKEN_LIFETIME
            _logger.warning("Salla backend %s: token refresh gave no readable expiry; "
                            "assuming %s days.", self.name, DEFAULT_TOKEN_LIFETIME.days)
        values = {"access_token": tokens["access_token"],
                  "refresh_token": tokens["refresh_token"] or refresh,
                  "token_expires_at": tokens["expires_at"]}
        if tokens["scope"]:
            values["token_scope"] = tokens["scope"]
        try:
            self._update_token_row(cr, values)
            cr.commit()
        except Exception:
            _logger.critical(
                "Salla backend %s (id %s): token refresh SUCCEEDED at Salla but the new "
                "tokens could NOT be saved. The old refresh token is spent; the app must be "
                "reinstalled on the store to get new tokens.",
                self.name, self.id, exc_info=True)
            raise
        _logger.info("Salla backend %s: access token refreshed, expires %s UTC",
                     self.name, values["token_expires_at"])
        self._set_token_cache(values)
        return {k: values[k] for k in ("access_token", "refresh_token", "token_expires_at")}

    @api.model
    def _post_token_refresh(self, token_url, client_id, client_secret, refresh, now):
        """POST grant_type=refresh_token. Returns mapping.parse_tokens() output.

        Errors carry only Salla's `error`/`error_description`, never the response body:
        a token endpoint response is the one body that can hold live credentials."""
        if not mapping.is_allowed_salla_url(token_url):
            # The ORM constraint covers the form; this covers a row edited by SQL.
            raise UserError(_("Salla token URL is not a Salla host; refusing to send credentials."))
        try:
            resp = requests.post(token_url, data={
                "grant_type": "refresh_token",
                "client_id": client_id or "",
                "client_secret": client_secret or "",
                "refresh_token": refresh,
            }, headers={"Accept": "application/json"}, timeout=TOKEN_TIMEOUT,
                # A 307/308 would resend client_secret + refresh_token in the body to
                # whatever host the Location names. Salla's token URL never redirects.
                allow_redirects=False)
        except requests.ConnectTimeout:
            # Never connected: the refresh token was not sent, still valid.
            raise UserError(_("Salla token endpoint unreachable (connect timeout)."))
        except requests.RequestException as e:
            # Sent, but no answer read: Salla may have rotated the token already.
            _logger.error("Salla token refresh: no answer (%s); the refresh token may "
                          "already be spent.", type(e).__name__)
            raise UserError(_(
                "Salla did not answer the token refresh (%s). The refresh token MAY already "
                "be spent: if the next refresh fails with invalid_grant, reinstall the app "
                "on the store.") % type(e).__name__)
        # allow_redirects=False makes a 3xx come back as the response itself, and
        # resp.ok is True below 400: without this it would read as "no access token".
        # Fixed label, no URL or Location: nothing about where it pointed is echoed.
        if 300 <= resp.status_code < 400:
            _logger.error("Salla token refresh: unexpected redirect (%s); refresh token "
                          "not followed elsewhere.", resp.status_code)
            raise UserError(_("Salla answered an unexpected redirect (%s) on the token "
                              "refresh.") % resp.status_code)
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if not resp.ok:
            reason = ""
            if isinstance(data, dict):
                reason = " ".join(mapping.text(data.get(k)) for k in ("error", "error_description")
                                  if mapping.text(data.get(k)))[:200]
            _logger.error("Salla token refresh rejected (%s): %s", resp.status_code, reason)
            raise UserError(_(
                "Salla rejected the token refresh (%s) %s. If it says invalid_grant the "
                "refresh token is dead: reinstall the app on the store.") % (resp.status_code, reason))
        tokens = mapping.parse_tokens(data, now)
        if not tokens:
            _logger.error("Salla token refresh: 2xx without access_token; response keys: %s",
                          mapping.payload_keys(data))
            raise UserError(_("Salla token refresh returned no access token."))
        return tokens

    @api.model
    def cron_refresh_tokens(self):
        """Daily: refresh every token nearing expiry, so the 1-month refresh token never
        lapses on a store that happens to have no API traffic."""
        for backend in self.search([("active", "=", True)]):
            try:
                if not backend.sudo().refresh_token:
                    continue
                backend._refresh_token()
            except Exception as e:  # never let one backend kill the cron
                _logger.exception("Salla token refresh failed for backend %s: %s",
                                  backend.name, e)

    def action_refresh_token(self):
        self.ensure_one()
        # The view hides the button, but any object method is callable over RPC.
        if not self.env.user.has_group(SECRET_GROUP):
            raise AccessError(_("Only an administrator can force a Salla token refresh."))
        tokens = self._refresh_token(stale_access_token=self.sudo().access_token, force=True)
        return self._notify(_("Token valid until %s UTC.") % tokens["token_expires_at"])

    # ------------------------------------------------------------------ HTTP
    def _request(self, method, path, params=None, payload=None):
        """Bearer request. Retries 429 (Retry-After / X-RateLimit-Reset) and 5xx/network
        with backoff; refreshes the token proactively near expiry and once on a 401.
        See the transaction rules above _set_token_cache before calling it."""
        self.ensure_one()
        backend = self.sudo()  # tokens/URLs are system-only fields; never exposed here
        if not mapping.is_allowed_salla_url(backend.base_url):
            raise UserError(_("Salla API URL is not a Salla host; refusing to send the token."))
        if not backend.access_token:
            raise UserError(_(
                "Salla backend %s is not authorized yet: install the app on the store "
                "(Salla sends the tokens through app.store.authorize).") % self.name)
        token = backend.access_token
        if backend.refresh_token and mapping.token_needs_refresh(
                backend.token_expires_at, fields.Datetime.now(), TOKEN_REFRESH_MARGIN):
            try:
                token = self._refresh_token(stale_access_token=token)["access_token"] or token
            except UserError as e:
                # The current token may still have hours left: try it rather than fail.
                _logger.warning("Salla backend %s: proactive refresh failed: %s", self.name, e)

        url = backend.base_url.rstrip("/") + path
        refreshed, attempt, last_err = False, 0, None
        while attempt < MAX_RETRIES:
            headers = {
                "Authorization": "Bearer %s" % token,
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            try:
                # No redirects: the Bearer token must not follow a Location header off
                # the allowlisted host. The 3xx is turned into an error right below.
                resp = requests.request(method, url, headers=headers, params=params,
                                        json=payload, timeout=REQUEST_TIMEOUT,
                                        allow_redirects=False)
            except requests.RequestException as e:
                last_err = type(e).__name__
                attempt += 1
                if attempt < MAX_RETRIES:
                    time.sleep(mapping.retry_delay(None, {}, attempt - 1))
                continue
            # resp.ok is True for a 3xx: without this a redirect would read as a success
            # with an empty body. No Location in the message.
            if 300 <= resp.status_code < 400:
                raise UserError(_("Salla answered an unexpected redirect (%s) on %s.") % (
                    resp.status_code, path))

            if resp.status_code == 401:
                if refreshed:
                    raise UserError(_(
                        "Salla rejected the token even after a refresh (401). Reinstall the "
                        "app on the store."))
                # One refresh per call, then the loop retries; no recursion into _request.
                token = self._refresh_token(stale_access_token=token, force=True)["access_token"]
                refreshed = True
                continue
            delay = mapping.retry_delay(resp.status_code, resp.headers, attempt)
            if delay is not None:
                last_err = "HTTP %s" % resp.status_code
                attempt += 1
                if attempt < MAX_RETRIES:
                    time.sleep(delay)
                continue
            if not resp.ok:
                # Admin API error bodies carry the error message, not credentials; still
                # truncated so a huge HTML error page doesn't flood the notification.
                raise UserError(_("Salla API error %s on %s: %s") % (
                    resp.status_code, path, resp.text[:500]))
            try:
                return resp.json()
            except ValueError:
                return resp.text
        raise UserError(_("Salla request %s failed after %s attempts: %s") % (
            path, MAX_RETRIES, last_err))

    # ------------------------------------------------------------------ webhook
    def _pick_for_event(self, merchant, event):
        """Among the backends whose secret verified a webhook, the one it belongs to
        (rules in mapping.pick_backend)."""
        key = mapping.pick_backend([(b.id, b.store_id) for b in self], merchant, event)
        return self.browse(key) if key else self.browse()

    def _process_webhook(self, payload):
        """Handle one verified webhook. Returns a short status for the HTTP answer.
        F1 only handles the app lifecycle; order events are logged and ignored (F2)."""
        self.ensure_one()
        event = mapping.event_name(payload)
        if event == mapping.AUTHORIZE_EVENT:
            tokens = mapping.parse_authorize(payload)
            if not tokens:
                _logger.error("Salla backend %s: %s without a readable access token; "
                              "payload keys: %s", self.name, event, mapping.payload_keys(payload))
                return "authorize:unparsed"
            expires = tokens["expires_at"]
            if not expires:
                expires = fields.Datetime.now() + DEFAULT_TOKEN_LIFETIME
                _logger.warning("Salla backend %s: authorize gave no readable expiry; "
                                "assuming %s days.", self.name, DEFAULT_TOKEN_LIFETIME.days)
            # A missing refresh token / scope never blanks the stored one: losing the
            # refresh token means reinstalling the app.
            values = {"access_token": tokens["access_token"], "token_expires_at": expires}
            if tokens["refresh_token"]:
                values["refresh_token"] = tokens["refresh_token"]
            else:
                _logger.warning("Salla backend %s: authorize carried no refresh token.", self.name)
            if tokens["scope"]:
                values["token_scope"] = tokens["scope"]
            if tokens["store_id"] and not self.store_id:
                values["store_id"] = tokens["store_id"]
            self._write_token_row(values)
            _logger.info("Salla backend %s: authorized for store %s, token expires %s UTC",
                         self.name, tokens["store_id"] or self.store_id, expires)
            return "authorized"
        if event in mapping.REVOKE_EVENTS:
            self._write_token_row({"access_token": False, "refresh_token": False,
                                   "token_expires_at": False})
            _logger.warning("Salla backend %s: %s received, tokens cleared. The app has to "
                            "be reinstalled on store %s.", self.name, event, self.store_id)
            return "revoked"
        return "ignored:%s" % (event or "?")

    # ------------------------------------------------------------------ actions
    def _notify(self, message, warning=False, title=None):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "warning" if warning else "success",
                "title": title or _("Salla"),
                "message": message,
                "sticky": warning,
            },
        }

    def action_test_connection(self):
        self.ensure_one()
        res = self._request("GET", "/store/info")
        data = res.get("data") if isinstance(res, dict) else None
        data = data if isinstance(data, dict) else {}
        store = mapping.text(data.get("id"))
        name = mapping.text(data.get("name")) or "?"
        if self.store_id and store and store != self.store_id:
            return self._notify(_(
                "Connected, but the token belongs to store %s (%s) while this backend is "
                "bound to store %s.") % (store, name, self.store_id), warning=True)
        return self._notify(_("Connection OK: store %s (%s).") % (name, store or "?"))

    def _iter_products(self):
        """Yield every Salla product, paging /products. Stops on the last page, an empty
        page, a page that isn't the one asked for, or MAX_PAGES."""
        self.ensure_one()
        page = 1
        for _i in range(MAX_PAGES):
            res = self._request("GET", "/products", params={"page": page, "per_page": PER_PAGE})
            items = res.get("data") if isinstance(res, dict) else None
            if not isinstance(items, list) or not items:
                return
            pagination = res.get("pagination")
            served = mapping.current_page(pagination)
            if served is not None and served != page:
                # An API that ignores `page` would hand back page 1 forever.
                _logger.warning("Salla backend %s: asked for products page %s, got %s; "
                                "listing stopped.", self.name, page, served)
                return
            for product in items:
                if isinstance(product, dict):
                    yield product
            page = mapping.next_page(pagination)
            if not page:
                return
        _logger.warning("Salla backend %s: product listing stopped at the %s-page cap",
                        self.name, MAX_PAGES)

    def _product_skus(self, product):
        """SKUs of a product and its variants. When the list payload only declares
        options, read the variants from the product detail (field names unverified)."""
        skus = mapping.product_skus(product)
        if mapping.needs_variant_fetch(product) and product.get("id"):
            try:
                detail = self._request("GET", "/products/%s" % product["id"])
                detail = detail.get("data") if isinstance(detail, dict) else None
                skus += [s for s in mapping.product_skus(detail) if s not in skus]
            except UserError as e:
                _logger.warning("Salla product %s: variants not readable: %s", product.get("id"), e)
        return skus

    def action_check_products(self):
        """Reconcile Salla product/variant SKUs against product.product.default_code.
        Reports SKUs missing from Odoo and SKUs that only match an archived product."""
        self.ensure_one()
        # active_test=False so archived products are diagnosed as "archived", not "missing".
        Product = self.env["product.product"].with_context(active_test=False)
        rows, no_sku = [], []
        for product in self._iter_products():
            title = mapping.text(product.get("name"))[:40]
            skus = self._product_skus(product)
            if not skus:
                no_sku.append("%s (%s) — no SKU on Salla" % (product.get("id") or "?", title))
            rows += [(sku, title) for sku in skus]

        codes = list({sku for sku, _t in rows})
        # order="active desc" -> an active match wins over an archived duplicate
        found = {}
        for prod in Product.search([("default_code", "in", codes)], order="active desc") if codes else []:
            found.setdefault(prod.default_code, prod)
        missing = list(no_sku)
        for sku, title in rows:
            match = found.get(sku)
            if not match:
                missing.append("%s (%s) — not in Odoo" % (sku, title))
            elif not match.active:
                missing.append("%s (%s) — ARCHIVED in Odoo" % (sku, title))
        total = len(rows) + len(no_sku)
        if missing:
            _logger.warning("Salla SKU check: %s issues of %s: %s", len(missing), total, missing)
        msg = (_("%s of %s Salla SKUs need attention:\n%s") % (
            len(missing), total, "\n".join(missing[:20]) + ("\n…" if len(missing) > 20 else ""))
            if missing else _("All %s Salla SKUs match an active Odoo product.") % total)
        return self._notify(msg, warning=bool(missing), title=_("Salla Product Check"))
