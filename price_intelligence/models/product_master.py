# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ProductMaster(models.Model):
    _name = 'product.master'
    _description = 'Master Product Table'
    create_date = fields.Datetime(string="Creation Date")
    external_id = fields.Char(string='External ID')
    product_id = fields.Char(string='Product ID', required=True)
    product_name = fields.Char(string='Product Name', required=True)
    label_product_name = fields.Char(string='Label Product Name', required=True)

    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], string='Status', default='active')
    master_product = fields.Boolean(string='Master Product')
    uploaded_in_odoo = fields.Boolean(string='Uploaded in Odoo')
    notes = fields.Text(string='Notes')

    formula_code = fields.Char(string='Formula Code')

    moq = fields.Float(string='MOQ')

    order_unit = fields.Char(string='Order Unit')
    presentation = fields.Char(string='Presentation', required=True)
    scent = fields.Selection([
        ('rose_musk', 'Rose musk'),
        ('unscented', 'Unscented'),
        ('jasmine', 'Jasmine'),
        ('baby_scent', 'Baby scent'),
        ('not_applicable', 'Attribute not aplicable')
    ], string='Scent')
    type = fields.Selection([
        ('not_applicable', 'Attribute not applicable'),
        ('new', 'New'),
        ('refill', 'Refill (only liquid)')
    ], string='Type')

    link_to_product_mockup = fields.Char(string='Link to Product Mockup')

    volume_liters = fields.Float(string='Volume (Liters)', required=True)
    pack_quantity_units = fields.Integer(string='Pack Quantity (Units)', required=True)

    type_of_product_id = fields.Many2one('product.classification', string='Type of Product', required=True)

    category = fields.Char(
        string='Category',
        related='type_of_product_id.category',
        store=True,
        readonly=True
    )
    generic_product_type = fields.Char(
        string='Generic Product Type',
        related='type_of_product_id.generic_product_type',
        store=True,
        readonly=True
    )
    subindustry_id = fields.Many2one(
        'product.subindustry',
        string='Sub-Industry',
        related='type_of_product_id.subindustry_id',
        store=True,
        readonly=True
    )
    industry_id = fields.Many2one(
        'product.industry',
        string='Industry',
        related='type_of_product_id.industry_id',
        store=True,
        readonly=True
    )
    description = fields.Text(string='Description')
    dilution_rate = fields.Char(string='Dilution Rate')

    bottle_cost = fields.Float(string='Bottle', required=True)
    label_cost = fields.Float(string='Label', required=True)
    liquid_cost = fields.Float(string='Liquid', required=True)
    microfibers_cost = fields.Float(string='Microfibers', required=True)
    plastic_bag_cost = fields.Float(string='Plastic Bag', required=True)
    labor_cost = fields.Float(string='Labor', required=True)
    shipping_cost = fields.Float(string='Shipping', required=True)
    other_costs = fields.Float(string='Other Costs', required=True)

    unit_cost_sar = fields.Float(string='Unit Cost (SAR)',
                                 compute='_compute_unit_cost_sar',
                                 store=True)

    @api.depends('bottle_cost', 'label_cost', 'liquid_cost', 'microfibers_cost',
                 'plastic_bag_cost', 'labor_cost', 'shipping_cost', 'other_costs')
    def _compute_unit_cost_sar(self):
        for record in self:
            record.unit_cost_sar = (
                    record.bottle_cost +
                    record.label_cost +
                    record.liquid_cost +
                    record.microfibers_cost +
                    record.plastic_bag_cost +
                    record.labor_cost +
                    record.shipping_cost +
                    record.other_costs
            )

    @api.constrains('volume_liters', 'pack_quantity_units')
    def _check_volume_or_pack_quantity(self):
        for record in self:
            if record.volume_liters <= 0 and record.pack_quantity_units <= 0:
                raise ValidationError(
                    "The product must have a 'Volume (Liters)' or 'Pack Quantity (Units)' greater than 0. Both can't be 0."
                )