from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    # Carrier mapping is data, not code: one field the user fills once per carrier
    # (Aramex, SMSA, …) instead of a hardcoded table that needs a redeploy to change.
    trendyol_provider_code = fields.Char(
        string="Trendyol Provider Code",
        help="Trendyol cargo providerCode for this carrier (e.g. DHLMP). Sent with the "
             "waybill number when the delivery is validated. Leave empty to never push "
             "tracking for orders shipped with this carrier.",
    )
