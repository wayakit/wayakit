{
    "name": "Salla Connector",
    "summary": "Direct Salla (KSA) integration for Wayakit, no middleware: OAuth app "
               "authorization, signed webhooks, connection test and SKU reconciliation.",
    "category": "Sales",
    "version": "17.0.1.0.1",
    "author": "Wayakit",
    "website": "https://wayakit.com",
    "license": "LGPL-3",
    # sale_stock (not plain stock): from F2 on a confirmed Salla order must produce its
    # delivery and carry warehouse_id. Deliberately independent of the Tecfy modules
    # (odoo_salla_*, models tecfysalla.*): this replaces them and must survive their
    # uninstall.
    "depends": ["sale_management", "sale_stock"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/ir.model.access.csv",
        "views/salla_backend_views.xml",
        "data/salla_cron.xml",
    ],
    "application": False,
    "installable": True,
}
