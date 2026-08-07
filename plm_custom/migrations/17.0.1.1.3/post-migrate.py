from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Recompute is_plm_component (stored) after the target category changed
    from 'PLM Component' to 'All / Raw material / Chemical'.

    ponytail: uses add_to_compute (the ORM's own recompute queue) instead of
    calling _compute_is_plm_component() by hand, which assigns outside the
    protected context and degrades into one write() per record.

    The folder version MUST stay <= the manifest version or Odoo silently
    skips this script (odoo/modules/migration.py, compare()). That is what
    happened on 2026-08-07: folder 17.0.1.1.1 vs manifest 17.0.1.0.2.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    templates = env['product.template'].with_context(
        active_test=False
    ).search([])
    env.add_to_compute(templates._fields['is_plm_component'], templates)
    env.flush_all()