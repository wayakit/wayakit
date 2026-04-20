from odoo import fields, models


class BillingDefaultFields(models.Model):
    _name = 'billing.default.fields'
    _description = 'Billing Default Fields'
    _rec_name = 'name'
    _order = 'name'

    name = fields.Char(string='Label', required=True)
    field_name = fields.Char(string='Field Name', required=True)


class ShippingDefaultFields(models.Model):
    _name = 'shipping.default.fields'
    _description = 'Shipping Default Fields'
    _rec_name = 'name'
    _order = 'name'

    name = fields.Char(string='Label', required=True)
    field_name = fields.Char(string='Field Name', required=True)
