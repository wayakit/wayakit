from odoo import models, fields, api
from odoo.exceptions import AccessError, ValidationError

PLM_COMPONENT_CATEGORY = 'PLM Component'


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    synonym_name = fields.Char(
        string='Synonym Name',
        help='Anonymized/codified name shown to PLM Standard users.',
    )

    is_plm_component = fields.Boolean(
        string='Is PLM Component',
        compute='_compute_is_plm_component',
        store=True,
    )

    @api.depends('categ_id', 'categ_id.name')
    def _compute_is_plm_component(self):
        for record in self:
            record.is_plm_component = (
                record.categ_id.name == PLM_COMPONENT_CATEGORY
            )

    def _is_plm_standard_user(self):
        is_confidential = self.env.user.has_group(
            'plm_custom.group_plm_confidential'
        )
        is_standard = self.env.user.has_group(
            'plm_custom.group_plm_standard'
        )
        return is_standard and not is_confidential

    # ── Breadcrumb / display_name ──────────────────────────────────────────
    def _compute_display_name(self):
        if not self._is_plm_standard_user():
            return super()._compute_display_name()
        for record in self:
            if record.is_plm_component and record.synonym_name:
                record.display_name = record.synonym_name
            else:
                record.display_name = record.name or ''

    def name_get(self):
        if not self._is_plm_standard_user():
            return super().name_get()
        result = []
        for record in self:
            if record.is_plm_component and record.synonym_name:
                display_name = record.synonym_name
            else:
                display_name = record.name or ''
            result.append((record.id, display_name))
        return result

    # ── _name_search: autocomplete en widgets Many2one ─────────────────────
    @api.model
    def _name_search(self, name='', domain=None, operator='ilike',
                     limit=100, order=None):
        if not self._is_plm_standard_user() or not name:
            return super()._name_search(
                name=name, domain=domain, operator=operator,
                limit=limit, order=order,
            )
        base_domain = list(domain or [])
        return base_domain + [
            '|',
            '&', ('is_plm_component', '=', True),
                 ('synonym_name', operator, name),
            '&', ('is_plm_component', '=', False),
                 ('name', operator, name),
        ]

    # ── _search: intercepta TODAS las búsquedas por 'name' ────────────────
    # Es el método de más bajo nivel — se llama siempre, sin importar
    # qué vista de búsqueda esté activa ni qué RPC llega del cliente.
    @api.model
    def _search(self, domain, offset=0, limit=None, order=None,
                access_rights_uid=None):
        if self._is_plm_standard_user():
            new_domain = []
            for leaf in domain:
                if (
                    isinstance(leaf, (list, tuple))
                    and len(leaf) == 3
                    and leaf[0] == 'name'
                ):
                    # Redirige búsqueda por nombre real a sinónimo en PLM Components
                    new_domain += [
                        '|',
                        '&', ('is_plm_component', '=', True),
                             ('synonym_name', leaf[1], leaf[2]),
                        '&', ('is_plm_component', '=', False),
                             ('name', leaf[1], leaf[2]),
                    ]
                else:
                    new_domain.append(leaf)
            domain = new_domain
        return super()._search(
            domain, offset=offset, limit=limit,
            order=order, access_rights_uid=access_rights_uid,
        )

    # ── Campos computados para la vista ───────────────────────────────────
    is_plm_confidential = fields.Boolean(
        string='Is PLM Confidential User',
        compute='_compute_is_plm_confidential',
        store=False,
    )

    @api.depends_context('uid')
    def _compute_is_plm_confidential(self):
        is_confidential = self.env.user.has_group(
            'plm_custom.group_plm_confidential'
        )
        for record in self:
            record.is_plm_confidential = is_confidential

    @api.onchange('categ_id')
    def _onchange_categ_plm_confidential(self):
        self.is_plm_confidential = self.env.user.has_group(
            'plm_custom.group_plm_confidential'
        )

    display_name_plm = fields.Char(
        string='Display Name',
        compute='_compute_display_name_plm',
        store=False,
    )

    @api.depends('name', 'synonym_name', 'is_plm_component')
    @api.depends_context('uid')
    def _compute_display_name_plm(self):
        is_standard = self._is_plm_standard_user()
        for record in self:
            if is_standard and record.is_plm_component and record.synonym_name:
                record.display_name_plm = record.synonym_name
            else:
                record.display_name_plm = record.name or ''

    @api.constrains('is_plm_component', 'synonym_name')
    def _check_synonym_name_required(self):
        for record in self:
            if record.is_plm_component and not record.synonym_name:
                raise ValidationError("PLM Restriction: A Synonym Name is strictly required for PLM Components.")


class ProductTemplateSecurity(models.Model):
    _inherit = 'product.template'

    def write(self, vals):
        if self._is_plm_standard_user():
            if 'categ_id' in vals:
                new_category = self.env['product.category'].browse(vals['categ_id'])
                if new_category.name == PLM_COMPONENT_CATEGORY:
                    raise AccessError(
                        "PLM Restriction: Standard users cannot assign the 'PLM Component' category to products.")
            for record in self:
                if record.is_plm_component:
                    raise AccessError(
                        f"PLM Restriction: Standard users are not allowed to edit PLM Components ({record.display_name}).")
        return super().write(vals)

    def unlink(self):
        if self._is_plm_standard_user():
            for record in self:
                if record.is_plm_component:
                    raise AccessError(
                        f"PLM Restriction: Standard users are not allowed to delete PLM Components ({record.display_name}).")
        return super().unlink()