from odoo import models, fields, api
from odoo.exceptions import AccessError, ValidationError


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

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

    def _is_plm_standard_user(self):
        is_confidential = self.env.user.has_group(
            'plm_custom.group_plm_confidential'
        )
        is_standard = self.env.user.has_group(
            'plm_custom.group_plm_standard'
        )
        return is_standard and not is_confidential

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
        return super().write(vals)

    def unlink(self):
        if self._is_plm_standard_user():
            raise AccessError("PLM Restriction: Standard users are not allowed to delete Bills of Materials.")
        return super().unlink()


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

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
        help='Quantity converted to grams: volume in mL x density. '
             'Only computed for lines whose UoM is a volume.',
    )

    @api.depends('product_qty', 'product_uom_id',
                 'product_id.product_tmpl_id.density')
    def _compute_qty_in_grams(self):
        litre = self.env.ref('uom.product_uom_litre', raise_if_not_found=False)
        for line in self:
            density = line.product_id.product_tmpl_id.density
            if (
                density
                and litre
                and line.product_uom_id.category_id == litre.category_id
            ):
                qty_ml = line.product_uom_id._compute_quantity(
                    line.product_qty, litre
                ) * 1000.0
                line.qty_in_grams = qty_ml * density
            else:
                line.qty_in_grams = 0.0

    # 1. Nuevo campo para el porcentaje
    component_percentage = fields.Float(
        string='Percentage (%)',
        digits=(6, 4),  # Permite decimales precisos como 33.3333%
        default=0.0
    )

    # 2. Restricción estricta de 0 a 100
    @api.constrains('component_percentage')
    def _check_component_percentage(self):
        for line in self:
            if line.component_percentage < 0.0 or line.component_percentage > 100.0:
                raise ValidationError("PLM Restriction: The percentage must be between 0 and 100.")

    @api.onchange('component_percentage', 'bom_id.sample_size')
    def _onchange_component_percentage(self):
        for line in self:
            if line.component_percentage > 0 and line.bom_id.sample_size > 0:
                # Calcula la cantidad real basada en el Sample Size
                line.product_qty = (line.bom_id.sample_size * line.component_percentage) / 100.0

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

    def _is_plm_standard_user(self):
        is_confidential = self.env.user.has_group(
            'plm_custom.group_plm_confidential'
        )
        is_standard = self.env.user.has_group(
            'plm_custom.group_plm_standard'
        )
        return is_standard and not is_confidential

    # Restricciones para las líneas del BoM
    @api.model_create_multi
    def create(self, vals_list):
        if self._is_plm_standard_user():
            raise AccessError("PLM Restriction: Standard users cannot add components to a BoM.")
        return super().create(vals_list)

    def write(self, vals):
        if self._is_plm_standard_user():
            raise AccessError("PLM Restriction: Standard users cannot edit BoM components.")
        return super().write(vals)

    def unlink(self):
        if self._is_plm_standard_user():
            raise AccessError("PLM Restriction: Standard users cannot delete BoM components.")
        return super().unlink()

