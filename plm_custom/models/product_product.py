from odoo import models, api


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _is_plm_standard_user(self):
        is_confidential = self.env.user.has_group(
            'plm_custom.group_plm_confidential'
        )
        is_standard = self.env.user.has_group(
            'plm_custom.group_plm_standard'
        )
        return is_standard and not is_confidential

    @staticmethod
    def _build_display_name(name, default_code):
        if default_code:
            return f'[{default_code}] {name}'
        return name

    def _compute_display_name(self):
        if not self._is_plm_standard_user():
            return super()._compute_display_name()
        for record in self:
            tmpl = record.product_tmpl_id
            if tmpl.is_plm_component and tmpl.synonym_name:
                name = tmpl.synonym_name
            else:
                name = record.name or ''
            record.display_name = self._build_display_name(
                name, record.default_code
            )

    def name_get(self):
        if not self._is_plm_standard_user():
            return super().name_get()
        result = []
        for record in self:
            tmpl = record.product_tmpl_id
            if tmpl.is_plm_component and tmpl.synonym_name:
                name = tmpl.synonym_name
            else:
                name = record.name or ''
            display_name = self._build_display_name(name, record.default_code)
            result.append((record.id, display_name))
        return result

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike',
                     limit=100, order=None):
        if not self._is_plm_standard_user() or not name:
            return super()._name_search(
                name=name, domain=domain, operator=operator,
                limit=limit, order=order,
            )
        search_domain = list(domain or []) + [
            '|',
            '|',
            ('default_code', operator, name),
            '&', ('product_tmpl_id.is_plm_component', '=', True),
                 ('product_tmpl_id.synonym_name', operator, name),
            '&', ('product_tmpl_id.is_plm_component', '=', False),
                 ('name', operator, name),
        ]
        return self._search(search_domain, limit=limit, order=order)