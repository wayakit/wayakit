from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Recompute is_plm_component: the target category changed from
    'PLM Component' to 'All / Raw Materials / Chemical'."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    templates = env['product.template'].with_context(
        active_test=False
    ).search([])
    templates._compute_is_plm_component()
    templates.flush_model(['is_plm_component'])
