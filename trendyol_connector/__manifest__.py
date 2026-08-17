{
    "name": "Trendyol Connector (MENA, FBM)",
    "summary": "Direct Trendyol MENA integration for Wayakit: auth, product match, order "
               "import, order confirmation, status/tracking push and stock sync.",
    "category": "Sales",
    "version": "17.0.2.0.0",
    "author": "Wayakit",
    "website": "https://wayakit.com",
    "license": "LGPL-3",
    # stock_delivery (not plain stock): it pulls sale_stock — which is what turns a
    # confirmed order into a delivery and provides sale.order.warehouse_id /
    # stock.picking.sale_id — and delivery, where carrier_id / carrier_tracking_ref on
    # stock.picking actually live in Odoo 17.
    "depends": ["sale_management", "stock_delivery"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/ir.model.access.csv",
        "data/trendyol_data.xml",
        "views/trendyol_backend_views.xml",
        "views/sale_order_views.xml",
        "views/delivery_carrier_views.xml",
        "views/activity.xml",
    ],
    "application": False,
    "installable": True,
}