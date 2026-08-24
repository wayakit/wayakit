"""Pure Trendyol->Odoo mapping helpers.

No Odoo imports on purpose so the non-trivial parsing logic (status filter,
epoch dates, line normalization) is unit-testable standalone:
    python trendyol_connector/tests/test_mapping.py
"""
from datetime import datetime

# Trendyol shipment-package statuses we treat as real sales worth importing.
# Excluded on purpose: Cancelled, Returned, UnDelivered, UnSupplied, Awaiting.
IMPORTABLE = {"Created", "Picking", "Invoiced", "Shipped", "AtCollectionPoint", "Delivered"}

# Trendyol status -> Odoo sale.order state. Phase 2 uses it to auto-confirm.
# NOTE: "done" is NOT a valid sale.order state in Odoo 17 — SALE_ORDER_STATE is only
# draft/sent/sale/cancel and locking moved to the `locked` boolean. Delivered therefore
# maps to "sale"; see LOCK_STATUSES for the locking part.
STATE_MAP = {
    "Created": "draft",
    "Picking": "draft",
    "Invoiced": "sale",
    "Shipped": "sale",
    "AtCollectionPoint": "sale",
    "Delivered": "sale",
    "Cancelled": "cancel",
}

# Statuses after which the order should be locked (Odoo 17 replacement for state "done").
LOCK_STATUSES = {"Delivered"}

def _canon(status):
    """The GET API says "AtCollectionPoint"; webhooks say "AT_COLLECTION_POINT".
    Canonical form: uppercase, no underscores."""
    return (status or "").replace("_", "").upper()


_IMPORTABLE_CANON = {_canon(s) for s in IMPORTABLE}
_STATE_MAP_CANON = {_canon(k): v for k, v in STATE_MAP.items()}
_LOCK_CANON = {_canon(s) for s in LOCK_STATUSES}


def should_import(status):
    return _canon(status) in _IMPORTABLE_CANON


def map_state(status):
    return _STATE_MAP_CANON.get(_canon(status), "draft")


def should_lock(status):
    return _canon(status) in _LOCK_CANON


def extract_packages(payload):
    """Normalize a webhook payload into a list of package dicts. Trendyol doesn't
    document the webhook body shape, so accept the likely forms: a single package
    object, a {"content": [...]} page (same as getShipmentPackages), or a bare list."""
    if isinstance(payload, list):
        return [p for p in payload if isinstance(p, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("content"), list):
            return [p for p in payload["content"] if isinstance(p, dict)]
        if payload.get("id") or payload.get("shipmentPackageId") or payload.get("lines"):
            return [payload]
    return []


def package_id(pkg):
    """The shipment package's unique id, used as the anti-dup key.

    The orders endpoint returns it as `shipmentPackageId` — there is NO top-level `id`
    on the real payload (the only `id`s are inside shipmentAddress/invoiceAddress).
    Webhooks and the docs use `id`. Accept both; return "" (never the string "None")
    when neither is there, because "None" collapses every order onto one dedup key and
    the unique constraint then swallows every order after the first."""
    return str(pkg.get("id") or pkg.get("shipmentPackageId") or "").strip()


def epoch_ms_to_dt(ms):
    """Trendyol dates are epoch milliseconds (UTC). Returns a naive UTC datetime
    (what Odoo Datetime fields store) or None."""
    if not ms:
        return None
    return datetime.utcfromtimestamp(ms / 1000.0)


def buyer(pkg):
    """Extract the individual buyer from a shipment package.

    Everything here is optional: the MENA payload is expected to carry the name and
    little else (the address travels on Trendyol's own shipping label, not the API), so
    each field falls back until it runs out and the caller decides what to do with "".

    Same trap as package_id/lineId: the field names below are the documented ones plus
    the ones seen on real payloads. Log a full production package before trusting them.

    `ref` is the dedup key (Trendyol's customer id). When Trendyol masks it, the caller
    falls back to matching on the name.
    """
    addr = pkg.get("shipmentAddress") or pkg.get("invoiceAddress") or {}
    name = (
        " ".join(filter(None, [pkg.get("customerFirstName"), pkg.get("customerLastName")]))
        or addr.get("fullName")
        or " ".join(filter(None, [addr.get("firstName"), addr.get("lastName")]))
    )
    return {
        "ref": str(pkg.get("customerId") or "").strip(),
        "name": " ".join((name or "").split()),   # collapse the double spaces a missing half leaves
        "street": addr.get("address1") or addr.get("fullAddress") or "",
        "street2": addr.get("address2") or "",
        "city": addr.get("city") or "",
        "zip": str(addr.get("postalCode") or ""),
        "phone": addr.get("phone") or "",
        "country_code": (addr.get("countryCode") or "").upper(),
    }


def normalize_lines(pkg):
    """Flatten a shipment package's `lines` into {sku, quantity, price, name}.
    Wayakit stores its SKU in Trendyol's "Model code" (productMainId), but order
    lines from the live API only ever carry stockCode/barcode (no productMainId,
    no merchantSku) — try productMainId first, then stockCode/barcode/merchantSku/
    sku as fallbacks. Lines cancelled inside an otherwise-importable package are
    dropped."""
    out = []
    for line in pkg.get("lines") or []:
        if line.get("orderLineItemStatusName") == "Cancelled":
            continue
        # Live API sends the VAT-inclusive unit price as lineUnitPrice (price/amount
        # kept as fallbacks — not seen on real payloads, only used by older tests).
        gross = line.get("lineUnitPrice", line.get("price", line.get("amount", 0.0))) or 0.0
        # Trendyol prices are VAT-inclusive; Odoo KSA sales tax (15%, id=20) is
        # price-EXcluded, so strip the line's vatRate to get the net unit price.
        vat = line.get("vatRate") or 0.0
        out.append({
            "sku": str(line.get("productMainId") or line.get("stockCode")
                       or line.get("barcode") or line.get("merchantSku")
                       or line.get("sku") or "").strip(),
            "quantity": line.get("quantity") or 1,
            "price": gross / (1 + vat / 100.0),
            "name": line.get("productName"),
            # Trendyol's own line id — required to push a per-line package status
            # (PUT shipment-packages expects lines[].lineId). Kept on the Odoo line.
            # The live orders payload names it `lineId`, NOT `id` (same trap as
            # shipmentPackageId in package_id): reading `id` gave an empty list and
            # the status push 404'd. `id` kept as the doc/webhook spelling.
            "line_id": str(line.get("lineId") or line.get("id") or "").strip(),
        })
    return out
