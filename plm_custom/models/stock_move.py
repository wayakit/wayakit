from odoo import models


def _mask_description_picking(records, rows, fnames):
    """Replace the real chemical name with the synonym in already-read rows.

    `description_picking` is a stored Text that purchase writes at move creation
    from product.description_purchase, so it carries the vendor's real chemical
    name ("Citrus\\nCitric acid") on every WH/IN receipt. Masking display_name
    does nothing for it -- the string is already in the database.

    No synonym means an empty string, never the real name: unlike a product's
    display_name, the content of this field IS the confidential name, so falling
    back to it would defeat the whole point.
    """
    if 'description_picking' not in fnames:
        return rows
    if not records._is_plm_standard_user():
        return rows
    # Work off the ids that actually came back: _read_format empties vals for
    # records that vanished mid-read, and touching product_id on those would
    # raise MissingError.
    present = [vals for vals in rows if vals.get('id')]
    if not present:
        return rows
    masked = {}
    for rec in records.browse([vals['id'] for vals in present]):
        tmpl = rec.product_id.product_tmpl_id
        if tmpl.is_plm_component:
            masked[rec.id] = tmpl.synonym_name or ''
    for vals in present:
        if vals['id'] in masked:
            vals['description_picking'] = masked[vals['id']]
    return rows


class StockMove(models.Model):
    # _read_format, not read(): odoo/models.py says read() "is not supposed to
    # be overridden", and search_read() reaches _read_format without going
    # through it. Views (web_search_read -> web_read -> read), read() and
    # search_read() all converge here.
    _inherit = ['stock.move', 'plm.mask.mixin']

    def _read_format(self, fnames, load='_classic_read'):
        rows = super()._read_format(fnames, load=load)
        return _mask_description_picking(self, rows, fnames)


class StockMoveLine(models.Model):
    _inherit = ['stock.move.line', 'plm.mask.mixin']

    def _read_format(self, fnames, load='_classic_read'):
        rows = super()._read_format(fnames, load=load)
        return _mask_description_picking(self, rows, fnames)

    # ponytail: description_picking is still reachable through export_data on
    # stock.move/stock.move.line, which reads fields directly and never calls
    # _read_format. Blocking those models outright would break legitimate
    # inventory exports; if it has to be closed, mask inside _export_rows.
