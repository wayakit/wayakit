from odoo.exceptions import ValidationError
from odoo.tests import Form
from odoo.tests.common import TransactionCase


class TestComponentPercentage(TransactionCase):
    """The percentage is defined on the formulation, which is in grams:
    0.5 % = 0.5 g per 100 of sample. Only afterwards is that gram figure
    converted to the component's own stock UoM through the density."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gram = cls.env.ref('uom.product_uom_gram')
        cls.kg = cls.env.ref('uom.product_uom_kgm')
        cls.unit = cls.env.ref('uom.product_uom_unit')
        # Odoo core ships no mL; this database defines its own (factor 1000).
        cls.ml = cls.env['uom.uom'].create({
            'name': 'mL (test)',
            'category_id': cls.env.ref('uom.product_uom_categ_vol').id,
            'factor': 1000.0,
            'uom_type': 'smaller',
            'rounding': 0.001,
        })
        finished = cls.env['product.product'].create({'name': 'Test finished'})
        cls.bom = cls.env['mrp.bom'].create({
            'product_tmpl_id': finished.product_tmpl_id.id,
            'product_qty': 1.0,
        })
        # Crown: the component from the ticket. mL in stock, density 0.9.
        cls.crown = cls.env['product.product'].create({
            'name': 'Crown (test)',
            'uom_id': cls.ml.id,
            'uom_po_id': cls.ml.id,
            'density': 0.9,
        })

    def _component(self, uom, density=0.0):
        return self.env['product.product'].create({
            'name': 'Test component',
            'uom_id': uom.id,
            'uom_po_id': uom.id,
            'density': density,
        })

    def _line(self, product, **vals):
        """Create a BoM line the way an import does: no product_qty."""
        return self.env['mrp.bom.line'].create(dict(
            {'bom_id': self.bom.id, 'product_id': product.id}, **vals
        ))

    # -- the ticket ------------------------------------------------------

    def test_crown_half_percent(self):
        """0.5 % of Crown = 0.5 g per 100, NOT 0.5 mL converted to 0.45 g."""
        line = self._line(self.crown, component_percentage=0.5)
        self.assertAlmostEqual(line.product_qty, 0.5 / 0.9, places=4)
        self.assertAlmostEqual(line.qty_in_grams, 0.5, places=4)

    def test_crown_five_percent(self):
        """The live case: line 4587 held 5 mL / 4.5 g; it must be 5 g."""
        line = self._line(self.crown, component_percentage=5.0)
        self.assertAlmostEqual(line.product_qty, 5 / 0.9, places=4)
        self.assertAlmostEqual(line.qty_in_grams, 5.0, places=4)

    def test_round_trip_is_the_acceptance_criterion(self):
        """qty_in_grams must give the percentage back, whatever the UoM."""
        for uom, density in ((self.ml, 0.9), (self.ml, 1.1),
                             (self.gram, 0.0), (self.kg, 1.665)):
            for pct in (0.5, 5.0, 33.3333):
                line = self._line(self._component(uom, density),
                                  component_percentage=pct)
                self.assertAlmostEqual(
                    line.qty_in_grams, pct,  # sample base is 100 g
                    places=3,
                    msg=f'{pct} % of a {uom.name} component (density {density})',
                )

    # -- the import path (the onchange never fires there) -----------------

    def test_create_without_product_qty(self):
        """How the new BoMs arrive: a percentage and no quantity at all."""
        line = self._line(self.crown, component_percentage=5.0)
        self.assertAlmostEqual(line.product_qty, 5 / 0.9, places=4)

    def test_create_overrides_an_imported_qty(self):
        """The percentage owns the quantity; a stale imported one loses."""
        line = self._line(self.crown, component_percentage=5.0, product_qty=999)
        self.assertAlmostEqual(line.product_qty, 5 / 0.9, places=4)

    def test_write_percentage(self):
        line = self._line(self.crown, component_percentage=5.0)
        line.write({'component_percentage': 10.0})
        self.assertAlmostEqual(line.product_qty, 10 / 0.9, places=4)
        self.assertAlmostEqual(line.qty_in_grams, 10.0, places=3)

    def test_write_sample_size_recomputes_lines(self):
        line = self._line(self._component(self.gram), component_percentage=5.0)
        self.assertAlmostEqual(line.product_qty, 5.0, places=4)
        self.bom.write({'sample_size': 200.0})
        self.assertAlmostEqual(line.product_qty, 10.0, places=4)

    def test_write_product_switches_density(self):
        line = self._line(self.crown, component_percentage=5.0)
        denser = self._component(self.ml, 1.25)
        line.write({'product_id': denser.id, 'product_uom_id': self.ml.id})
        self.assertAlmostEqual(line.product_qty, 5 / 1.25, places=4)

    # -- no regressions ---------------------------------------------------

    def test_weight_component_unaffected(self):
        """Component UoM already matches the formulation: no density involved."""
        line = self._line(self._component(self.gram, 1.01),
                          component_percentage=100.0)
        self.assertAlmostEqual(line.product_qty, 100.0, places=4)
        self.assertAlmostEqual(line.qty_in_grams, 100.0, places=4)

    def test_line_without_percentage_keeps_its_qty(self):
        """How the old BoMs work: an explicit quantity, no percentage."""
        line = self._line(self.crown, product_qty=7.0)
        self.assertAlmostEqual(line.product_qty, 7.0)

    def test_uom_with_no_gram_equivalent(self):
        line = self._line(self._component(self.unit), component_percentage=5.0)
        self.assertAlmostEqual(line.product_qty, 5.0)
        self.assertAlmostEqual(line.qty_in_grams, 0.0)

    # -- the rounding bug this fix depends on ------------------------------

    def test_fractional_ml_is_not_rounded_up(self):
        """UoM conversion defaults to rounding UP at 1 mL: 0.1 mL read as
        0.9 g instead of 0.09 g. Without round=False the criterion above
        cannot hold."""
        line = self._line(self.crown, product_qty=0.1)
        self.assertAlmostEqual(line.qty_in_grams, 0.09, places=4)
        line.write({'product_qty': 1.4})
        self.assertAlmostEqual(line.qty_in_grams, 1.26, places=4)

    # -- formulation basis -------------------------------------------------

    def test_sample_uom_is_normalised(self):
        """A 1 kg sample is a 1000 g basis, not a 1 g one."""
        self.bom.write({'sample_size': 1.0, 'sample_uom_id': self.kg.id})
        line = self._line(self._component(self.gram), component_percentage=5.0)
        self.assertAlmostEqual(line.product_qty, 50.0, places=4)

    def test_percentage_over_100_is_allowed(self):
        """Formulas are expressed per 100, per 1000 or on another basis, so a
        base component can legitimately go over 100."""
        line = self._line(self._component(self.gram), component_percentage=900.0)
        self.assertAlmostEqual(line.qty_in_grams, 900.0, places=3)

    def test_negative_percentage_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._line(self._component(self.gram), component_percentage=-1.0)

    # -- the form path -----------------------------------------------------

    def test_onchange_in_the_form(self):
        """Assert before saving, so this covers the onchange and not create()."""
        with Form(self.bom) as bom_form:
            with bom_form.bom_line_ids.new() as line_form:
                line_form.product_id = self.crown
                line_form.component_percentage = 5.0
                self.assertAlmostEqual(line_form.product_qty, 5 / 0.9, places=3)
