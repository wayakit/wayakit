"""Pure Salla->Odoo mapping helpers.

No Odoo imports on purpose so the parsing / signature / token rules are testable
standalone (same pattern as trendyol_connector):
    python salla_connector/tests/test_mapping.py

Every Salla field name below is taken from docs.salla.dev and is UNVERIFIED against a
real payload. The Trendyol connector got three of those wrong (shipmentPackageId,
lineId, lineUnitPrice), so each reader is tolerant and the controller logs the
structure of the first real webhooks. Fix the names here, once, when a payload
disagrees.
"""
import hashlib
import hmac
import math
import re
from urllib.parse import urlsplit
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta, timezone

AUTHORIZE_EVENT = "app.store.authorize"
# Both spellings appear in Salla's docs depending on the page; either one means the
# tokens we hold are dead.
REVOKE_EVENTS = {"app.uninstalled", "app.store.revoke"}

# Keys whose VALUE must never reach a log line. Matched as a substring of the
# lowercased key so access_token / refresh_token / client_secret are all caught.
_SENSITIVE_KEY_PARTS = ("token", "secret", "password", "authorization", "api_key")
# Customer PII (confidential under Wayakit policy), masked the same way. Substrings
# catch customer_email / shipping_address / mobile_code. "name"/"city"/"location" are
# exact matches only: as substrings they would mask half the payload. That also masks
# a product's "name" — acceptable, the log is for checking field NAMES, not values.
_PII_KEY_PARTS = ("first_name", "last_name", "full_name", "email", "mobile", "phone",
                  "address", "street", "postal", "zip", "latitude", "longitude",
                  "national", "district", "block", "building")
_PII_KEYS = {"name", "city", "location"}

# OAuth credentials (client_secret, refresh token, Bearer) are only ever sent to these.
# A backend pointed anywhere else would hand them to whoever runs that host.
# Exact hosts, no wildcard: a *.salla.dev rule would trust any subdomain Salla (or a
# dangling DNS record) ever exposes.
_SALLA_HOSTS = {"api.salla.dev", "accounts.salla.sa"}
# Whole netloc, after lowercasing: plain host chars and an optional :443. Anything else
# (backslash, %, @, unicode) is how URL parsers disagree on what the host is.
_NETLOC_RE = re.compile(r"[a-z0-9.-]+(:443)?")

# Below this an "expires" number cannot be an epoch timestamp (10**9 s = 2001-09-09)
# and above it cannot be a lifetime (31 years). Salla's access token lives 14 days.
_EPOCH_SECONDS_MIN = 10 ** 9
_EPOCH_MS_MIN = 10 ** 12

_HEX = set("0123456789abcdef")


def _utcnow():
    """Naive UTC, the format Odoo Datetime fields store."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def text(value):
    """str(value).strip(), but "" for None/bool/containers instead of "None"/"True"
    — the Trendyol "None" package id collapsed every order onto one dedup key."""
    if value is None or isinstance(value, (bool, dict, list, tuple, set)):
        return ""
    return str(value).strip()


# ------------------------------------------------------------------ webhook trust
def verify_signature(raw_body, secret, signature):
    """True when `signature` is the hex HMAC-SHA256 of `raw_body` keyed with `secret`.

    Salla signs the RAW request body, so this must run on the bytes as received,
    never on re-serialized JSON. Tolerant to str/bytes inputs, surrounding whitespace,
    upper-case hex and a "sha256=" prefix; constant-time compare.

    An EMPTY body (b"") is still verified — the HMAC of an empty body is as
    unforgeable as any other, and the controller answers it 200 "ok:0". A missing
    body (None), secret or signature is always False.
    """
    if raw_body is None or not secret or not signature:
        return False
    try:
        if isinstance(raw_body, str):
            raw_body = raw_body.encode("utf-8")
        if isinstance(secret, str):
            secret = secret.encode("utf-8")
        if isinstance(signature, bytes):
            signature = signature.decode("ascii")
    except (UnicodeError, AttributeError):
        return False
    if not isinstance(raw_body, bytes) or not isinstance(secret, bytes) \
            or not isinstance(signature, str):
        return False
    sig = signature.strip().lower()
    if sig.startswith("sha256="):
        sig = sig[len("sha256="):].strip()
    # compare_digest raises TypeError on non-ASCII str; a non-hex header is just wrong.
    if not sig or not set(sig) <= _HEX:
        return False
    expected = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def event_name(payload):
    """Lowercased `event` of a webhook payload, "" when absent."""
    if not isinstance(payload, dict):
        return ""
    return text(payload.get("event")).lower()


def merchant_id(payload):
    """The Salla store (merchant) id a webhook belongs to, as a string, "" if absent.

    Docs show `merchant` as a bare number; accept {"id": ...} too, and fall back to
    data.merchant in case the envelope differs."""
    if not isinstance(payload, dict):
        return ""
    for holder in (payload, payload.get("data") if isinstance(payload.get("data"), dict) else {}):
        value = holder.get("merchant")
        if isinstance(value, dict):
            value = value.get("id")
        found = text(value)
        if found:
            return found
    return ""


def pick_backend(candidates, merchant, event=""):
    """Choose which backend a signed webhook belongs to, or None.

    `candidates` = [(key, store_id), ...] for every active backend whose secret
    verified the signature. Several can match: the webhook secret belongs to the Salla
    APP, so the demo store and the real store share it.

    1. The backend bound to that exact store wins, for every event.
    2. Revoke/uninstall events stop there — never a fallback, and never without a
       merchant: an uninstall on the demo store must not wipe the real store's tokens.
    3. `app.store.authorize` may bind a backend not bound to any store yet (first
       install; the first such candidate wins) — and stops there. It never lands on an
       already-bound backend without an exact match: if merchant_id() misreads the real
       payload, the demo store's authorize must not overwrite prod's tokens.
    4. Any other event with NO merchant in the payload goes to the single matching
       backend if there is exactly one.
    A store we do not know never reaches another store's backend.
    """
    merchant = text(merchant)
    event = text(event).lower()
    candidates = list(candidates or [])
    if merchant:
        for key, store in candidates:
            if text(store) == merchant:
                return key
    if event in REVOKE_EVENTS:
        return None
    if event == AUTHORIZE_EVENT:
        for key, store in candidates:
            if not text(store):
                return key
        return None
    if not merchant and len(candidates) == 1:
        return candidates[0][0]
    return None


def is_allowed_salla_url(url):
    """True only for an https URL on exactly api.salla.dev or accounts.salla.sa,
    default port, no user-info, plain host characters. Guards base_url/token_url: whatever host is there
    receives the client secret, the single-use refresh token and the Bearer token."""
    if not isinstance(url, str) or not url.strip():
        return False
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        return False
    if parts.scheme.lower() != "https" or parts.username or parts.password:
        return False
    if port not in (None, 443):
        return False
    if not _NETLOC_RE.fullmatch(parts.netloc.lower()):
        return False
    host = (parts.hostname or "").lower().rstrip(".")
    return host in _SALLA_HOSTS


# ------------------------------------------------------------------ OAuth tokens
def expires_at(value, now=None):
    """Turn an OAuth "expires" number into a naive UTC datetime, or None.

    Salla's authorize webhook documents `expires` as an epoch timestamp, while the
    standard token endpoint answers `expires_in` = seconds from now. Rather than trust
    either name, decide by magnitude: >= 10**12 epoch ms, >= 10**9 epoch seconds,
    anything smaller positive = seconds from `now`. A non-numeric string is read as an
    ISO date ("2026-10-29 12:00:00", optional "T" and "Z"/offset; naive = UTC).
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _parse_iso(value)
    # float("nan") / "inf" parse fine and then blow up in datetime: junk -> None,
    # because a webhook must never 500 on an odd expiry value.
    if not math.isfinite(number) or number <= 0:
        return None
    if number >= _EPOCH_MS_MIN:
        number /= 1000.0
    try:
        if number >= _EPOCH_SECONDS_MIN:
            return datetime.fromtimestamp(number, timezone.utc).replace(tzinfo=None)
        return (now or _utcnow()) + timedelta(seconds=number)
    except (OverflowError, ValueError, OSError):
        return None


def _parse_iso(value):
    """ "2026-10-29 12:00:00" / "2026-10-29T12:00:00Z" / "...+03:00" -> naive UTC.
    A naive string is taken as UTC. Anything unparseable -> None."""
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw[-1:] in ("Z", "z"):
        raw = raw[:-1] + "+00:00"   # fromisoformat only learned "Z" in Python 3.11
    try:
        when = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if when.tzinfo is not None:
        when = when.astimezone(timezone.utc).replace(tzinfo=None)
    return when


def parse_tokens(data, now=None):
    """{access_token, refresh_token, expires_at, scope} from a token-bearing dict
    (authorize webhook `data` or the token endpoint response), or None without an
    access token."""
    if not isinstance(data, dict):
        return None
    access = text(data.get("access_token"))
    if not access:
        return None
    raw_exp = data.get("expires")
    if raw_exp is None:
        raw_exp = data.get("expires_in")
    return {
        "access_token": access,
        "refresh_token": text(data.get("refresh_token")),
        "expires_at": expires_at(raw_exp, now),
        "scope": text(data.get("scope")),
    }


def parse_authorize(payload, now=None):
    """Parse an `app.store.authorize` webhook (OAuth Easy Mode).

    Documented shape (unverified):
        {"event": "app.store.authorize", "merchant": 1234, "created_at": "...",
         "data": {"access_token", "refresh_token", "expires", "scope", "token_type"}}
    Tokens are read from `data`, or from the top level if Salla ever flattens it.
    Returns parse_tokens(...) + "store_id", or None when no access token is found.
    """
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    tokens = parse_tokens(data if isinstance(data, dict) else payload, now)
    if tokens is None and isinstance(data, dict):
        tokens = parse_tokens(payload, now)
    if tokens is None:
        return None
    tokens["store_id"] = merchant_id(payload)
    return tokens


def token_needs_refresh(expires, now, margin):
    """True when the access token expires within `margin` of `now`.
    An unknown expiry counts as "needs refresh": guessing it is still valid is how a
    refresh token silently lapses after its one month."""
    if not expires:
        return True
    return expires - margin <= now


# ------------------------------------------------------------------ HTTP helpers
def _header(headers, name):
    """Case-insensitive header lookup that also works on a plain dict."""
    if not headers:
        return None
    if name in headers:
        return headers[name]
    lname = name.lower()
    for key, value in headers.items():
        if str(key).lower() == lname:
            return value
    return None


def retry_delay(status, headers, attempt, now=None, cap=30):
    """Seconds to sleep before retrying, or None when the response must not be retried.

    - status None (network error) or >= 500 -> exponential backoff 2**attempt.
    - 429 -> Retry-After (seconds, or an HTTP-date); else X-RateLimit-Reset, which Salla
      documents as an epoch timestamp (accept a bare seconds count too, by magnitude);
      else exponential backoff. Always capped at `cap` and never negative.
    - anything else -> None.
    `now` = epoch seconds, injectable for tests.
    """
    backoff = float(min(2 ** attempt, cap))
    if status is None or status >= 500:
        return backoff
    if status != 429:
        return None
    if now is None:
        now = datetime.now(timezone.utc).timestamp()
    retry_after = text(_header(headers, "Retry-After"))
    # isascii(): str.isdigit() also accepts "²" and other Unicode digits int() rejects.
    if retry_after.isascii() and retry_after.isdigit():
        return float(min(int(retry_after), cap))
    if retry_after:
        # RFC 9110 also allows an HTTP-date here; a garbage value falls through.
        try:
            when = parsedate_to_datetime(retry_after)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            return float(min(max(when.timestamp() - now, 0.0), cap))
        except (TypeError, ValueError, IndexError, OverflowError, AttributeError):
            pass
    reset = text(_header(headers, "X-RateLimit-Reset"))
    try:
        reset = float(reset)
    except ValueError:
        return backoff
    if not math.isfinite(reset):   # "nan"/"inf" parse, then time.sleep() chokes on them
        return backoff
    if reset >= _EPOCH_SECONDS_MIN:
        reset -= now
    return float(min(max(reset, 0.0), cap))


def current_page(pagination):
    """The page number a Salla `pagination` block says it is, or None."""
    if not isinstance(pagination, dict):
        return None
    for key in ("currentPage", "current_page"):
        try:
            return int(pagination.get(key))
        except (TypeError, ValueError):
            continue
    return None


def next_page(pagination):
    """Next page number from a Salla `pagination` block, or None on the last page.

    Documented keys are camelCase (currentPage/totalPages); snake_case accepted too.
    When totalPages is missing, a `links.next` still means there is one more page.
    Callers keep their own hard page cap: a paginator that never says "last" must not
    loop forever."""
    if not isinstance(pagination, dict):
        return None

    def _int(*keys):
        for key in keys:
            try:
                return int(pagination.get(key))
            except (TypeError, ValueError):
                continue
        return None

    current = _int("currentPage", "current_page")
    total = _int("totalPages", "total_pages")
    if current is None:
        return None
    if total is not None:
        return current + 1 if current < total else None
    links = pagination.get("links")
    if isinstance(links, dict) and links.get("next"):
        return current + 1
    return None


# ------------------------------------------------------------------ products
def product_skus(product):
    """Every SKU a Salla product carries: its own `sku` plus each variant's.

    Variants are expected under `skus` (product detail) and accepted under `variants`.
    Stripped, empties dropped, de-duplicated preserving order."""
    if not isinstance(product, dict):
        return []
    codes = [product.get("sku")]
    for key in ("skus", "variants"):
        for variant in product.get(key) or []:
            if isinstance(variant, dict):
                codes.append(variant.get("sku"))
    out = []
    for code in codes:
        code = text(code)
        if code and code not in out:
            out.append(code)
    return out


def needs_variant_fetch(product):
    """True when the product declares options but the list payload carried no variant
    list, so the variant SKUs have to be read from the product detail."""
    if not isinstance(product, dict) or not product.get("options"):
        return False
    return not any(isinstance(product.get(key), list) for key in ("skus", "variants"))


# ------------------------------------------------------------------ safe logging
def _sensitive(key):
    key = str(key).lower()
    return (key in _PII_KEYS
            or any(part in key for part in _SENSITIVE_KEY_PARTS)
            or any(part in key for part in _PII_KEY_PARTS))


def redact(payload):
    """Deep copy of `payload` with every credential AND customer-PII key's value
    replaced by "***" (keys kept, so the structure stays readable). For logging only."""
    if isinstance(payload, dict):
        return {k: ("***" if _sensitive(k) else redact(v)) for k, v in payload.items()}
    if isinstance(payload, list):
        return [redact(v) for v in payload]
    return payload


def payload_keys(payload, prefix="", depth=4):
    """Sorted dotted key paths of a payload — its STRUCTURE, no values at all.
    Used to log the authorize webhook, whose values are the tokens. Lists show as
    "key[]" with the keys of their first dict element."""
    out = set()
    if depth <= 0:
        return []
    if isinstance(payload, dict):
        for key, value in payload.items():
            path = "%s%s" % (prefix, key)
            out.add(path)
            out.update(payload_keys(value, path + ".", depth - 1))
    elif isinstance(payload, list):
        first = next((v for v in payload if isinstance(v, dict)), None)
        if first is not None:
            base = prefix[:-1] + "[]." if prefix.endswith(".") else prefix
            out.update(payload_keys(first, base, depth - 1))
    return sorted(out)
