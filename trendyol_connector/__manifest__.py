{
    "name": "Trendyol Connector (MENA, FBM)",
    "summary": "Direct Trendyol MENA integration for Wayakit: auth, product match, order "
               "import, order confirmation, status push and stock sync.",
    "category": "Sales",
    "version": "17.0.3.0.0",
    "author": "Wayakit",
    "website": "https://wayakit.com",
    "license": "LGPL-3",
    # sale_stock (not plain stock): it is what turns a confirmed order into a delivery
    # and provides sale.order.warehouse_id / stock.picking.sale_id. The delivery/carrier
    # side is deliberately NOT a dependency: Trendyol supplies the shipping guide, so
    # Wayakit never pushes tracking (see CLAUDE.md §9).
    "depends": ["sale_management", "sale_stock"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/ir.model.access.csv",
        "data/trendyol_data.xml",
        "views/trendyol_backend_views.xml",
        "views/sale_order_views.xml",
        "views/activity.xml",
    ],
    "application": False,
    "installable": True,
}