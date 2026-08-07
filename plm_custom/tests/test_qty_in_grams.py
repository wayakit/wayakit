from odoo.tests.common import TransactionCase


class TestQtyInGrams(TransactionCase):
    """Covers the three branches of mrp.bom.line._compute_qty_in_grams."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        finished = cls.env['product.product'].create({'name': 'Test finished'})
        cls.bom = cls.env['mrp.bom'].create({
            'product_tmpl_id': finished.product_tmpl_id.id,
            'product_qty': 1.0,
        })

    def _grams(self, uom_xmlid, qty, density=0.0):
        uom = self.env.ref(uom_xmlid)
        component = self.env['product.product'].create({
            'name': 'Test component',
            'uom_id': uom.id,
            'uom_po_id': uom.id,
            'density': density,
        })
        line = self.env['mrp.bom.line'].create({
            'bom_id': self.bom.id,
            'product_id': component.id,
            'product_qty': qty,
            'product_uom_id': uom.id,
        })
        return line.qty_in_grams

    def test_qty_in_grams(self):
        # Weight: direct conversion, density irrelevant.
        self.assertAlmostEqual(self._grams('uom.product_uom_gram', 5.0), 5.0)
        self.assertAlmostEqual(self._grams('uom.product_uom_kgm', 0.5), 500.0)
        # Volume: converted to mL, then multiplied by density.
        self.assertAlmostEqual(
            self._grams('uom.product_uom_litre', 1.0, density=1.05), 1050.0
        )
        # Volume without density, and UoMs with no gram equivalent.
        self.assertAlmostEqual(self._grams('uom.product_uom_litre', 1.0), 0.0)
        self.assertAlmostEqual(self._grams('uom.product_uom_unit', 2.0), 0.0)
