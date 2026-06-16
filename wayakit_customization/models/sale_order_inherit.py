# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_national_short_code = fields.Char(
        related='partner_id.x_national_short_code',
        string="National Address Short Code",
        readonly=False,
        store=False,
        help="Saudi National Address short code of the customer (captured via WhatsApp). "
             "Editing it here writes back to the customer record and is reused across orders.",
    )