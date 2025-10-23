# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ProductMaster(models.Model):
    _name = 'product.master'
    _description = 'Master Product Table'
    external_id = fields.Char(string='External ID')
    product_id = fields.Char(string='Product ID')
    product_name = fields.Char(string='Product Name')
    label_product_name = fields.Char(string='Label Product Name')
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
    presentation = fields.Char(string='Presentation')
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
    volume_liters = fields.Float(string='Volume (Liters)')
    pack_quantity_units = fields.Integer(string='Pack Quantity (Units)')
    type_of_product_id = fields.Many2one('product.classification', string='Type of Product')
    category = fields.Char(string='Category')
    generic_product_type = fields.Char(string='Generic Product Type')
    subindustry_id = fields.Many2one('product.subindustry', string='Sub-Industry')
    industry_id = fields.Many2one('product.industry', string='Industry', readonly=True, store=True,
                                  compute='_compute_industry')
    description = fields.Text(string='Description')
    dilution_rate = fields.Char(string='Dilution Rate')

    # Cost Fields
    bottle_cost = fields.Float(string='Bottle')
    label_cost = fields.Float(string='Label')
    liquid_cost = fields.Float(string='Liquid')
    microfibers_cost = fields.Float(string='Microfibers')
    plastic_bag_cost = fields.Float(string='Plastic Bag')
    labor_cost = fields.Float(string='Labor')
    shipping_cost = fields.Float(string='Shipping')
    other_costs = fields.Float(string='Other Costs')
    unit_cost_sar = fields.Float(string='Unit Cost (SAR)',
                                 compute='_compute_unit_cost_sar',
                                 store=True)

    @api.depends('subindustry_id')
    def _compute_industry(self):
        for record in self:
            if record.subindustry_id:
                record.industry_id = record.subindustry_id.industry_id
            else:
                record.industry_id = False

    @api.onchange('type_of_product_id')
    def _onchange_type_of_product_id(self):
        if self.type_of_product_id:
            classification = self.type_of_product_id

            self.category = classification.category
            self.subindustry_id = classification.subindustry_id
            self.generic_product_type = classification.generic_product_type
        else:
            self.category = False
            self.subindustry_id = False
            self.generic_product_type = False
            self.industry_id = False

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