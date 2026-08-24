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
    assert mapping.map_state("Whatever") == "draft"  # safe default
    assert mapping.map_state("CANCELLED") == "cancel"  # webhook spelling
    # Odoo 17 removed the "done" state from sale.order (draft/sent/sale/cancel only);
    # writing it would raise. Delivered confirms the order and locks it instead.
    assert "done" not in mapping.STATE_MAP.values()
    assert mapping.map_state("Delivered") == "sale"


def test_should_lock():
    assert mapping.should_lock("Delivered")
    assert mapping.should_lock("DELIVERED")   # webhook spelling
    assert not mapping.should_lock("Shipped")
    assert not mapping.should_lock(None)


def test_extract_packages():
    pkg = {"id": 1, "lines": []}
    assert mapping.extract_packages(pkg) == [pkg]                      # single package
    assert mapping.extract_packages({"content": [pkg, pkg]}) == [pkg, pkg]  # page shape
    assert mapping.extract_packages([pkg]) == [pkg]                    # bare list
    assert mapping.extract_packages({"foo": "bar"}) == []              # unknown -> ignored
    assert mapping.extract_packages("junk") == []


def test_package_id():
    # Real orders-endpoint payload: no top-level "id", only "shipmentPackageId".
    assert mapping.package_id({"shipmentPackageId": 92261124, "orderNumber": "858409652"}) == "92261124"
    assert mapping.package_id({"id": 123}) == "123"                       # webhook/doc shape
    assert mapping.package_id({"shipmentAddress": {"id": 18400106}}) == ""  # nested id is NOT it
    # must never be the string "None": that collapses every order onto one dedup key
    assert mapping.package_id({}) == ""


def test_epoch_ms_to_dt():
    dt = mapping.epoch_ms_to_dt(1700000000000)
    assert dt is not None and dt.year == 2023 and dt.month == 11
    assert mapping.epoch_ms_to_dt(0) is None
    assert mapping.epoch_ms_to_dt(None) is None


def test_buyer_name_sources():
    # 1. the package's own customer fields win
    assert mapping.buyer({"customerFirstName": "Salahah", "customerLastName": "Al-Shahri",
                          "shipmentAddress": {"fullName": "Someone Else"}}
                         )["name"] == "Salahah Al-Shahri"
    # 2. shipmentAddress.fullName
    assert mapping.buyer({"shipmentAddress": {"fullName": "Fariduh Al-Abas"}}
                         )["name"] == "Fariduh Al-Abas"
    # 3. shipmentAddress first+last
    assert mapping.buyer({"shipmentAddress": {"firstName": "Ana", "lastName": "Ruiz"}}
                         )["name"] == "Ana Ruiz"
    # half a name must not leave a trailing space -> it would create "Trendyol - Ana "
    # and never match "Trendyol - Ana" again on the next order.
    assert mapping.buyer({"customerFirstName": "Ana"})["name"] == "Ana"


def test_buyer_name_only_payload():
    # The MENA shape Wayakit expects: a name and nothing else (the address travels on
    # Trendyol's shipping label). Must not blow up and must not invent address values.
    info = mapping.buyer({"customerFirstName": "Ana", "customerLastName": "Ruiz"})
    assert info["name"] == "Ana Ruiz"
    assert (info["street"], info["city"], info["zip"], info["phone"],
            info["country_code"]) == ("", "", "", "", "")


def test_buyer_ref_and_address():
    info = mapping.buyer({
        "customerId": 4455661,
        "shipmentAddress": {"fullName": "Ana Ruiz", "address1": "King Fahd Rd",
                            "address2": "Apt 4", "city": "Riyadh", "postalCode": 12345,
                            "phone": "+966500000000", "countryCode": "sa"},
    })
    assert info["ref"] == "4455661"          # str, never an int: it is matched as a Char
    assert info["street"] == "King Fahd Rd" and info["street2"] == "Apt 4"
    assert info["zip"] == "12345"            # arrives as an int on real payloads
    assert info["country_code"] == "SA"      # upper: res.country.code is uppercase


def test_buyer_anonymous():
    # No name anywhere -> "" so the caller falls back to the generic marketplace partner
    # instead of creating one anonymous contact per order.
    assert mapping.buyer({})["name"] == ""
    assert mapping.buyer({"shipmentAddress": {"city": "Riyadh"}})["name"] == ""
    assert mapping.buyer({})["ref"] == ""    # never the literal "None"


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


def test_line_id():
    # Real orders payload spells it "lineId", not "id" — reading "id" produced an empty
    # lines list and the status push answered 404. Both spellings must resolve.
    pkg = {"lines": [{"lineId": 10562124, "stockCode": "FP-HOM-03601", "quantity": 1,
                      "lineUnitPrice": 100.0}]}
    assert mapping.normalize_lines(pkg)[0]["line_id"] == "10562124"
    # doc/webhook spelling
    assert mapping.normalize_lines({"lines": [{"id": 987654}]})[0]["line_id"] == "987654"
    # absent -> empty string, never the literal "None" (it would be pushed as a lineId)
    assert mapping.normalize_lines({"lines": [{"stockCode": "X"}]})[0]["line_id"] == ""


def test_sku_from_model_code():
    # Wayakit stores the SKU in Trendyol's "Model code" (productMainId); when
    # merchantSku/sku are absent it must be used as the match key.
    pkg = {"lines": [{"productMainId": "FP-PET-01500", "quantity": 1, "price": 50.0}]}
    assert mapping.normalize_lines(pkg)[0]["sku"] == "FP-PET-01500"


def test_sku_from_stock_code():
    # Live order-line payloads carry only stockCode/barcode, no productMainId/
    # merchantSku — this is the shape that must resolve to a SKU.
    pkg = {"lines": [{"stockCode": "FP-HOM-03601", "barcode": "FP-HOM-03601",
                       "quantity": 1, "price": 13.0}]}
    assert mapping.normalize_lines(pkg)[0]["sku"] == "FP-HOM-03601"


def test_price_from_line_unit_price():
    # Live order-line payloads have no "price"/"amount" field, only lineUnitPrice
    # (gross) — that's what was silently defaulting to 0.
    pkg = {"lines": [{"stockCode": "FP-HOM-03601", "quantity": 1,
                       "lineUnitPrice": 13.0, "vatRate": 10.0}]}
    line = mapping.normalize_lines(pkg)[0]
    assert abs(line["price"] - 13.0 / 1.10) < 1e-9


def test_vat_stripped():
    # Trendyol sends VAT-inclusive prices; Odoo adds 15% back -> net must be gross/1.15
    pkg = {"lines": [{"merchantSku": "FP-DIS-00001", "quantity": 1, "price": 115.0, "vatRate": 15}]}
    line = mapping.normalize_lines(pkg)[0]
    assert abs(line["price"] - 100.0) < 1e-9


if __name__ == "__main__":
    for fn in [test_should_import, test_map_state, test_should_lock,
               test_package_id, test_epoch_ms_to_dt,
               test_buyer_name_sources, test_buyer_name_only_payload,
               test_buyer_ref_and_address, test_buyer_anonymous, test_normalize_lines, test_line_id,
               test_sku_from_model_code, test_sku_from_stock_code,
               test_price_from_line_unit_price, test_vat_stripped, test_extract_packages]:
        fn()
        print(fn.__name__, "OK")
    print("all passed")
