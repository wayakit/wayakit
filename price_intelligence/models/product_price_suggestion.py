# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ProductPriceSuggestion(models.Model):
    _name = 'product.price.suggestion'
    _description = 'Product Price Suggestion'
    _order = 'last_update_date desc'

    last_update_date = fields.Datetime(string='Last Update Date', readonly=True, default=fields.Datetime.now)
    product_id_str = fields.Char(string='Product ID', required=True)
    product_type = fields.Char(string='Product Type')
    generic_product_type = fields.Char(string='Generic Product Type')
    subindustry = fields.Char(string='Sub-industry')
    industry = fields.Char(string='Industry')
    volume_units = fields.Float(string='Volume (L)/Units')
    production_cost = fields.Float(string='Production Cost')
    suggested_price = fields.Float(string='Suggested Sale Price')
    profit = fields.Float(string='Profit')
    product_name = fields.Char(string='Product Name')
    predicted_price_per_unit = fields.Float(string='Sugg. Price Per L/U')
    model_confidence = fields.Float(string='Model Confidence (%)')
    market_min_found = fields.Float(string='Market Min Found')
    market_max_found = fields.Float(string='Market Max Found')
    competitors_count = fields.Integer(string='Competitors Count')

    @api.model
    def create(self, vals):
        # 1. Crear la sugerencia
        record = super(ProductPriceSuggestion, self).create(vals)

        # 2. Buscar si existe un Producto Maestro
        if record.product_id_str:
            master_products = self.env['product.master'].search([
                ('product_id', '=', record.product_id_str)
            ])

            # 3. SOLUCIÓN: Usar write() para disparar el recálculo completo y limpio
            if master_products:
                master_products.write({
                    'ai_last_updated': fields.Datetime.now()
                })

                # Opcional: Despertar a los hermanos (Logic remains similar but using write)
                # Nota: Si los hermanos dependen de este producto, su lógica debería manejarlo,
                # si no, puedes iterar y hacer write en ellos también.
                siblings = self.env['product.master'].search([
                    ('generic_product_type', '=', master_products[0].generic_product_type),
                    ('id', 'not in', master_products.ids)
                ])
                if siblings:
                    siblings.write({
                        'ai_last_updated': fields.Datetime.now()
                    })

        return record