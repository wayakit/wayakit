"""Standalone self-check for the pure mapping logic (no Odoo needed).

Run:  python trendyol_connector/tests/test_mapping.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "models"))
import mapping  # noqa: E402


def test_should_import():
    assert mapping.should_import("Created")
    assert mapping.should_import("Delivered")
    assert not mapping.should_import("Cancelled")
    assert not mapping.should_import(None)
    # webhook enum spelling (UPPER_SNAKE) must be accepted too
    assert mapping.should_import("CREATED")
    assert mapping.should_import("AT_COLLECTION_POINT")
    assert not mapping.should_import("CANCELLED")


def test_map_state():
    assert mapping.map_state("Created") == "draft"
    assert mapping.map_state("Delivered") == "done"
    assert mapping.map_state("Whatever") == "draft"  # safe default
    assert mapping.map_state("CANCELLED") == "cancel"  # webhook spelling


def test_extract_packages():
    pkg = {"id": 1, "lines": []}
    assert mapping.extract_packages(pkg) == [pkg]                      # single package
    assert mapping.extract_packages({"content": [pkg, pkg]}) == [pkg, pkg]  # page shape
    assert mapping.extract_packages([pkg]) == [pkg]                    # bare list
    assert mapping.extract_packages({"foo": "bar"}) == []              # unknown -> ignored
    assert mapping.extract_packages("junk") == []


def test_epoch_ms_to_dt():
    dt = mapping.epoch_ms_to_dt(1700000000000)
    assert dt is not None and dt.year == 2023 and dt.month == 11
    assert mapping.epoch_ms_to_dt(0) is None
    assert mapping.epoch_ms_to_dt(None) is None


def test_normalize_lines():
    pkg = {"lines": [
        {"merchantSku": " FP-PET-01500 ", "quantity": 2, "price": 45.0, "productName": "Pet Kit"},
        {"sku": "RM-CHE-00008", "amount": 10.0},  # no price -> falls back to amount; no qty -> 1
        {"merchantSku": "FP-HOM-02900", "quantity": 1, "price": 9.0,
         "orderLineItemStatusName": "Cancelled"},  # dropped
    ]}
    lines = mapping.normalize_lines(pkg)
    assert len(lines) == 2  # cancelled line filtered out
    assert lines[0]["sku"] == "FP-PET-01500"  # trimmed
    assert lines[0]["quantity"] == 2 and lines[0]["price"] == 45.0  # no vatRate -> gross kept
    assert lines[1]["sku"] == "RM-CHE-00008"
    assert lines[1]["quantity"] == 1 and lines[1]["price"] == 10.0
    assert mapping.normalize_lines({}) == []


def test_sku_from_model_code():
    # Wayakit stores the SKU in Trendyol's "Model code" (productMainId); when
    # merchantSku/sku are absent it must be used as the match key.
    pkg = {"lines": [{"productMainId": "FP-PET-01500", "quantity": 1, "price": 50.0}]}
    assert mapping.normalize_lines(pkg)[0]["sku"] == "FP-PET-01500"


def test_vat_stripped():
    # Trendyol sends VAT-inclusive prices; Odoo adds 15% back -> net must be gross/1.15
    pkg = {"lines": [{"merchantSku": "FP-DIS-00001", "quantity": 1, "price": 115.0, "vatRate": 15}]}
    line = mapping.normalize_lines(pkg)[0]
    assert abs(line["price"] - 100.0) < 1e-9


if __name__ == "__main__":
    for fn in [test_should_import, test_map_state, test_epoch_ms_to_dt,
               test_normalize_lines, test_sku_from_model_code, test_vat_stripped,
               test_extract_packages]:
        fn()
        print(fn.__name__, "OK")
    print("all passed")
