"""Pure Trendyol->Odoo mapping helpers.

No Odoo imports on purpose so the non-trivial parsing logic (status filter,
epoch dates, line normalization) is unit-testable standalone:
    python trendyol_connector/tests/test_mapping.py
"""
from datetime import datetime

# Trendyol shipment-package statuses we treat as real sales worth importing.
# Excluded on purpose: Cancelled, Returned, UnDelivered, UnSupplied, Awaiting.
IMPORTABLE = {"Created", "Picking", "Invoiced", "Shipped", "AtCollectionPoint", "Delivered"}

# Trendyol status -> Odoo sale.order state. Phase 1 imports everything as draft;
# this map is the hook Phase 2/3 uses to auto-confirm/close. Kept here so it has a test.
STATE_MAP = {
    "Created": "draft",
    "Picking": "draft",
    "Invoiced": "sale",
    "Shipped": "sale",
    "AtCollectionPoint": "sale",
    "Delivered": "done",
    "Cancelled": "cancel",
}


def _canon(status):
    """The GET API says "AtCollectionPoint"; webhooks say "AT_COLLECTION_POINT".
    Canonical form: uppercase, no underscores."""
    return (status or "").replace("_", "").upper()


_IMPORTABLE_CANON = {_canon(s) for s in IMPORTABLE}
_STATE_MAP_CANON = {_canon(k): v for k, v in STATE_MAP.items()}


def should_import(status):
    return _canon(status) in _IMPORTABLE_CANON


def map_state(status):
    return _STATE_MAP_CANON.get(_canon(status), "draft")


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


def epoch_ms_to_dt(ms):
    """Trendyol dates are epoch milliseconds (UTC). Returns a naive UTC datetime
    (what Odoo Datetime fields store) or None."""
    if not ms:
        return None
    return datetime.utcfromtimestamp(ms / 1000.0)


def normalize_lines(pkg):
    """Flatten a shipment package's `lines` into {sku, quantity, price, name}.
    merchantSku is the seller SKU == Odoo product.product.default_code.
    Lines cancelled inside an otherwise-importable package are dropped."""
    out = []
    for line in pkg.get("lines") or []:
        if line.get("orderLineItemStatusName") == "Cancelled":
            continue
        gross = line.get("price", line.get("amount", 0.0)) or 0.0
        # Trendyol prices are VAT-inclusive; Odoo KSA sales tax (15%, id=20) is
        # price-EXcluded, so strip the line's vatRate to get the net unit price.
        vat = line.get("vatRate") or 0.0
        out.append({
            "sku": (line.get("merchantSku") or line.get("sku") or "").strip(),
            "quantity": line.get("quantity") or 1,
            "price": gross / (1 + vat / 100.0),
            "name": line.get("productName"),
        })
    return out
