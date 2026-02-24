# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from markupsafe import Markup
import logging
import re

_logger = logging.getLogger(__name__)


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

    formula_code = fields.Many2one('product.formula.code', string='Formula Code')

    moq = fields.Float(string='MOQ')

    order_unit = fields.Char(string='Order Unit')
    presentation = fields.Char(string='Presentation')
    scent = fields.Selection([
        ('rose_musk', 'Rose musk'),
        ('unscented', 'Unscented'),
        ('jasmine', 'Jasmine'),
        ('baby_scent', 'Baby scent'),
        ('not_applicable', 'Attribute not applicable')
    ], string='Scent')
    type = fields.Selection([
        ('not_applicable', 'Attribute not applicable'),
        ('new', 'New'),
        ('refill', 'Refill (only liquid)')
    ], string='Type')

    link_to_product_mockup = fields.Char(string='Link to Product Mockup')

    volume_liters = fields.Float(string='Volume (Liters)')
    pack_quantity_units = fields.Integer(string='Pack Quantity (Units)')

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
    dilution_rate = fields.Float(string='Dilution Rate', digits=(12, 2),
                                 help="Factor to multiply the liquid cost. Leave at 0.0 or 1.0 to apply no change.")

    bottle_cost = fields.Float(string='Bottle', required=True)
    label_cost = fields.Float(string='Label', required=True)
    liquid_cost = fields.Float(string='Liquid',
                               compute='_compute_liquid_cost',
                               store=True,
                               readonly=True)
    microfibers_cost = fields.Float(string='Microfibers', required=True)
    plastic_bag_cost = fields.Float(string='Plastic Bag', required=True)
    labor_cost = fields.Float(string='Labor', required=True)
    shipping_cost = fields.Float(string='Shipping', required=True)
    other_costs = fields.Float(string='Other Costs', required=True)

    unit_cost_sar = fields.Float(string='Unit Cost (SAR)',
                                 compute='_compute_unit_cost_sar',
                                 store=True)

    ecommerce_data_html = fields.Html(
        string='Ecommerce Price',
        compute='_compute_ecommerce_data',
        store=False,
        help="Price fetched from Odoo Ecommerce with direct link to product form. If not found, infers product with same category."
    )

    ai_last_updated = fields.Datetime(string='Last AI Update Trigger')

    is_ai_pricing_active = fields.Boolean(
        string='Is AI Pricing Active',
        compute='_compute_pricing_list',
        store=True,
        help="Technical field to indicate if the current pricing is based on AI or Traditional rules."
    )

    ai_market_min = fields.Float(string='Market Min', compute='_compute_ai_predicted_price')
    ai_market_max = fields.Float(string='Market Max', compute='_compute_ai_predicted_price')
    is_box_8_4 = fields.Boolean(compute='_compute_is_box_8_4', store=True)

    dilution_rate_ml = fields.Float(
        string='Dilution Rate (ml/L)',
        help="Milliliters of concentrated product needed to make 1L of ready-to-use mixture."
    )

    dilution_ratio = fields.Float(
        string='Ratio (1:X)',
        compute='_compute_dilution_data',
        store=True,
        help="Example: If 20ml/L, Ratio is 1:50 (1000/20)"
    )
    total_diluted_liters = fields.Float(
        string='Total Yield (Liters)',
        compute='_compute_dilution_data',
        store=True,
        help="Total liters of ready-to-use product that this container produces."
    )

    diluted_price_spark = fields.Float(string='Spark Diluted P/L', compute='_compute_dilution_data', store=True)
    diluted_price_flow = fields.Float(string='Flow Diluted P/L', compute='_compute_dilution_data', store=True)
    diluted_price_cycle = fields.Float(string='Cycle Diluted P/L', compute='_compute_dilution_data', store=True)
    diluted_price_stream = fields.Float(string='Stream Diluted P/L', compute='_compute_dilution_data', store=True)
    diluted_price_source = fields.Float(string='Source Diluted P/L', compute='_compute_dilution_data', store=True)

    dilution_recommendation_id = fields.Many2one(
        'product.dilution.recommendation',
        string='Usage Recommendation'
    )

    def _get_product_from_ext_id(self, ext_id):
        """Busca el registro en Odoo (Template o Product) y valida activo/publicado."""
        if not ext_id:
            return None

        imd_env = self.env['ir.model.data'].sudo()

        domain = []
        if '.' in ext_id:
            module, name = ext_id.split('.', 1)
            domain += [('module', '=', module), ('name', '=', name)]
        else:
            domain += [('name', '=', ext_id)]

        xml_id_rec = imd_env.search(domain, limit=1)

        if xml_id_rec:
            if xml_id_rec.model in ['product.template', 'product.product']:
                try:
                    record = self.env[xml_id_rec.model].sudo().browse(xml_id_rec.res_id)

                    # Validaciones de seguridad
                    if not record.exists():
                        return None
                    if not record.active:
                        return None

                    is_published = False
                    if xml_id_rec.model == 'product.product':
                        is_published = record.product_tmpl_id.is_published
                    else:
                        is_published = record.is_published

                    if not is_published:
                        return None

                    return record
                except Exception as e:
                    _logger.warning(f"Error fetching product: {e}")
                    return None
        return None

    def _get_variant_price(self, product_obj, target_vol_liters):
        """
        Busca el precio priorizando:
        1. Type = New
        2. Volume = Match Exacto (Flexible)
        3. Scent = Unscented (Prioridad)
        """
        if not product_obj:
            return 0.0, None

        if product_obj._name == 'product.product':
            return product_obj.lst_price, product_obj

        volume_match = None

        for variant in product_obj.product_variant_ids:
            if not variant.active:
                continue

            match_type = False
            match_vol = False
            is_unscented = False

            for ptav in variant.product_template_attribute_value_ids:
                attr_name = ptav.attribute_id.name.lower()
                val_name = ptav.name.lower()
                val_clean = val_name.replace(" ", "")

                if 'type' in attr_name and 'new' in val_name:
                    match_type = True

                if 'scent' in attr_name and 'unscented' in val_name:
                    is_unscented = True

                if 'volume' in attr_name:
                    if target_vol_liters == 0.7 and '700ml' in val_clean:
                        match_vol = True
                    elif target_vol_liters == 4.0 and '4l' in val_clean:
                        match_vol = True
                    elif target_vol_liters not in [0.7, 4.0]:
                        nums = re.findall(r"[-+]?\d*\.\d+|\d+", val_name)
                        if nums:
                            try:
                                v = float(nums[0])
                                v_l = v / 1000.0 if v >= 50 else v
                                if abs(v_l - target_vol_liters) < 0.05:
                                    match_vol = True
                            except:
                                pass

            if match_type and match_vol:
                if is_unscented:
                    return variant.lst_price, variant

                if not volume_match:
                    volume_match = variant

        if volume_match:
            return volume_match.lst_price, volume_match

        return 0.0, None

    @api.depends('external_id', 'generic_product_type', 'volume_liters')
    def _compute_ecommerce_data(self):
        # Filtro de subindustrias permitidas
        allowed_subindustries = ['Home', 'Automotive', 'Pets']

        for record in self:
            found_object = None
            final_price = 0.0

            # 1. Intentar buscar el producto propio
            my_object = record._get_product_from_ext_id(record.external_id)

            if my_object:
                p, v_obj = record._get_variant_price(my_object, record.volume_liters)
                if p > 0:
                    final_price = p
                    found_object = v_obj if v_obj else my_object

            # 2. INTELIGENCIA DE PRECIOS
            if final_price == 0.0 and record.generic_product_type:

                base_domain = [
                    ('generic_product_type', '=', record.generic_product_type),
                    ('external_id', '!=', False),
                    ('type_of_product_id.subindustry_id.name', 'in', allowed_subindustries)
                ]

                if isinstance(record.id, int):
                    base_domain.append(('id', '!=', record.id))

                # A) Match Exacto de Volumen (Busca registros master con el mismo volumen)
                siblings = self.search(base_domain + [('volume_liters', '=', record.volume_liters)])
                for sibling in siblings:
                    sib_obj = record._get_product_from_ext_id(sibling.external_id)
                    p, v_obj = record._get_variant_price(sib_obj, record.volume_liters)
                    if p > 0:
                        final_price = p
                        found_object = v_obj
                        break

                # B) Volúmenes Grandes (Busca registros master grandes)
                if final_price == 0.0 and record.volume_liters >= 3.5:
                    siblings_large = self.search(base_domain + [('volume_liters', '>=', 3.5)],
                                                 order='volume_liters desc')
                    for sibling in siblings_large:
                        sib_obj = record._get_product_from_ext_id(sibling.external_id)
                        p, v_obj = record._get_variant_price(sib_obj, sibling.volume_liters)
                        if p > 0:
                            final_price = p
                            found_object = v_obj
                            break

                # C) Búsqueda Cruzada: Buscar en hermanos pequeños si tienen variante grande
                if final_price == 0.0 and record.volume_liters >= 3.5:
                    siblings_small = self.search(base_domain + [('volume_liters', '<', 3.5)])

                    # C-1) Buscar variante EXACTA (ej. 20L) dentro de productos pequeños
                    for sibling in siblings_small:
                        sib_obj = record._get_product_from_ext_id(sibling.external_id)
                        p, v_obj = record._get_variant_price(sib_obj, record.volume_liters)
                        if p > 0:
                            final_price = p
                            found_object = v_obj
                            break

                    # C-2) [NUEVO] Si busco algo muy grande (> 4.0L, ej 8.4L o 20L) y falló lo anterior,
                    # intento buscar la variante de 4.0L como punto medio antes de caer al 700ml.
                    if final_price == 0.0 and record.volume_liters > 4.0:
                        for sibling in siblings_small:
                            sib_obj = record._get_product_from_ext_id(sibling.external_id)
                            p, v_obj = record._get_variant_price(sib_obj, 4.0)
                            if p > 0:
                                final_price = p
                                found_object = v_obj
                                break

                # D) Fallback a 700ml (0.7L)
                if final_price == 0.0:
                    siblings_small = self.search(base_domain + [('volume_liters', '=', 0.7)])
                    for sibling in siblings_small:
                        sib_obj = record._get_product_from_ext_id(sibling.external_id)
                        p, v_obj = record._get_variant_price(sib_obj, 0.7)
                        if p > 0:
                            final_price = p
                            found_object = v_obj
                            break

            # 3. Construcción del HTML
            if found_object and final_price > 0:
                currency_symbol = found_object.currency_id.symbol or '$'

                model_name = found_object._name
                res_id = found_object.id
                url = f"/web#id={res_id}&model={model_name}&view_type=form"

                price_text = f"{currency_symbol} {final_price:,.2f}"

                html_content = f"""
                        <a href="{url}" target="_blank" 
                           style="color: #28a745; font-weight: bold; text-decoration: none;">
                           {price_text}
                        </a>
                    """
                record.ecommerce_data_html = Markup(html_content)
            else:
                record.ecommerce_data_html = Markup('<span style="color: #6c757d;">$ 0.00</span>')

    # =========================================================
    # LOGICA DE PRECIOS E INTELIGENCIA
    # =========================================================

    # 1. Configuración Manual (Delegada a Clasificación)
    manual_base_margin = fields.Float(
        string='Strategy Base Margin (0.7L)',
        related='type_of_product_id.base_margin_07',
        readonly=False,
    )

    # 2. Margen Efectivo (Calculado)
    base_prediction_margin = fields.Float(
        string='Applied Margin (%)',
        compute='_compute_pricing_list',
        store=True,
        digits=(12, 4),
        help="Final margin used for the operation(Margin Base + Margin per volume)."
    )

    # 3. AI Prediction & Profit
    ai_predicted_price = fields.Float(string='AI Prediction (Price)', compute='_compute_ai_predicted_price')
    ai_predicted_margin = fields.Float(string='AI Margin (%)', compute='_compute_ai_predicted_price')

    # 4. PRECIOS POR TIER (Editables para refresco en vivo)
    price_tier_spark = fields.Float(string='Spark Price (Tier 1)', compute='_compute_pricing_list', store=True,
                                    readonly=False)
    price_tier_flow = fields.Float(string='Flow Price (Tier 2)', compute='_compute_pricing_list', store=True,
                                   readonly=False)
    price_tier_cycle = fields.Float(string='Cycle Price (Tier 3)', compute='_compute_pricing_list', store=True,
                                    readonly=False)
    price_tier_stream = fields.Float(string='Stream Price (Tier 4)', compute='_compute_pricing_list', store=True,
                                     readonly=False)
    price_tier_source = fields.Float(string='Source Price (Tier 5)', compute='_compute_pricing_list', store=True,
                                     readonly=False)

    # 5. DETALLES POR TIER (Márgenes y Precio/Litro) - NUEVO
    # Margenes
    margin_tier_spark = fields.Float(string='Spark Margin', compute='_compute_pricing_list', store=True, digits=(12, 2))
    margin_tier_flow = fields.Float(string='Flow Margin', compute='_compute_pricing_list', store=True, digits=(12, 2))
    margin_tier_cycle = fields.Float(string='Cycle Margin', compute='_compute_pricing_list', store=True, digits=(12, 2))
    margin_tier_stream = fields.Float(string='Stream Margin', compute='_compute_pricing_list', store=True,
                                      digits=(12, 2))
    margin_tier_source = fields.Float(string='Source Margin', compute='_compute_pricing_list', store=True,
                                      digits=(12, 2))

    # Precio por Litro
    pl_tier_spark = fields.Float(string='Spark P/L', compute='_compute_pricing_list', store=True, digits=(12, 2))
    pl_tier_flow = fields.Float(string='Flow P/L', compute='_compute_pricing_list', store=True, digits=(12, 2))
    pl_tier_cycle = fields.Float(string='Cycle P/L', compute='_compute_pricing_list', store=True, digits=(12, 2))
    pl_tier_stream = fields.Float(string='Stream P/L', compute='_compute_pricing_list', store=True, digits=(12, 2))
    pl_tier_source = fields.Float(string='Source P/L', compute='_compute_pricing_list', store=True, digits=(12, 2))

    # --- FUNCIONES COMPUTE ---

    @api.depends('formula_code', 'formula_code.price_per_liter', 'volume_liters', 'dilution_rate')
    def _compute_liquid_cost(self):
        for record in self:
            # A. Calculamos el Costo Base (Fórmula * Litros)
            base_cost = 0.0
            if record.formula_code and record.volume_liters > 0:
                cost_liter = record.formula_code.price_per_liter
                base_cost = cost_liter * record.volume_liters

            # B. Aplicamos el Dilution Rate
            # Regla: Si es mayor a 0, multiplicamos. Si es 0, se queda igual.
            if record.dilution_rate > 0:
                record.liquid_cost = base_cost * record.dilution_rate
            else:
                record.liquid_cost = base_cost

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

    def _get_sibling_record(self, target_vol):
        """Ayuda a encontrar el registro hermano (mismo tipo) con otro volumen."""
        self.ensure_one()
        if not self.generic_product_type:
            return None

        # Tolerancia para búsqueda de volumen (float)
        domain = [
            ('generic_product_type', '=', self.generic_product_type),
            ('volume_liters', '>=', target_vol - 0.05),
            ('volume_liters', '<=', target_vol + 0.05),
            # Asegurar que buscamos en la misma subindustria para evitar cruces raros
            ('type_of_product_id', '!=', False)
        ]

        # CORRECCIÓN NEWID: Solo excluir self.id si es un entero real (ya guardado en DB)
        if self.id and isinstance(self.id, int):
            domain.append(('id', '!=', self.id))

        # Si la clasificación es importante, filtrar también por subindustria si aplica
        if self.type_of_product_id.subindustry_id:
            domain.append(('type_of_product_id.subindustry_id', '=', self.type_of_product_id.subindustry_id.id))

        return self.search(domain, limit=1)

    def _get_ai_suggestion(self, volume_liters):
        self.ensure_one()
        if not self.product_id:
            return 0.0, False

        suggestion = self.env['product.price.suggestion'].search([
            ('product_id_str', '=', self.product_id)
        ], limit=1, order='last_update_date desc')

        if not suggestion:
            return 0.0, False

        price = suggestion.suggested_price

        # 1. Validación Básica
        if price <= 0:
            return 0.0, False

        # 2. VALIDACIÓN DE RANGOS DE MERCADO (CRÍTICO)
        # Si el precio está fuera de rango, la predicción NO ES ACEPTADA.
        if suggestion.market_min_found > 0 and price < suggestion.market_min_found:
            return 0.0, False  # Rechazada por estar muy barata

        if suggestion.market_max_found > 0 and price > suggestion.market_max_found:
            return 0.0, False  # Rechazada por estar muy cara

        # 3. Validación de Margen Mínimo (Safety Net)
        if self.unit_cost_sar > 0:
            margin = 1.0 - (self.unit_cost_sar / price)
            if margin < 0.30:
                return 0.0, False  # Rechazada por margen riesgoso

        # Si pasa todo, es una predicción ACEPTADA
        return price, True

    @api.depends('unit_cost_sar', 'volume_liters', 'type_of_product_id',
                 'manual_base_margin',
                 'type_of_product_id.base_margin_07',
                 'type_of_product_id.variance_box',
                 'type_of_product_id.variance_4l',
                 'type_of_product_id.variance_20l',
                 'ai_predicted_price',
                 'ai_last_updated')
    def _compute_pricing_list(self):
        for record in self:
            cost = record.unit_cost_sar
            vol = record.volume_liters or 1.0

            record.is_ai_pricing_active = False

            # Limpiar valores previos
            record.price_tier_spark = 0.0
            record.price_tier_flow = 0.0
            record.price_tier_cycle = 0.0
            record.price_tier_stream = 0.0
            record.price_tier_source = 0.0

            # Si no hay costo, no podemos calcular nada con seguridad
            if not cost:
                # Resetear metadata visual
                record.margin_tier_spark = 0.0;
                record.pl_tier_spark = 0.0
                record.margin_tier_flow = 0.0;
                record.pl_tier_flow = 0.0
                record.margin_tier_cycle = 0.0;
                record.pl_tier_cycle = 0.0
                record.margin_tier_stream = 0.0;
                record.pl_tier_stream = 0.0
                record.margin_tier_source = 0.0;
                record.pl_tier_source = 0.0
                record.base_prediction_margin = 0.0
                continue

            # =========================================================
            # PASO 1: EVALUAR "CONDICIÓN MADRE" (El Gatekeeper 0.7L)
            # =========================================================
            use_smart_mode = False

            # Identificar el registro de 0.7L (puede ser self o un hermano)
            rec_07 = None
            if abs(vol - 0.7) < 0.05:
                rec_07 = record
            else:
                rec_07 = record._get_sibling_record(0.7)

            # Validar IA del 0.7L
            price_ai_07 = 0.0
            has_valid_ai_07 = False

            if rec_07:
                # Checa existencia, rango de mercado y margen >= 30%
                price_ai_07, has_valid_ai_07 = rec_07._get_ai_suggestion(0.7)

            # DECISIÓN GLOBAL: ¿Modo Inteligente o Tradicional?
            if has_valid_ai_07:
                use_smart_mode = True
            else:
                use_smart_mode = False

            record.is_ai_pricing_active = use_smart_mode

            # =========================================================
            # PASO 2: CALCULAR PRECIOS (Dos Ramas)
            # =========================================================

            tier1_price = 0.0
            tier1_margin = 0.0

            # --- RAMA A: MODO TRADICIONAL (COST PLUS) ---
            # (Se usa si falla la IA del 0.7L o su margen es < 30%)
            if not use_smart_mode:
                # Lógica original: Base Margin + Varianza -> Tier 5 -> Tier 1
                base = record.type_of_product_id.base_margin_07 if record.type_of_product_id else 0.30

                added_margin = 0.0
                if record.type_of_product_id and vol > 0:
                    if 8.0 <= vol <= 9.0:
                        added_margin = record.type_of_product_id.variance_box
                    elif 3.5 <= vol <= 5.0:
                        added_margin = record.type_of_product_id.variance_4l
                    elif vol >= 18.0:
                        added_margin = record.type_of_product_id.variance_20l

                effective_margin = base + added_margin  # Margen Base (Source)

                # Definir Extras (Deltas hacia arriba)
                # Tiers: Source(Base), Stream, Cycle, Flow, Spark(Top)
                if (0.6 <= vol <= 0.8) or (8.0 <= vol <= 9.0):
                    extras = [0.25, 0.15, 0.10, 0.05]  # [Spark, Flow, Cycle, Stream]
                elif 3.5 <= vol <= 5.0:
                    extras = [0.08, 0.06, 0.04, 0.02]
                else:
                    extras = [0.04, 0.03, 0.02, 0.01]

                def calc_price_up(c, m_target):
                    if m_target >= 0.99: m_target = 0.99
                    return c / (1.0 - m_target)

                # Calcular Tiers Ascendentes
                record.price_tier_source = calc_price_up(cost, effective_margin)  # Base
                record.price_tier_stream = calc_price_up(cost, effective_margin + extras[3])
                record.price_tier_cycle = calc_price_up(cost, effective_margin + extras[2])
                record.price_tier_flow = calc_price_up(cost, effective_margin + extras[1])
                record.price_tier_spark = calc_price_up(cost, effective_margin + extras[0])

            # --- RAMA B: MODO INTELIGENTE (TARGET PRICING) ---
            else:
                # Aquí calculamos el Tier 1 (Spark) primero y bajamos

                # --- A. CALCULO DEL TIER 1 SEGÚN ENVASE ---

                # 1. Caso 0.7L (Ya validado y obtenido en Gatekeeper)
                if abs(vol - 0.7) < 0.05:
                    tier1_price = price_ai_07

                # 2. Caso 8.4L (La Caja) -> Copia x12
                elif 8.0 <= vol <= 9.0:
                    # Usamos el precio unitario del 0.7L (Tier 1) * 12
                    tier1_price = price_ai_07 * 12.0

                # 3. Caso 4L (Galón)
                elif 3.5 <= vol <= 5.0:
                    p_ai, valid_ai = record._get_ai_suggestion(vol)
                    if valid_ai:
                        # Prioridad 1: IA Propia
                        tier1_price = p_ai
                    else:
                        # Fallback: Margen 0.7L + Varianza 4L
                        # Margen real del 0.7L (Tier 1 AI)
                        m_07 = 1.0 - (rec_07.unit_cost_sar / price_ai_07)
                        variance = record.type_of_product_id.variance_4l if record.type_of_product_id else 0.15
                        target_m = m_07 + variance
                        if target_m >= 0.99: target_m = 0.99
                        tier1_price = cost / (1.0 - target_m)

                # 4. Caso 20L (Bidón)
                elif vol >= 18.0:
                    p_ai, valid_ai = record._get_ai_suggestion(vol)

                    if valid_ai:
                        # Prioridad 1: IA Propia
                        tier1_price = p_ai
                    else:
                        # Buscar hermano de 4L para Prioridad 2
                        rec_4l = record._get_sibling_record(4.0)

                        # Validar si el hermano de 4L tiene IA válida (llamando a la funcion, NO asumiendo)
                        # Ojo: aquí _get_ai_suggestion ya valida rango y margen del 4L
                        p_ai_4l, valid_ai_4l = 0.0, False
                        if rec_4l:
                            p_ai_4l, valid_ai_4l = rec_4l._get_ai_suggestion(4.0)

                        if valid_ai_4l:
                            # Prioridad 2: Derivar de 4L
                            # Margen efectivo del 4L (usando su IA)
                            m_4l = 1.0 - (rec_4l.unit_cost_sar / p_ai_4l)

                            # Calcular el "salto" de varianza.
                            v_4l = record.type_of_product_id.variance_4l
                            v_20l = record.type_of_product_id.variance_20l
                            delta_variance = v_20l - v_4l

                            target_m = m_4l + delta_variance
                            if target_m >= 0.99: target_m = 0.99
                            tier1_price = cost / (1.0 - target_m)
                        else:
                            # Prioridad 3: Derivar de 0.7L (Fallback final)
                            m_07 = 1.0 - (rec_07.unit_cost_sar / price_ai_07)
                            variance = record.type_of_product_id.variance_20l if record.type_of_product_id else 0.20
                            target_m = m_07 + variance
                            if target_m >= 0.99: target_m = 0.99
                            tier1_price = cost / (1.0 - target_m)

                # Default (otros tamaños raros que no son 0.7, caja, 4L ni 20L)
                else:
                    base = record.type_of_product_id.base_margin_07 or 0.30
                    tier1_price = cost / (1.0 - base)

                # --- B. ASIGNACIÓN DE TIER 1 Y BAJADA (TARGET PRICING) ---

                # Asignar Tier 1 (Spark)
                record.price_tier_spark = tier1_price

                # Calcular margen real del Tier 1 obtenido para usar como ancla de bajada
                if tier1_price > 0:
                    tier1_margin = 1.0 - (cost / tier1_price)
                else:
                    tier1_margin = 0.0

                # Definir Deltas de BAJADA (cuánto restamos al margen del Tier 1)
                # Basado en la inversa de los extras tradicionales para mantener consistencia visual

                if (0.6 <= vol <= 0.8) or (8.0 <= vol <= 9.0):
                    # Tradicional subía: [0.25, 0.15, 0.10, 0.05] vs Base 0
                    # Bajada desde 0.25:
                    drops = [0.10, 0.15, 0.20, 0.25]
                    # Spark-0.10=Flow(0.15); Spark-0.15=Cycle(0.10); Spark-0.20=Stream(0.05); Spark-0.25=Source(0)
                elif 3.5 <= vol <= 5.0:
                    # Tradicional subía: [0.08, 0.06, 0.04, 0.02]
                    # Bajada desde 0.08:
                    drops = [0.02, 0.04, 0.06, 0.08]
                else:
                    # Tradicional subía: [0.04, 0.03, 0.02, 0.01]
                    # Bajada desde 0.04:
                    drops = [0.01, 0.02, 0.03, 0.04]

                def calc_price_down(c, m_top, drop):
                    target = m_top - drop
                    # FLOOR 30%: Si baja de 0.30, se queda forzosamente en 0.30
                    if target < 0.30:
                        target = 0.30
                    return c / (1.0 - target)

                record.price_tier_flow = calc_price_down(cost, tier1_margin, drops[0])
                record.price_tier_cycle = calc_price_down(cost, tier1_margin, drops[1])
                record.price_tier_stream = calc_price_down(cost, tier1_margin, drops[2])
                record.price_tier_source = calc_price_down(cost, tier1_margin, drops[3])

            # =========================================================
            # CALCULO FINAL DE METADATA (Márgenes y P/L)
            # =========================================================
            # Esto aplica para ambas ramas (para llenar los campos informativos en la vista)

            def get_meta(p, c, v):
                if p <= 0: return 0.0, 0.0
                m = 1.0 - (c / p)
                pl = p / v if v > 0 else 0.0
                return m, pl

            record.margin_tier_spark, record.pl_tier_spark = get_meta(record.price_tier_spark, cost, vol)
            record.margin_tier_flow, record.pl_tier_flow = get_meta(record.price_tier_flow, cost, vol)
            record.margin_tier_cycle, record.pl_tier_cycle = get_meta(record.price_tier_cycle, cost, vol)
            record.margin_tier_stream, record.pl_tier_stream = get_meta(record.price_tier_stream, cost, vol)
            record.margin_tier_source, record.pl_tier_source = get_meta(record.price_tier_source, cost, vol)

            # Guardamos el margen efectivo aplicado en 'base_prediction_margin'
            # En modo inteligente es Spark (Tier 1), en tradicional es Source (Base) conceptualmente,
            # pero para estandarizar guardaremos el margen del Tier 1 (Spark) si hay IA, o el calculado base si no.
            if use_smart_mode:
                record.base_prediction_margin = record.margin_tier_spark
            else:
                # En modo tradicional, el "base_prediction_margin" solía ser el margen de entrada (0.30 + var)
                # Lo mantenemos así para referencia
                base = record.type_of_product_id.base_margin_07 if record.type_of_product_id else 0.30
                add_m = 0.0
                if record.type_of_product_id and vol > 0:
                    if 8.0 <= vol <= 9.0:
                        add_m = record.type_of_product_id.variance_box
                    elif 3.5 <= vol <= 5.0:
                        add_m = record.type_of_product_id.variance_4l
                    elif vol >= 18.0:
                        add_m = record.type_of_product_id.variance_20l
                record.base_prediction_margin = base + add_m

    @api.depends('product_id', 'ai_last_updated', 'unit_cost_sar')
    def _compute_ai_predicted_price(self):
        for record in self:
            record.ai_predicted_price = 0.0
            record.ai_predicted_margin = 0.0
            record.ai_market_min = 0.0
            record.ai_market_max = 0.0

            if not record.product_id:
                continue

            suggestion = self.env['product.price.suggestion'].search([
                ('product_id_str', '=', record.product_id)
            ], limit=1, order='last_update_date desc')

            if suggestion:
                record.ai_predicted_price = suggestion.suggested_price
                record.ai_market_min = suggestion.market_min_found
                record.ai_market_max = suggestion.market_max_found

                if suggestion.suggested_price > 0:
                    current_profit = suggestion.suggested_price - record.unit_cost_sar
                    record.ai_predicted_margin = current_profit / suggestion.suggested_price

    _rec_name = 'product_name'

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, order=None, name_get_uid=None):
        if args is None:
            args = []
        domain = args[:]
        if name:
            domain = ['|',
                      '|',
                      ('product_name', operator, name),
                      ('external_id', operator, name),
                      ('product_id', operator, name)
                      ] + domain

        return self._search(domain, limit=limit, order=order, access_rights_uid=name_get_uid)

    @api.depends('volume_liters')
    def _compute_is_box_8_4(self):
        for record in self:
            # Detectar rango 8.0 - 9.0
            record.is_box_8_4 = (8.0 <= record.volume_liters <= 9.0)

    @api.onchange('dilution_recommendation_id')
    def _onchange_dilution_recommendation(self):
        """Al elegir una recomendación del dropdown, se autocompleta el campo de ml."""
        if self.dilution_recommendation_id:
            self.dilution_rate_ml = self.dilution_recommendation_id.dilution_rate_ml

    @api.depends('dilution_rate_ml', 'volume_liters',
                 'price_tier_spark', 'price_tier_flow', 'price_tier_cycle',
                 'price_tier_stream', 'price_tier_source')
    def _compute_dilution_data(self):
        for rec in self:
            # 1. Calcular el Ratio (Ej: 1000 / 20ml = 50)
            if rec.dilution_rate_ml > 0:
                rec.dilution_ratio = 1000.0 / rec.dilution_rate_ml
            else:
                rec.dilution_ratio = 0.0

            # 2. Calcular Rendimiento Total (Ej: 4L de envase * 50 de ratio = 200 Litros diluidos)
            rec.total_diluted_liters = rec.volume_liters * rec.dilution_ratio

            # 3. Calcular Precios Diluidos (Precio del Envase / Litros Totales Diluidos)
            if rec.total_diluted_liters > 0:
                rec.diluted_price_spark = rec.price_tier_spark / rec.total_diluted_liters
                rec.diluted_price_flow = rec.price_tier_flow / rec.total_diluted_liters
                rec.diluted_price_cycle = rec.price_tier_cycle / rec.total_diluted_liters
                rec.diluted_price_stream = rec.price_tier_stream / rec.total_diluted_liters
                rec.diluted_price_source = rec.price_tier_source / rec.total_diluted_liters
            else:
                rec.diluted_price_spark = 0.0
                rec.diluted_price_flow = 0.0
                rec.diluted_price_cycle = 0.0
                rec.diluted_price_stream = 0.0
                rec.diluted_price_source = 0.0
