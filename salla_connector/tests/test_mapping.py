"""Standalone self-check for the pure mapping logic (no Odoo needed).

Run:  python3 salla_connector/tests/test_mapping.py

All secrets/tokens below are obviously fake test values.
"""
import hashlib
import hmac
import inspect
import json
import math
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "models"))
import mapping  # noqa: E402

SECRET = "fake-webhook-secret-for-tests"
BODY = b'{"event":"order.created","merchant":1000000001,"data":{"id":42}}'
NOW = datetime(2026, 10, 15, 12, 0, 0)          # naive UTC, like Odoo stores it
NOW_TS = 1792065600.0                            # == NOW as epoch seconds


def _sign(body, secret=SECRET):
    if isinstance(body, str):
        body = body.encode("utf-8")
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


# --- verify_signature(raw_body, secret, signature) ---------------------------

def test_signature_valid():
    assert mapping.verify_signature(BODY, SECRET, _sign(BODY))


def test_signature_wrong_secret():
    assert not mapping.verify_signature(BODY, SECRET, _sign(BODY, "another-fake-secret"))


def test_signature_tampered_one_byte():
    tampered = BODY.replace(b'"id":42', b'"id":43')
    assert len(tampered) == len(BODY)
    assert not mapping.verify_signature(tampered, SECRET, _sign(BODY))
    # and one flipped hex char in the signature itself
    sig = _sign(BODY)
    flipped = sig[:-1] + ("0" if sig[-1] != "0" else "1")
    assert not mapping.verify_signature(BODY, SECRET, flipped)


def test_signature_missing_or_empty_header():
    assert not mapping.verify_signature(BODY, SECRET, None)
    assert not mapping.verify_signature(BODY, SECRET, "")
    assert not mapping.verify_signature(BODY, SECRET, "   ")
    assert not mapping.verify_signature(BODY, SECRET, "sha256=")


def test_signature_empty_secret():
    # An unconfigured backend must never accept anything, not even a body
    # "signed" with the empty key (which anyone can compute).
    assert not mapping.verify_signature(BODY, "", _sign(BODY, ""))
    assert not mapping.verify_signature(BODY, None, _sign(BODY, ""))


def test_signature_case_whitespace_prefix():
    sig = _sign(BODY)
    assert mapping.verify_signature(BODY, SECRET, sig.upper())
    assert mapping.verify_signature(BODY, SECRET, "  %s\n" % sig)
    assert mapping.verify_signature(BODY, SECRET, "sha256=" + sig)
    assert mapping.verify_signature(BODY, SECRET, sig.encode("ascii"))   # header as bytes


def test_signature_bytes_vs_str_body():
    assert mapping.verify_signature(BODY.decode("utf-8"), SECRET, _sign(BODY))
    # non-ASCII body: str must be hashed as UTF-8, same as the raw bytes
    body = '{"name":"منظف"}'
    assert mapping.verify_signature(body, SECRET, _sign(body.encode("utf-8")))
    assert mapping.verify_signature(body.encode("utf-8"), SECRET, _sign(body))


def test_signature_is_over_raw_bytes():
    """Same JSON document, different bytes -> must FAIL. Proves nobody parses
    and re-serializes the body before hashing."""
    sig = _sign(BODY)
    doc = json.loads(BODY)
    respaced = json.dumps(doc).encode("utf-8")                       # ", " and ": "
    reordered = json.dumps(dict(reversed(list(doc.items()))),
                           separators=(",", ":")).encode("utf-8")
    assert json.loads(respaced) == json.loads(reordered) == doc
    assert respaced != BODY and reordered != BODY
    assert not mapping.verify_signature(respaced, SECRET, sig)
    assert not mapping.verify_signature(reordered, SECRET, sig)
    assert not mapping.verify_signature(BODY + b"\n", SECRET, sig)
    # same document, \\u escape vs raw UTF-8 encoding
    escaped = json.dumps({"n": "م"}, ensure_ascii=True).encode("utf-8")
    raw_utf8 = json.dumps({"n": "م"}, ensure_ascii=False).encode("utf-8")
    assert json.loads(escaped) == json.loads(raw_utf8) and escaped != raw_utf8
    assert not mapping.verify_signature(raw_utf8, SECRET, _sign(escaped))


def test_signature_empty_body():
    # signed empty body is valid (controller answers 200), unsigned is not
    assert mapping.verify_signature(b"", SECRET, _sign(b""))
    assert mapping.verify_signature("", SECRET, _sign(b""))
    assert not mapping.verify_signature(b"", SECRET, None)
    assert not mapping.verify_signature(b"", SECRET, _sign(b"x"))
    assert not mapping.verify_signature(None, SECRET, _sign(b""))   # missing body


def test_signature_garbage_header():
    for bad in ("not-hex-at-all", _sign(BODY)[:-1], _sign(BODY) + "0",
                "sha256=" + "z" * 64, "م" * 64, "0" * 64, 12345, ["x"]):
        assert not mapping.verify_signature(BODY, SECRET, bad), bad


def test_signature_uses_compare_digest():
    """Timing-safe comparison: digests must not be compared with ==."""
    src = inspect.getsource(mapping.verify_signature)
    assert "compare_digest" in src
    assert "== sig" not in src and "sig ==" not in src and "== expected" not in src


# --- authorize / tokens ------------------------------------------------------

AUTHORIZE = {
    "event": "app.store.authorize",
    "merchant": 1000000001,
    "created_at": "2026-10-15 12:00:00",
    "data": {
        "access_token": "FAKE_ACCESS_TOKEN",
        "refresh_token": "FAKE_REFRESH_TOKEN",
        "expires": 1700000000,
        "scope": "settings.read offline_access",
        "token_type": "bearer",
    },
}


def test_parse_authorize_full():
    t = mapping.parse_authorize(AUTHORIZE, now=NOW)
    assert t["access_token"] == "FAKE_ACCESS_TOKEN"
    assert t["refresh_token"] == "FAKE_REFRESH_TOKEN"
    assert t["expires_at"] == datetime(2023, 11, 14, 22, 13, 20)   # epoch s, naive UTC
    assert t["scope"] == "settings.read offline_access"
    assert t["store_id"] == "1000000001"                             # str, not int


def test_parse_authorize_missing_refresh_token():
    payload = dict(AUTHORIZE, data=dict(AUTHORIZE["data"]))
    del payload["data"]["refresh_token"]
    t = mapping.parse_authorize(payload, now=NOW)
    assert t["access_token"] == "FAKE_ACCESS_TOKEN"
    assert t["refresh_token"] == ""          # never the string "None"
    payload["data"]["refresh_token"] = None
    assert mapping.parse_authorize(payload, now=NOW)["refresh_token"] == ""


def test_parse_authorize_missing_data():
    assert mapping.parse_authorize({"event": "app.store.authorize", "merchant": 1}) is None
    assert mapping.parse_authorize(dict(AUTHORIZE, data={})) is None
    assert mapping.parse_authorize(dict(AUTHORIZE, data=None)) is None
    no_access = dict(AUTHORIZE, data={"refresh_token": "FAKE_REFRESH_TOKEN"})
    assert mapping.parse_authorize(no_access) is None
    blank_access = dict(AUTHORIZE, data=dict(AUTHORIZE["data"], access_token="   "))
    assert mapping.parse_authorize(blank_access) is None


def test_parse_authorize_flat_and_nested_merchant():
    flat = {"event": "app.store.authorize", "merchant": {"id": 77},
            "access_token": "FAKE_ACCESS_TOKEN", "expires_in": 3600}
    t = mapping.parse_authorize(flat, now=NOW)
    assert t["access_token"] == "FAKE_ACCESS_TOKEN"
    assert t["store_id"] == "77"
    assert t["expires_at"] == NOW + timedelta(hours=1)
    # merchant only inside data
    inner = {"data": dict(AUTHORIZE["data"], merchant=55)}
    assert mapping.parse_authorize(inner, now=NOW)["store_id"] == "55"
    # no merchant anywhere -> "" (pick_backend then decides), never "None"
    t = mapping.parse_authorize({"data": dict(AUTHORIZE["data"])}, now=NOW)
    assert t["store_id"] == ""


def test_parse_authorize_garbage():
    for junk in (None, "junk", 42, [], [AUTHORIZE], {"data": "x"}, {"data": [1, 2]}, True):
        assert mapping.parse_authorize(junk) is None, junk


def test_expires_epoch_vs_lifetime():
    # epoch seconds
    assert mapping.expires_at(1700000000, NOW) == datetime(2023, 11, 14, 22, 13, 20)
    # epoch milliseconds
    assert mapping.expires_at(1700000000000, NOW) == datetime(2023, 11, 14, 22, 13, 20)
    # lifetime in seconds (expires_in): Salla's 14 days
    assert mapping.expires_at(1209600, NOW) == NOW + timedelta(days=14)
    assert mapping.expires_at("1209600", NOW) == NOW + timedelta(days=14)
    # expires wins over expires_in when both are present
    t = mapping.parse_tokens({"access_token": "FAKE_ACCESS_TOKEN",
                              "expires": 1700000000, "expires_in": 60}, NOW)
    assert t["expires_at"] == datetime(2023, 11, 14, 22, 13, 20)


def test_expires_iso_strings():
    want = datetime(2026, 10, 29, 12, 0, 0)
    assert mapping.expires_at("2026-10-29 12:00:00", NOW) == want      # naive = UTC
    assert mapping.expires_at("2026-10-29T12:00:00", NOW) == want
    assert mapping.expires_at("2026-10-29T12:00:00Z", NOW) == want
    assert mapping.expires_at("2026-10-29T12:00:00z", NOW) == want
    assert mapping.expires_at(" 2026-10-29 12:00:00 ", NOW) == want
    # +03:00 (KSA) -> converted to naive UTC, not just stripped
    assert mapping.expires_at("2026-10-29T15:00:00+03:00", NOW) == want
    assert mapping.expires_at("2026-10-29 15:00:00+03:00", NOW) == want
    assert mapping.expires_at("2026-10-29T06:00:00-06:00", NOW) == want  # Mexico, crosses no day
    assert mapping.expires_at("2026-10-30T02:00:00+14:00", NOW) == want  # crosses the day
    res = mapping.expires_at("2026-10-29T15:00:00+03:00", NOW)
    assert res.tzinfo is None                                           # Odoo Datetime: naive
    for junk in ("2026-13-45 12:00:00", "2026-10-29 25:00:00", "29/10/2026", "tomorrow", "Z"):
        assert mapping.expires_at(junk, NOW) is None, junk


def test_expires_magnitude_boundaries():
    # 10**9 - 1 is still a LIFETIME in seconds from now
    assert mapping.expires_at(10 ** 9 - 1, NOW) == NOW + timedelta(seconds=10 ** 9 - 1)
    # 10**9 is the first EPOCH second: 2001-09-09 01:46:40 UTC
    assert mapping.expires_at(10 ** 9, NOW) == datetime(2001, 9, 9, 1, 46, 40)
    # 10**12 is the first EPOCH millisecond: the same instant
    assert mapping.expires_at(10 ** 12, NOW) == datetime(2001, 9, 9, 1, 46, 40)
    assert mapping.expires_at(str(10 ** 12), NOW) == datetime(2001, 9, 9, 1, 46, 40)
    # just under 10**12 is epoch seconds in year ~33658: out of datetime range -> None, no crash
    assert mapping.expires_at(10 ** 12 - 1, NOW) is None


def test_expires_garbage_is_none():
    for junk in (None, True, False, 0, -5, "", "abc", {}, []):
        assert mapping.expires_at(junk, NOW) is None, junk


def test_expires_non_finite_or_huge_does_not_crash():
    """A garbage `expires` must yield None (-> treated as needs-refresh), never raise
    inside the webhook: an exception there loses the authorize event and its tokens."""
    for junk in ("nan", float("nan"), "inf", float("inf"), 10 ** 20):
        try:
            value = mapping.expires_at(junk, NOW)
        except Exception as exc:  # noqa: BLE001
            raise AssertionError("expires_at(%r) raised %s: %s"
                                 % (junk, type(exc).__name__, exc))
        assert value is None, (junk, value)


def test_token_needs_refresh_boundaries():
    margin = timedelta(days=3)
    exp = NOW + margin
    assert mapping.token_needs_refresh(exp, NOW, margin)                       # exactly at margin
    assert not mapping.token_needs_refresh(exp + timedelta(seconds=1), NOW, margin)
    assert mapping.token_needs_refresh(exp - timedelta(seconds=1), NOW, margin)
    assert mapping.token_needs_refresh(NOW - timedelta(days=1), NOW, margin)   # past
    assert mapping.token_needs_refresh(NOW, NOW, timedelta(0))                 # expires now
    assert mapping.token_needs_refresh(None, NOW, margin)                      # unknown
    assert mapping.token_needs_refresh(False, NOW, margin)                     # Odoo empty field
    assert not mapping.token_needs_refresh(NOW + timedelta(days=14), NOW, margin)


# --- backend routing / events ------------------------------------------------

def test_event_and_merchant():
    assert mapping.event_name({"event": " App.Store.Authorize "}) == mapping.AUTHORIZE_EVENT
    assert mapping.event_name({}) == ""
    assert mapping.event_name("junk") == ""
    assert mapping.merchant_id({"merchant": 0}) == "0"
    assert mapping.merchant_id({"merchant": None}) == ""
    assert mapping.merchant_id({"merchant": True}) == ""      # never "True"
    assert mapping.merchant_id([]) == ""


def test_pick_backend():
    AUTH, ORDER = mapping.AUTHORIZE_EVENT, "order.created"
    # (1) exact store match wins, for every event, over an unbound backend
    for ev in (AUTH, ORDER, "", "app.uninstalled", "app.store.revoke"):
        assert mapping.pick_backend([(1, ""), (2, "55")], "55", ev) == 2, ev
    # (3) only authorize may take the first unbound backend (first install)
    assert mapping.pick_backend([(1, "99"), (2, False), (3, "")], "55", AUTH) == 2
    assert mapping.pick_backend([(1, "99"), (2, False)], "55") is None          # no event
    assert mapping.pick_backend([(1, "99"), (2, False)], "55", ORDER) is None
    assert mapping.pick_backend([(1, "99"), (2, False)], "55", "  APP.STORE.AUTHORIZE ") == 2
    # unknown store with every backend bound -> None (never overwrite another store)
    for ev in (AUTH, ORDER, ""):
        assert mapping.pick_backend([(1, "99"), (2, "98")], "55", ev) is None, ev
    # (4) non-revoke event with no merchant -> the single backend, only if exactly one
    assert mapping.pick_backend([(1, "99")], "", ORDER) == 1
    assert mapping.pick_backend([(1, "99")], None) == 1
    assert mapping.pick_backend([(1, "99"), (2, "98")], "", ORDER) is None
    assert mapping.pick_backend([(1, "")], "", AUTH) == 1        # first install, no merchant
    # authorize never lands on a BOUND backend without an exact store match: a misread
    # merchant must not let the demo store overwrite prod's tokens
    assert mapping.pick_backend([(1, "99")], "", AUTH) is None
    assert mapping.pick_backend([(1, "99")], None, AUTH) is None
    assert mapping.pick_backend([(1, "99"), (2, "98")], "", AUTH) is None
    assert mapping.pick_backend([(1, "99")], "55", AUTH) is None
    assert mapping.pick_backend([(1, "99"), (2, "")], "", AUTH) == 2   # only the unbound one
    assert mapping.pick_backend([], "55", AUTH) is None
    assert mapping.pick_backend(None, "55", AUTH) is None


def test_pick_backend_revoke():
    """(2) An uninstall on the demo store must never wipe another backend's tokens."""
    for ev in sorted(mapping.REVOKE_EVENTS):
        # foreign store, an unbound backend available -> still None
        assert mapping.pick_backend([(1, "99"), (2, "")], "55", ev) is None, ev
        assert mapping.pick_backend([(2, "")], "55", ev) is None, ev
        # no merchant at all -> None, even with a single candidate
        assert mapping.pick_backend([(1, "99")], "", ev) is None, ev
        assert mapping.pick_backend([(1, "")], None, ev) is None, ev
        # exact match -> that one
        assert mapping.pick_backend([(1, "99"), (2, "55"), (3, "")], "55", ev) == 2, ev
        assert mapping.pick_backend([(1, "99")], 99, ev.upper()) == 1, ev   # int merchant, case


def test_is_allowed_salla_url():
    """Exact hosts only: api.salla.dev and accounts.salla.sa. Whatever host passes
    receives the client secret, the single-use refresh token and the Bearer token."""
    for ok in ("https://api.salla.dev/admin/v2", "https://accounts.salla.sa/oauth2/token",
               "https://API.Salla.Dev/admin/v2", "HTTPS://ACCOUNTS.SALLA.SA/oauth2/token",
               "https://api.salla.dev:443/admin/v2", "  https://api.salla.dev/admin/v2  ",
               "https://api.salla.dev./admin/v2",          # trailing dot = same FQDN
               "https://accounts.salla.sa./oauth2/token"):
        assert mapping.is_allowed_salla_url(ok), ok
    for bad in (
            # no wildcard any more, no bare domain
            "https://salla.dev/", "https://x.salla.dev/", "https://store.salla.dev/admin/v2",
            "https://salla.sa/", "https://x.accounts.salla.sa/", "https://evilsalla.dev/",
            # scheme / port
            "http://api.salla.dev/admin/v2", "http://accounts.salla.sa/oauth2/token",
            "ftp://api.salla.dev/", "https://api.salla.dev:8443/admin/v2",
            "https://api.salla.dev:80/", "https://api.salla.dev:abc/",
            # host confusion
            "https://salla.dev.evil.com/", "https://api.salla.dev.evil.com/",
            "https://accounts.salla.sa.evil.com/", "https://evil.com/.salla.dev",
            "https://evil.com/api.salla.dev", "https://evil.com/?h=api.salla.dev",
            "https://evil.com#api.salla.dev",
            "https://evil.com\\@accounts.salla.sa/oauth2/token",   # backslash + @
            "https://accounts.salla.sa\\@evil.com/oauth2/token",   # and its reverse
            "https://api.salla.dev\\evil.com/", "https://api.salla.dev%2eevil.com/",
            "https://\u0430pi.salla.dev/admin/v2",                  # Cyrillic a
            "https://api.s\u0430lla.dev/admin/v2",
            "https://accounts.salla.s\u0430/oauth2/token",
            "https://api\u3002salla\u3002dev/",                    # ideographic full stop
            # user-info
            "https://user:pw@api.salla.dev/", "https://user@accounts.salla.sa/",
            "https://api.salla.dev@evil.com/", "https://:@api.salla.dev/",
            # empty / garbage
            "//api.salla.dev/admin", "api.salla.dev/admin/v2", "https://", "https://[::1]/",
            "", "   ", None, 42, b"https://api.salla.dev", ["https://api.salla.dev"],
            "not a url at all"):
        assert not mapping.is_allowed_salla_url(bad), bad


# --- retry_delay(status, headers, attempt, now=None, cap=30) -----------------

def test_retry_delay_retry_after_numeric():
    assert mapping.retry_delay(429, {"Retry-After": "7"}, 0, now=NOW_TS) == 7.0
    assert mapping.retry_delay(429, {"retry-after": "7"}, 0, now=NOW_TS) == 7.0   # case
    assert mapping.retry_delay(429, {"Retry-After": "0"}, 0, now=NOW_TS) == 0.0


def test_retry_delay_cap():
    assert mapping.retry_delay(429, {"Retry-After": "3600"}, 0, now=NOW_TS) == 30.0
    assert mapping.retry_delay(429, {"Retry-After": "9" * 30}, 0, now=NOW_TS) == 30.0
    assert mapping.retry_delay(500, {}, 10, now=NOW_TS) == 30.0
    assert mapping.retry_delay(429, {"X-RateLimit-Reset": str(NOW_TS + 600)}, 0, now=NOW_TS) == 30.0


def test_retry_delay_http_date():
    hdr = {"Retry-After": "Thu, 15 Oct 2026 12:00:10 GMT"}
    assert mapping.retry_delay(429, hdr, 0, now=NOW_TS) == 10.0
    past = {"Retry-After": "Thu, 15 Oct 2026 11:00:00 GMT"}
    assert mapping.retry_delay(429, past, 0, now=NOW_TS) == 0.0          # never negative
    far = {"Retry-After": "Fri, 16 Oct 2026 12:00:00 GMT"}
    assert mapping.retry_delay(429, far, 0, now=NOW_TS) == 30.0


def test_retry_delay_rate_limit_reset():
    # epoch timestamp
    assert mapping.retry_delay(429, {"X-RateLimit-Reset": str(int(NOW_TS) + 12)}, 0, now=NOW_TS) == 12.0
    # bare seconds count
    assert mapping.retry_delay(429, {"X-RateLimit-Reset": "5"}, 0, now=NOW_TS) == 5.0
    # reset already passed
    assert mapping.retry_delay(429, {"X-RateLimit-Reset": str(int(NOW_TS) - 50)}, 0, now=NOW_TS) == 0.0
    # Retry-After takes precedence
    both = {"Retry-After": "3", "X-RateLimit-Reset": str(int(NOW_TS) + 20)}
    assert mapping.retry_delay(429, both, 0, now=NOW_TS) == 3.0


def test_retry_delay_missing_header():
    assert mapping.retry_delay(429, {}, 0, now=NOW_TS) == 1.0          # 2**0
    assert mapping.retry_delay(429, None, 2, now=NOW_TS) == 4.0
    assert mapping.retry_delay(None, None, 1, now=NOW_TS) == 2.0       # network error
    assert mapping.retry_delay(503, {}, 3, now=NOW_TS) == 8.0


def test_retry_delay_not_retryable():
    for status in (200, 400, 401, 403, 404, 422):
        assert mapping.retry_delay(status, {"Retry-After": "5"}, 0, now=NOW_TS) is None, status


def test_retry_delay_garbage_header():
    """Whatever the header says, the result is a finite float in [0, cap]: it goes
    straight into time.sleep(), which raises on NaN and blocks on huge values."""
    for value in ("soon", "-5", "1.5", "", "  ", "²", "nan", "inf", "Thu, 99 Foo"):
        for name in ("Retry-After", "X-RateLimit-Reset"):
            try:
                d = mapping.retry_delay(429, {name: value}, 1, now=NOW_TS)
            except Exception as exc:  # noqa: BLE001
                raise AssertionError("retry_delay(429, {%r: %r}) raised %s: %s"
                                     % (name, value, type(exc).__name__, exc))
            assert isinstance(d, float) and math.isfinite(d) and 0.0 <= d <= 30.0, \
                (name, value, d)


# --- next_page(pagination) ---------------------------------------------------

def _walk(pages):
    """Simulate the caller's loop against a fake server; returns pages fetched.
    Hard cap so a broken next_page fails the test instead of hanging it."""
    fetched, page = [], 1
    while page is not None:
        assert len(fetched) < 50, "pagination did not terminate"
        fetched.append(page)
        page = mapping.next_page(pages(page))
    return fetched


def test_next_page_basic():
    assert mapping.next_page({"currentPage": 1, "totalPages": 3}) == 2
    assert mapping.next_page({"current_page": "2", "total_pages": "3"}) == 3
    assert mapping.next_page({"currentPage": 3, "totalPages": 3}) is None     # last page
    assert mapping.next_page({"currentPage": 1, "totalPages": 1}) is None     # single page
    assert mapping.next_page({"currentPage": 5, "totalPages": 3}) is None     # past the end
    assert mapping.next_page({"currentPage": 1, "totalPages": 0}) is None     # empty result


def test_next_page_walk_terminates():
    assert _walk(lambda p: {"currentPage": p, "totalPages": 4}) == [1, 2, 3, 4]
    assert _walk(lambda p: {"currentPage": p, "totalPages": 1}) == [1]
    # links.next only, server stops sending it on page 3
    links = lambda p: {"currentPage": p, "links": {"next": "u"} if p < 3 else {}}  # noqa: E731
    assert _walk(links) == [1, 2, 3]
    # server keeps echoing page 1 with totalPages 1 -> stop, do not refetch forever
    assert _walk(lambda p: {"currentPage": 1, "totalPages": 1}) == [1]


def test_current_page():
    assert mapping.current_page({"currentPage": 3, "totalPages": 5}) == 3
    assert mapping.current_page({"current_page": "2"}) == 2
    assert mapping.current_page({"currentPage": "x", "current_page": 4}) == 4   # fallback key
    for junk in (None, {}, "junk", [], 3, {"totalPages": 5}, {"currentPage": None},
                 {"currentPage": "abc"}, {"currentPage": [1]}, {"currentPage": {}}):
        assert mapping.current_page(junk) is None, junk


def test_next_page_missing_or_garbage():
    for junk in (None, {}, "junk", [], 3, {"totalPages": 5}, {"currentPage": "x", "totalPages": 5},
                 {"currentPage": None, "links": {"next": "u"}},
                 {"currentPage": 1}, {"currentPage": 1, "links": {"next": ""}},
                 {"currentPage": 1, "links": "u"}):
        assert mapping.next_page(junk) is None, junk


# --- product_skus(product) ---------------------------------------------------

def test_product_skus_with_variants():
    prod = {"sku": "FP-TEST-00001",
            "skus": [{"sku": "FP-TEST-00002"}, {"sku": "FP-TEST-00003"}]}
    assert mapping.product_skus(prod) == ["FP-TEST-00001", "FP-TEST-00002", "FP-TEST-00003"]
    alt = {"sku": "", "variants": [{"sku": "FP-TEST-00004"}]}
    assert mapping.product_skus(alt) == ["FP-TEST-00004"]
    both = {"skus": [{"sku": "A"}], "variants": [{"sku": "B"}]}
    assert mapping.product_skus(both) == ["A", "B"]


def test_product_skus_dedup_and_whitespace():
    prod = {"sku": " FP-TEST-00001 ",
            "skus": [{"sku": "FP-TEST-00001"}, {"sku": "\tFP-TEST-00002\n"},
                     {"sku": "FP-TEST-00002"}]}
    assert mapping.product_skus(prod) == ["FP-TEST-00001", "FP-TEST-00002"]


def test_product_skus_empty_and_none():
    assert mapping.product_skus({"sku": None, "skus": [{"sku": ""}, {"sku": "  "}, {}]}) == []
    assert mapping.product_skus({"sku": "A", "skus": None}) == ["A"]
    assert mapping.product_skus({"sku": "A", "skus": ["junk", 3, None]}) == ["A"]
    assert mapping.product_skus({"sku": 12345}) == ["12345"]          # numeric SKU
    assert mapping.product_skus({"sku": True}) == []                  # never "True"
    for junk in (None, "junk", [], 3):
        assert mapping.product_skus(junk) == [], junk


def test_needs_variant_fetch():
    assert mapping.needs_variant_fetch({"options": [{"name": "size"}]})
    assert not mapping.needs_variant_fetch({"options": [{"name": "size"}], "skus": []})
    assert not mapping.needs_variant_fetch({"options": []})
    assert not mapping.needs_variant_fetch({"sku": "A"})
    assert not mapping.needs_variant_fetch(None)


# --- safe logging -------------------------------------------------------------

def test_redact_hides_tokens():
    out = mapping.redact(AUTHORIZE)
    assert out["data"]["access_token"] == "***"
    assert out["data"]["refresh_token"] == "***"
    assert out["data"]["scope"] == "settings.read offline_access"
    assert out["merchant"] == 1000000001
    assert "FAKE_ACCESS_TOKEN" not in json.dumps(out)
    assert "FAKE_REFRESH_TOKEN" not in json.dumps(out)
    nested = {"list": [{"Client_Secret": "FAKE_SECRET", "Authorization": "Bearer FAKE"}]}
    assert "FAKE" not in json.dumps(mapping.redact(nested))
    assert AUTHORIZE["data"]["access_token"] == "FAKE_ACCESS_TOKEN"   # input untouched


def test_redact_masks_pii():
    order = {
        "id": 900001, "status": "under_review", "total": {"amount": 230, "currency": "SAR"},
        "reference_id": 12345, "sku": "FP-TEST-00001", "quantity": 4,
        "customer": {"id": 77, "first_name": "Fake", "last_name": "Buyer",
                     "full_name": "Fake Buyer", "mobile": "500000000", "mobile_code": "+966",
                     "email": "fake.buyer@example.invalid", "phone": "0110000000",
                     "city": "FakeCity", "name": "Fake Buyer"},
        "shipping": {"address": {"street_number": "1", "street": "Fake St",
                                 "national_address": "ABCD1234", "postal_code": "00000",
                                 "location": "24.0,46.0", "latitude": 24.0, "longitude": 46.0,
                                 "district": "Fake District", "building_number": "9"},
                     "shipping_address": "Fake address line"},
        "items": [{"id": 1, "name": "Fake Product", "sku": "FP-TEST-00002", "quantity": 2,
                   "receiver": {"customer_email": "x@example.invalid", "zip": "00000"}}],
    }
    out = mapping.redact(order)
    dump = json.dumps(out, ensure_ascii=False)
    for leaked in ("Fake", "fake.buyer", "500000000", "0110000000", "ABCD1234",
                   "x@example.invalid", "24.0,46.0"):
        assert leaked not in dump, leaked
    c = out["customer"]
    for key in ("first_name", "last_name", "full_name", "mobile", "mobile_code", "email",
                "phone", "city", "name"):
        assert c[key] == "***", key
    assert out["shipping"]["address"] == "***"              # whole sub-dict masked by key
    assert out["shipping"]["shipping_address"] == "***"
    assert out["items"][0]["name"] == "***"                 # exact "name", inside a list
    assert out["items"][0]["receiver"] == {"customer_email": "***", "zip": "***"}
    # unrelated keys untouched, including inside nested dicts and lists
    assert out["id"] == 900001 and out["status"] == "under_review"
    assert out["total"] == {"amount": 230, "currency": "SAR"}
    assert out["reference_id"] == 12345 and out["sku"] == "FP-TEST-00001" and out["quantity"] == 4
    assert c["id"] == 77
    assert out["items"][0]["id"] == 1 and out["items"][0]["sku"] == "FP-TEST-00002"
    assert out["items"][0]["quantity"] == 2
    # "name"/"city"/"location" are EXACT matches only: these keys stay readable
    nested = mapping.redact({"store_name": "S", "city_id": 5, "location_id": 6, "status_name": "ok"})
    assert nested == {"store_name": "S", "city_id": 5, "location_id": 6, "status_name": "ok"}
    # list of dicts at the top level, scalars pass through
    assert mapping.redact([{"email": "e"}, {"id": 2}, 3, None]) == [{"email": "***"}, {"id": 2}, 3, None]
    assert mapping.redact("plain") == "plain"
    assert order["customer"]["email"] == "fake.buyer@example.invalid"   # input untouched


def test_payload_keys_has_no_values():
    keys = mapping.payload_keys(AUTHORIZE)
    assert "data.access_token" in keys and "merchant" in keys
    assert not any("FAKE" in k for k in keys)
    assert mapping.payload_keys({"items": [{"sku": "A"}]}) == ["items", "items[].sku"]
    assert mapping.payload_keys("junk") == []


if __name__ == "__main__":
    for fn in [test_signature_valid, test_signature_wrong_secret,
               test_signature_tampered_one_byte, test_signature_missing_or_empty_header,
               test_signature_empty_secret, test_signature_case_whitespace_prefix,
               test_signature_bytes_vs_str_body, test_signature_is_over_raw_bytes,
               test_signature_empty_body, test_signature_garbage_header,
               test_signature_uses_compare_digest,
               test_parse_authorize_full, test_parse_authorize_missing_refresh_token,
               test_parse_authorize_missing_data, test_parse_authorize_flat_and_nested_merchant,
               test_parse_authorize_garbage, test_expires_epoch_vs_lifetime,
               test_expires_iso_strings, test_expires_magnitude_boundaries,
               test_expires_garbage_is_none, test_expires_non_finite_or_huge_does_not_crash,
               test_token_needs_refresh_boundaries,
               test_event_and_merchant, test_pick_backend, test_pick_backend_revoke,
               test_is_allowed_salla_url,
               test_retry_delay_retry_after_numeric, test_retry_delay_cap,
               test_retry_delay_http_date, test_retry_delay_rate_limit_reset,
               test_retry_delay_missing_header, test_retry_delay_not_retryable,
               test_retry_delay_garbage_header,
               test_current_page, test_next_page_basic, test_next_page_walk_terminates,
               test_next_page_missing_or_garbage,
               test_product_skus_with_variants, test_product_skus_dedup_and_whitespace,
               test_product_skus_empty_and_none, test_needs_variant_fetch,
               test_redact_hides_tokens, test_redact_masks_pii,
               test_payload_keys_has_no_values]:
        fn()
        print(fn.__name__, "OK")
    print("all passed")
