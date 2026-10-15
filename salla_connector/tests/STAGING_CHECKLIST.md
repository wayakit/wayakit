# salla_connector F1: staging checklist (odoo.sh `mainTest` build)

Manual run by a human on the odoo.sh staging build. There is no local Odoo.
Run the standalone suite first: `python3 salla_connector/tests/test_mapping.py` must end in `all passed`.

Never paste real tokens, secrets or customer data into the ticket, this file or a chat.
Everything below uses shell placeholders; export them in your own terminal only.

```sh
export WEBHOOK_URL="https://<maintest-build-host>/sl/webhook"   # changes on EVERY rebuild, re-check it
export WEBHOOK_SECRET="<webhook secret of the Salla app, from the Partners Portal>"
export STORE_ID="<Salla Store ID shown on the backend after step 7>"
export UA="Mozilla/5.0 (X11; Linux x86_64) SallaStagingCheck"    # curl's own UA is blocked by Cloudflare on the prod zone
sig() { printf '%s' "$1" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | sed 's/^.* //'; }
post() {  # post '<body>' [signature]  -> prints the answer body + HTTP code
  curl -sS -w ' | HTTP %{http_code} in %{time_total}s\n' -A "$UA" -X POST "$WEBHOOK_URL" \
    -H 'Content-Type: application/json' ${2:+-H "X-Salla-Signature: $2"} --data-binary "$1"
}
```
Always `--data-binary` (plain `-d` strips newlines and changes the bytes you signed).

Odoo shell helpers (odoo.sh web shell -> `odoo-bin shell`). They print fingerprints, never token values:
```python
import hashlib, threading
from odoo import api, SUPERUSER_ID
from odoo.modules.registry import Registry
BID = 1          # <- the salla.backend id
reg = Registry(env.cr.dbname)
fp = lambda v: hashlib.sha256((v or "").encode()).hexdigest()[:8] if v else "EMPTY"
def current():   # committed DB state, read on a fresh cursor
    with reg.cursor() as cr:
        b = api.Environment(cr, SUPERUSER_ID, {})["salla.backend"].browse(BID)
        return b.access_token, b.refresh_token, b.token_expires_at
```

Reading the answers: **403 + HTML ("Attention Required") = Cloudflare**, the request never
reached Odoo. **401 / 400 / 405 / 200 / 500 with a short text body = Odoo** (405 = right path,
GET instead of POST). 404 = wrong path or the module is not installed on that build.

## A. Install / upgrade

1. The odoo.sh build of `mainTest` is green and `salla_connector` **installs** (fresh) and then **upgrades** (next build) with no errors in the build log. The install itself validates the form view that declares `store_id` and `client_id` twice (see step 29).
2. Settings > Technical > Scheduled Actions: **"Salla: Refresh Tokens"** exists (xmlid `salla_connector.ir_cron_salla_refresh_tokens`), active, every **1 day**, code `model.cron_refresh_tokens()`.
3. **Access rights.** Use a user who is a sale manager but **not** an admin (Settings > Administration):
   - In the form: **Salla Store ID**, **Client ID** and **Access Token Expires** are shown **read-only**, once each. **Base URL**, **Token URL**, Client Secret, Webhook Secret, access/refresh token and **Log Full Webhook Payloads** are **not shown**. **Refresh Token Now** is not shown.
   - The UI is not the guard, the server is. In the shell (rolls back, changes nothing):
     ```python
     from odoo.exceptions import AccessError, ValidationError
     mgr = env["res.users"].browse(UID)   # UID = the non-admin sale manager
     B = env["salla.backend"].with_user(mgr).browse(BID)
     for vals in ({"store_id": "1"}, {"client_id": "FAKE_CLIENT"},
                  {"token_expires_at": "2000-01-01 00:00:00"},
                  {"base_url": "https://evil.example/admin/v2"},
                  {"token_url": "https://evil.example/oauth2/token"},
                  {"log_payloads": True}):
         try:
             B.write(vals); print("NOT BLOCKED", vals)
         except AccessError as e:
             print("AccessError OK", list(vals))
     try:
         B.action_refresh_token(); print("NOT BLOCKED refresh")
     except AccessError:
         print("AccessError OK refresh")
     env.cr.rollback()
     ```
     Expected: every line `AccessError OK`. Any `NOT BLOCKED` is a bug.
   - As **admin**, a non-Salla URL is rejected by the constraint (shell, then rollback):
     ```python
     A = env["salla.backend"].browse(BID)
     for vals in ({"token_url": "https://evil.example/oauth2/token"},
                  {"base_url": "http://api.salla.dev/admin/v2"},
                  {"base_url": "https://api.salla.dev:8443/admin/v2"},
                  {"token_url": "https://user:pw@accounts.salla.sa/oauth2/token"}):
         try:
             A.write(vals); A.flush_recordset(); print("NOT BLOCKED", vals)
         except ValidationError:
             print("ValidationError OK", vals)
         env.cr.rollback()
     ```
     Same in the UI: editing Token URL to `https://evil.example/oauth2/token` and saving shows the red *must be an https URL on a Salla host*.
   - A plain salesman: can open the backend, cannot save anything.

## B. Configure the backend and authorize (Easy Mode)

4. Create a backend as admin (company KSA, id 1): Client ID, Client Secret and Webhook Secret of the **demo store** Private App. **Type the demo store's Salla Store ID by hand now, before installing the app** (Partners Portal > demo store). Only an `app.store.authorize` can bind an empty Store ID, and it takes the *first* unbound backend; typing it removes the guesswork. (Left empty, step 7 still binds it, which is the fallback, not the plan.) Base URL / Token URL keep their defaults. `Webhook URL` shows `web.base.url` + `/sl/webhook`; correct it to this build if `web.base.url` points elsewhere.
5. **Log Full Webhook Payloads** is **off** by default. Leave it off for now.
6. In the Partners Portal, set the app's webhook URL to `$WEBHOOK_URL` of **this** build. The build hostname changes on every rebuild; prefer the stable branch domain if there is one.
7. Install the app on the Salla **demo store**. Within seconds `app.store.authorize` must arrive and the backend must show: **Salla Store ID** filled, **Access Token Expires** ~14 days ahead (UTC), **Granted Scopes** filled (readonly), and (as admin) access/refresh token set (masked).
   - Log: `Salla webhook app.store.authorize (store …), payload keys: [...]` (keys only, **no token values**, confirm it) and `authorized for store …`.
   - Nothing arrived: look for the controller line in the log. No line at all = URL/Cloudflare; 401 = the Webhook Secret on the backend differs from the Portal's.
8. **Test Connection** -> green `Connection OK: store <name> (<id>)`. A warning `the token belongs to store X … bound to store Y` means the Store ID on the backend is wrong. Red 401 = token; 403 + HTML = Cloudflare.

## C. Check Product SKUs (demo store, 4 products)

Prepare in the demo store:
| Salla product | SKU | Odoo state |
|---|---|---|
| P1 | an existing `default_code`, e.g. `FP-TEST-00001` | active product |
| P2 | `FP-TEST-00002` | product **archived** in Odoo |
| P3 | `FP-TEST-99999` | does **not** exist in Odoo |
| P4 with 2 variants | variant SKUs `FP-TEST-00003` (exists) and `FP-TEST-99998` (does not) | |

9. **Check Product SKUs** -> warning `N of M Salla SKUs need attention`: `FP-TEST-00002 (…) — ARCHIVED in Odoo`, `FP-TEST-99999 (…) — not in Odoo`, `FP-TEST-99998 (…) — not in Odoo`. P1 and `FP-TEST-00003` must **not** be listed. If `FP-TEST-99998` is missing, variants are not read (log: `variants not readable`).
10. M (total) matches the SKUs actually in the demo store, and the log has the full list (`Salla SKU check: … issues of …`). A product with no SKU at all shows as `— no SKU on Salla`. No `stopped at the 200-page cap` warning and no `asked for products page X, got Y` warning.

## D. Webhook trust boundary (curl)

11. No signature -> **401** `unauthorized`:
    `post '{"event":"order.created","merchant":1,"data":{}}'`
12. Bad signature -> **401**:
    `post '{"event":"order.created","merchant":1,"data":{}}' 0000000000000000000000000000000000000000000000000000000000000000`
13. Signed **empty** body -> **200** `ok:0`, fast (well under Salla's ~30 s):
    `post '' "$(sig '')"`
14. Signed **broken JSON** -> **400** `bad json`; the log says `unparseable body (N bytes)` and does NOT print the body:
    `B='{"event":"order.created",'; post "$B" "$(sig "$B")"`
15. Signed JSON that is **not an object** -> **400**:
    `B='[1,2,3]'; post "$B" "$(sig "$B")"`
16. Signed **valid** event for this store -> **200** `ok:ignored:app.settings.updated`; log line is `payload keys: [...]` only (log_payloads off):
    `B='{"event":"app.settings.updated","merchant":'"$STORE_ID"',"created_at":"2026-10-15 10:00:00","data":{"customer":{"first_name":"Fake","email":"fake@example.invalid"},"status":"ok"}}'; post "$B" "$(sig "$B")"`
17. **log_payloads on** (admin), resend step 16 -> the log now shows the full body with `"first_name": "***"`, `"email": "***"` and `"status": "ok"` readable. Resend a signed authorize (step 21's body) -> still **keys only**, never the body. Turn log_payloads **off** again.
18. Event for a store **no backend is bound to** (every backend already bound) -> **200** `ok:0` + WARNING `matches no backend allowed to take it; ignored`:
    `B='{"event":"app.settings.updated","merchant":1999999999,"data":{}}'; post "$B" "$(sig "$B")"`
19. Signature is over the **raw bytes**: step 16-style signature on the same JSON re-spaced -> **401**:
    ```sh
    B='{"event":"app.settings.updated","merchant":'"$STORE_ID"',"data":{}}'; S=$(sig "$B")
    B2='{"event": "app.settings.updated", "merchant": '"$STORE_ID"', "data": {}}'
    post "$B2" "$S"
    ```
20. Forged `app.store.authorize` (fake tokens, signed with a **wrong** secret) -> **401**, tokens and expiry unchanged (`current()` fingerprints identical before/after):
    ```sh
    B='{"event":"app.store.authorize","merchant":'"$STORE_ID"',"data":{"access_token":"FAKE_ACCESS_TOKEN","refresh_token":"FAKE_REFRESH_TOKEN","expires":1209600}}'
    post "$B" "$(printf '%s' "$B" | openssl dgst -sha256 -hmac 'not-the-secret' | sed 's/^.* //')"
    ```

## E. Token refresh

21. **Authorize without refresh_token must NOT blank the stored one.** Note `fp()` of the refresh token from `current()`, then:
    ```sh
    B='{"event":"app.store.authorize","merchant":'"$STORE_ID"',"data":{"access_token":"FAKE_ACCESS_TOKEN_NO_REFRESH"}}'
    post "$B" "$(sig "$B")"      # -> 200 ok:authorized
    ```
    Expected: refresh token **still set, same fingerprint**; Granted Scopes and Store ID unchanged; Access Token Expires ~**14 days ahead** (assumed); log WARNINGs `authorize carried no refresh token` and `authorize gave no readable expiry; assuming 14 days`.
    Now the access token is fake with a future expiry, so the **proactive** refresh does NOT fire (expiry is 14 days out): **Test Connection** -> Salla answers 401 -> exactly **one** refresh with the stored refresh token -> retry -> **green**. Log: exactly one `access token refreshed` line. With the expiry 14 days out the proactive path cannot fire (margin is 1 day), so that line can only come from the 401 -> refresh -> retry path. (There is no dedicated log line for the 401 retry; if you see two refresh lines, or none, report it.) If it ends red with `no refresh token`, the stored one was blanked: bug.
    Also: signed authorize with `"data":{}` -> **200** `ok:authorize:unparsed`, nothing changed.
22. Forced expiry (**admin only**: the field is read-only for everyone else and a non-admin write raises AccessError, step 3): set **Access Token Expires** to a past date (or < 1 day ahead), save, click **Test Connection** -> green; expiry ~14 days ahead; refresh fingerprint **changed** (single-use); one log line `access token refreshed, expires … UTC`.
23. Cron: as admin, put the expiry inside 1 day again, Scheduled Actions > "Salla: Refresh Tokens" > **Run Manually** -> same result as 22. Run it again at once -> **no** second refresh line. **Refresh Token Now** (admin) asks for confirmation, then shows `Token valid until … UTC`.
24. **Two simultaneous refreshes** (the single-use refresh token must never be sent twice). With the helpers loaded:
    ```python
    def go(n, stale, out):
        with reg.cursor() as cr:
            b = api.Environment(cr, SUPERUSER_ID, {})["salla.backend"].browse(BID)
            try:
                r = b._refresh_token(stale_access_token=stale, force=True)
                out[n] = ("ok", fp(r["refresh_token"]), r["token_expires_at"])
            except Exception as e:
                out[n] = ("raised", type(e).__name__, str(e)[:200])

    def race(use_stale):
        acc, ref, exp = current()
        print("before: refresh", fp(ref), "expires", exp)
        out = {}
        ts = [threading.Thread(target=go, args=(i, acc if use_stale else None, out)) for i in range(2)]
        [t.start() for t in ts]; [t.join() for t in ts]
        print("threads:", out)
        acc, ref, exp = current()
        print("after:  refresh", fp(ref), "expires", exp)

    race(use_stale=True)    # A: what two "Refresh Token Now" clicks do
    race(use_stale=False)   # B: two blind forced refreshes
    ```
    Expected:
    - **A**: exactly **one** `access token refreshed` log line. The other thread hits the lock (NOWAIT, retries every 3 s), sees the access token already changed and returns the new tokens **without** calling Salla. Both threads `ok`, same fingerprint.
    - **B**: **two** refresh lines, at least ~3 s apart (serialized by the lock), the second using the refresh token the first one just saved. Both `ok`; final fingerprint differs from "before". Neither `raised`.
    - Afterwards **Test Connection** is green. A red 401 / "Reinstall the app" here means a spent refresh token was resent: **bug, report it** (and the app must be reinstalled on the demo store).
    - `raised UserError … kept the token refresh lock for over 18 s` is acceptable only if Salla's token endpoint was slower than ~15 s; note it.
25. A second 401 right after a refresh must show the red `Salla rejected the token even after a refresh (401). Reinstall the app on the store.`, not loop (only observable if Salla really rejects the fresh token; do not force it).

## F. Rate limiting (429)

26. Not forceable on the demo store without hammering it; do not try. On any real 429 in the log, check the wait honoured `Retry-After` (seconds or HTTP-date) or `X-RateLimit-Reset`, never exceeded 30 s, and after 3 attempts raised `Salla request … failed after 3 attempts: HTTP 429`. The arithmetic is covered by `test_retry_delay_*`.

## G. Odoo 17 assumptions nobody has executed yet

These four are API calls that only a real Odoo 17 can confirm. A wrong one shows up as a
`TypeError` / `AttributeError` / `ProgrammingError` in the log, usually as a 500 on the webhook.

27. **`cr.execute(..., log_exceptions=False)`** (token UPDATE, the lock SELECTs). Steps 7 and 22 already run it on success: no `unexpected keyword argument 'log_exceptions'` anywhere in the log. The point of the flag is checked in step 30: the failed query must **not** be logged with its parameters.
28. **`env.cache.set(record, field, value)`** (`_set_token_cache`): the caller's transaction must see the new tokens without re-reading its old snapshot. In the shell:
    ```python
    b = env["salla.backend"].browse(BID)
    before = fp(b.refresh_token)
    r = b._refresh_token(force=True)
    print("cache:", fp(b.refresh_token), "returned:", fp(r["refresh_token"]),
          "db:", fp(current()[1]), "before:", before)
    env.cr.rollback()
    print("db after rollback:", fp(current()[1]))
    ```
    Expected: cache == returned == db != before, and **db after rollback is still the new one** (the refresh committed on its own cursor; the rollback of the caller does not undo it, and nothing was written back from the cache).
29. **Duplicated `store_id` / `client_id` with `groups="!base.group_system"`** in the form: the install/upgrade passes view validation (step 1); as admin each field appears **once, editable**; as the non-admin sale manager each appears **once, read-only** (step 3). Showing twice, or not at all, is a bug.
30. **`SET LOCAL lock_timeout`** (an authorize/revoke write waits at most 12 s per attempt, 2 attempts on fresh cursors). Hold the row lock from the shell for **longer than 25 s**, then send a signed authorize with a fake token:
    ```python
    env.cr.execute("SELECT id FROM salla_backend WHERE id = %s FOR UPDATE", (BID,))
    # leave the shell open, do NOT commit; run the curl below now, roll back after it answers
    ```
    ```sh
    B='{"event":"app.store.authorize","merchant":'"$STORE_ID"',"data":{"access_token":"FAKE_ACCESS_TOKEN_LOCKTEST","refresh_token":"FAKE_REFRESH_TOKEN_LOCKTEST","expires":1209600}}'
    post "$B" "$(sig "$B")"
    ```
    Then `env.cr.rollback()` in the shell. Expected: one INFO `token row busy, retrying the write on a fresh cursor`, then the curl answers **500** `error` after **~24 s** (2 x 12 s; not instantly, not hanging until the rollback). The log has `processing failed` with a lock-timeout error, **`grep LOCKTEST` on the log finds nothing** (step 27: no query parameters logged), and `current()` fingerprints are unchanged. If the curl instead hangs until the rollback and then answers `ok:authorized`, `lock_timeout` was ignored: bug, and the stored refresh token is now the fake one; reinstall the app on the demo store.
    Variant: release the lock (`env.cr.rollback()`) **within ~10 s** of the curl -> **200** `ok:authorized` (the waiting write simply gets the lock, or retries once on a fresh cursor).
31. **Authorize colliding with a refresh** must be retried, **not** answered 500. Start a forced refresh and send a signed authorize while it is in flight (the refresh holds the row lock for the token POST):
    ```python
    out = {}
    t = threading.Thread(target=go, args=(0, None, out)); t.start()   # go() from step 24
    # within ~1 s, run the curl below in your terminal; then:
    t.join(); print(out, "refresh now:", fp(current()[1]))
    ```
    ```sh
    B='{"event":"app.store.authorize","merchant":'"$STORE_ID"',"data":{"access_token":"FAKE_ACCESS_TOKEN_COLLIDE","expires":1209600}}'
    post "$B" "$(sig "$B")"
    ```
    Expected: the curl answers **200** `ok:authorized` (possibly after waiting for the refresh), log may show `token row busy, retrying the write on a fresh cursor`, **no 500**. The refresh thread is `ok`. The refresh token is the one the refresh just obtained (the authorize carried none, so it did not blank it). The access token is now the fake one: **Test Connection** -> 401 -> one refresh -> **green** (same as step 21).

## H. Optional, destructive (last)

32. A signed `app.uninstalled` for `$STORE_ID` (or uninstalling the app from the demo store) -> **200** `ok:revoked`, access/refresh token and expiry cleared, WARNING `tokens cleared`. The app must then be reinstalled (back to step 7).
    Also: a signed `app.uninstalled` with **no** `merchant`, or with a merchant no backend is bound to -> **200** `ok:0`, nothing cleared.

## I. Before production (not F1 sign-off, but in this order)

33. Cloudflare Skip rule for `/sl/webhook` on `ksasystem.wayakit.com` exists **before** the prod URL is set in the app, **without** a method filter (see CLAUDE.md §11, Trendyol).
34. Create the prod backend and **type the prod Store ID by hand BEFORE installing the app on the real store and BEFORE pointing the app's webhook URL at prod**. The app's webhook secret is shared by the demo and real stores, and an `app.store.authorize` may bind the first **unbound** backend: if the prod backend is still unbound when the demo store re-authorizes, the demo tokens land on it. Once both backends are bound, an authorize can only reach the backend whose Store ID matches exactly (`test_pick_backend`).
35. Prod gets its own app installation and a fresh secret where possible; stage tokens never go to prod. An uninstall/revoke from the **demo** store must never touch a backend bound to another store: revoke only acts on an **exact** store match, never falls back to an unbound backend and never acts without a merchant (`pick_backend`, covered by `test_pick_backend_revoke`). Repeat step 32's "foreign merchant" curl against prod once both backends exist: prod tokens unchanged.
