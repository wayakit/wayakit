from odoo import models, fields, api
from odoo.exceptions import AccessError, ValidationError


class MrpBom(models.Model):
    _name = 'mrp.bom'
    _inherit = ['mrp.bom', 'plm.mask.mixin']

    product_tmpl_name = fields.Char(
        string='Product Name',
        related='product_tmpl_id.name',
        store=False,
    )

    product_tmpl_synonym = fields.Char(
        string='Product Synonym',
        related='product_tmpl_id.synonym_name',
        store=False,
    )

    is_plm_confidential_bom = fields.Boolean(
        string='Is PLM Confidential User',
        compute='_compute_is_plm_confidential_bom',
        store=False,
        default=lambda self: self.env.user.has_group(
            'plm_custom.group_plm_confidential'
        ),
    )

    ph_range = fields.Char(string='pH Range', help='E.g. 5.5 - 6.5')
    plm_color = fields.Char(string='Color', help='Color of the final product.')
    general_instructions = fields.Html(string='General Instructions')  # Html permite negritas, listas, etc.

    # NUEVOS CAMPOS: Sample Size
    sample_size = fields.Float(string='Sample Size', default=100.0, required=True)
    sample_uom_id = fields.Many2one('uom.uom', string='Sample UoM', required=True,
                                    default=lambda self: self.env.ref('uom.product_uom_gram', raise_if_not_found=False))

    def _sample_size_in_base(self):
        """Sample size as a plain number in its category's base unit: g for
        weight, mL for volume. The percentage numerator is always grams
        (0.5 % = 0.5 g per 100 of base), so this only normalizes the '100'."""
        self.ensure_one()
        gram = self.env.ref('uom.product_uom_gram', raise_if_not_found=False)
        litre = self.env.ref('uom.product_uom_litre', raise_if_not_found=False)
        uom = self.sample_uom_id
        if gram and uom.category_id == gram.category_id:
            return uom._compute_quantity(self.sample_size, gram, round=False)
        if litre and uom.category_id == litre.category_id:
            return uom._compute_quantity(
                self.sample_size, litre, round=False
            ) * 1000.0
        return self.sample_size

    @api.depends_context('uid')
    def _compute_is_plm_confidential_bom(self):
        is_confidential = self.env.user.has_group(
            'plm_custom.group_plm_confidential'
        )
        for record in self:
            record.is_plm_confidential_bom = is_confidential

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None,
                access_rights_uid=None):
        if self._is_plm_standard_user():
            domain = self._rewrite_product_tmpl_domain(domain)
        return super()._search(
            domain, offset=offset, limit=limit,
            order=order, access_rights_uid=access_rights_uid,
        )

    def _rewrite_product_tmpl_domain(self, domain):
        """
        Reescribe leaves de dominio que expondrían nombres reales a usuarios Standard.
        """
        BOM_LINE_NAME_PATHS = {
            'bom_line_ids.product_id',
            'bom_line_ids.product_id.name',
            'bom_line_ids.product_id.product_tmpl_id.name',
        }

        new_domain = []
        for leaf in domain:
            if not (
                    isinstance(leaf, (list, tuple))
                    and len(leaf) == 3
                    and isinstance(leaf[2], str)
            ):
                new_domain.append(leaf)
                continue

            field_path, operator, value = leaf[0], leaf[1], leaf[2]

            if field_path == 'product_tmpl_id':
                tmpl_domain = [
                    '|',
                    '&', ('is_plm_component', '=', True),
                    ('synonym_name', operator, value),
                    '&', ('is_plm_component', '=', False),
                    ('name', operator, value),
                ]
                tmpl_ids = self.env['product.template'].search(tmpl_domain).ids
                new_domain.append(('product_tmpl_id', 'in', tmpl_ids))

            elif field_path in BOM_LINE_NAME_PATHS:
                tmpl_domain = [
                    '|',
                    '&', ('is_plm_component', '=', True),
                    ('synonym_name', operator, value),
                    '&', ('is_plm_component', '=', False),
                    ('name', operator, value),
                ]
                tmpl_ids = self.env['product.template'].search(tmpl_domain).ids
                product_ids = self.env['product.product'].search(
                    [('product_tmpl_id', 'in', tmpl_ids)]
                ).ids
                new_domain.append(('bom_line_ids.product_id', 'in', product_ids))

            else:
                new_domain.append(leaf)

        return new_domain

    # _is_plm_standard_user() lives in plm.mask.mixin.

    def _plm_export_blocked(self):
        # A BoM IS the formula: never exportable by a Standard user.
        return True

    # ---------------------------------------------------------
    # NUEVAS RESTRICCIONES DE ESCRITURA PARA BOM (CUSTOM 2)
    # ---------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        if self._is_plm_standard_user():
            raise AccessError("PLM Restriction: Standard users are not allowed to create Bills of Materials.")
        return super().create(vals_list)

    def write(self, vals):
        if self._is_plm_standard_user():
            raise AccessError("PLM Restriction: Standard users are not allowed to edit Bills of Materials.")
        res = super().write(vals)
        # Moving the formulation basis moves every percentage-driven quantity.
        if 'sample_size' in vals or 'sample_uom_id' in vals:
            self.bom_line_ids._plm_apply_percentage()
        return res

    def unlink(self):
        if self._is_plm_standard_user():
            raise AccessError("PLM Restriction: Standard users are not allowed to delete Bills of Materials.")
        return super().unlink()


class MrpBomLine(models.Model):
    _name = 'mrp.bom.line'
    _inherit = ['mrp.bom.line', 'plm.mask.mixin']

    component_display_name = fields.Char(
        string='Component',
        compute='_compute_component_display_name',
        store=False,
    )

    component_density = fields.Float(
        string='Density (g/mL)',
        related='product_id.product_tmpl_id.density',
        readonly=True,
    )

    qty_in_grams = fields.Float(
        string='Qty (g)',
        compute='_compute_qty_in_grams',
        digits=(12, 4),
        help='Quantity in grams. Weight UoMs convert directly; volume UoMs '
             'convert to mL and multiply by the density. Any other UoM '
             '(units, length) has no gram equivalent and stays at 0.',
    )

    @api.depends('product_qty', 'product_uom_id',
                 'product_id.product_tmpl_id.density')
    def _compute_qty_in_grams(self):
        gram = self.env.ref('uom.product_uom_gram', raise_if_not_found=False)
        litre = self.env.ref('uom.product_uom_litre', raise_if_not_found=False)
        for line in self:
            uom = line.product_uom_id
            density = line.product_id.product_tmpl_id.density
            # round=False: UoM rounding defaults to 'UP' at the target unit's
            # precision (0.001 L = 1 mL), which snapped every fractional mL up
            # to the next whole mL. Formulation quantities are exact.
            if gram and uom.category_id == gram.category_id:
                line.qty_in_grams = uom._compute_quantity(
                    line.product_qty, gram, round=False
                )
            elif density and litre and uom.category_id == litre.category_id:
                qty_ml = uom._compute_quantity(
                    line.product_qty, litre, round=False
                ) * 1000.0
                line.qty_in_grams = qty_ml * density
            else:
                line.qty_in_grams = 0.0

    def _grams_to_product_uom(self, grams):
        """Inverse of _compute_qty_in_grams: grams -> quantity in the line's own
        UoM. Weight converts directly; volume divides by the density to get mL
        first. Any other UoM has no gram equivalent, so the number is returned
        untouched (previous behaviour)."""
        self.ensure_one()
        gram = self.env.ref('uom.product_uom_gram', raise_if_not_found=False)
        litre = self.env.ref('uom.product_uom_litre', raise_if_not_found=False)
        uom = self.product_uom_id
        density = self.product_id.product_tmpl_id.density
        if gram and uom.category_id == gram.category_id:
            return gram._compute_quantity(grams, uom, round=False)
        if density and litre and uom.category_id == litre.category_id:
            return litre._compute_quantity(
                grams / density / 1000.0, uom, round=False
            )
        return grams

    # 1. Nuevo campo para el porcentaje
    component_percentage = fields.Float(
        string='Percentage (%)',
        digits=(6, 4),  # Permite decimales precisos como 33.3333%
        default=0.0
    )

    # 2. No upper bound: Wayakit formulas are expressed per 100, per 1000 or on
    # another basis, so a single component (water, base) can legitimately go
    # over 100. Only a negative percentage is a real error.
    @api.constrains('component_percentage')
    def _check_component_percentage(self):
        for line in self:
            if line.component_percentage < 0.0:
                raise ValidationError("PLM Restriction: The percentage cannot be negative.")

    def _plm_percentage_qty(self):
        """product_qty implied by component_percentage, or None when the line is
        not percentage-driven. The percentage is defined on the formulation,
        which is in grams: 0.5 % = 0.5 g per 100 of sample. Resolve the grams
        FIRST, then convert to the component's own stock UoM via the density."""
        self.ensure_one()
        if self.component_percentage <= 0 or self.bom_id.sample_size <= 0:
            return None
        grams = (self.bom_id._sample_size_in_base()
                 * self.component_percentage / 100.0)
        return self._grams_to_product_uom(grams)

    def _plm_apply_percentage(self):
        """The onchange only fires in the form; BoMs are also loaded by import
        and copied by mrp.eco, so the percentage has to be resolved in the ORM."""
        for line in self:
            qty = line._plm_percentage_qty()
            if qty is not None:
                # The context stops write() from calling this back.
                line.with_context(plm_skip_percentage=True).write(
                    {'product_qty': qty}
                )

    @api.onchange('component_percentage', 'bom_id.sample_size',
                  'product_id', 'product_uom_id')
    def _onchange_component_percentage(self):
        for line in self:
            qty = line._plm_percentage_qty()
            if qty is not None:
                line.product_qty = qty

    @api.depends(
        'product_id',
        'product_id.product_tmpl_id.synonym_name',
        'product_id.product_tmpl_id.is_plm_component',
    )
    @api.depends_context('uid')
    def _compute_component_display_name(self):
        is_standard = self._is_plm_standard_user()
        for record in self:
            tmpl = record.product_id.product_tmpl_id
            is_plm = tmpl.is_plm_component
            if is_standard and is_plm and tmpl.synonym_name:
                record.component_display_name = tmpl.synonym_name
            else:
                record.component_display_name = record.product_id.display_name or ''

    # _is_plm_standard_user() lives in plm.mask.mixin.

    def _plm_export_blocked(self):
        return True

    # Restricciones para las líneas del BoM
    @api.model_create_multi
    def create(self, vals_list):
        if self._is_plm_standard_user():
            raise AccessError("PLM Restriction: Standard users cannot add components to a BoM.")
        lines = super().create(vals_list)
        # After super() on purpose: bom_id, product_uom_id and the density are
        # resolved by then, even when an import leaves them to their defaults.
        lines._plm_apply_percentage()
        return lines

    def write(self, vals):
        if self._is_plm_standard_user():
            raise AccessError("PLM Restriction: Standard users cannot edit BoM components.")
        res = super().write(vals)
        if not self.env.context.get('plm_skip_percentage') and (
            {'component_percentage', 'product_id', 'product_uom_id'} & vals.keys()
        ):
            self._plm_apply_percentage()
        return res

    def unlink(self):
        if self._is_plm_standard_user():
            raise AccessError("PLM Restriction: Standard users cannot delete BoM components.")
        return super().unlink()

