from odoo import fields, models, api

class ServiceType(models.Model):
    _name = "service.type"
    _description = "Service Type"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char()
    service_type = fields.Selection([
        ('vehicle', 'Vehicle'),
        ('curtain', 'Curtain'),
    ], string='Service Type')
    vehicle_type = fields.Selection([
        ('car', 'Car'),
        ('bike', 'Bike')
    ], string='Vehicle Type')
    in_use = fields.Selection([
        ('personal', 'Personal'),
        ('business', 'Business')
    ], string='In use')
    sub_type_ids = fields.One2many(
        'vehicle.type',
        'service_type_id',
    )


class VehicleType(models.Model):
    _name = "vehicle.type"
    _description = "Vehicle Type"

    name = fields.Char()
    price = fields.Float()
    inclusive_tax_price = fields.Float(compute='_compute_inclusive_tax_price', store=True)
    tax = fields.Many2one('account.tax')
    service_type_id = fields.Many2one('service.type')

    @api.depends('price', 'tax')
    def _compute_inclusive_tax_price(self):
        for rec in self:
            if rec.tax and rec.price:
                tax_value = (rec.tax.amount/100) * rec.price
                rec.inclusive_tax_price = rec.price + tax_value
            else:
                rec.inclusive_tax_price = rec.price


