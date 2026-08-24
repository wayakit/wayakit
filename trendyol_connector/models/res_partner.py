from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    trendyol_customer_ref = fields.Char(
        string="Trendyol Customer ID", index=True, copy=False, readonly=True,
        help="Trendyol's own customer id. Anti-duplicate key: a repeat buyer reuses this "
             "contact instead of creating a new one.",
    )
    # ponytail: no SQL unique constraint on purpose. res.partner is created by every app in
    # the database; a unique index here would turn any connector bug into a hard error on
    # unrelated contact creation. A limit=1 search is enough for ~2 orders/month.
