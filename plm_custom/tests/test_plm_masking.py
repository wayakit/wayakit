from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

REAL_TEXT = 'Citrus\nCitric acid'


class TestPlmMasking(TransactionCase):
    """description_picking masking on stock documents + the export guard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # is_plm_component keys on the exact complete_name, so build the chain.
        raw = cls.env['product.category'].create({
            'name': 'Raw material',
            'parent_id': cls.env.ref('product.product_category_all').id,
        })
        chemical = cls.env['product.category'].create({
            'name': 'Chemical',
            'parent_id': raw.id,
        })

        cls.component = cls.env['product.product'].create({
            'name': 'Citric acid',
            'categ_id': chemical.id,
            'synonym_name': 'Citrus',
        })
        cls.component_no_synonym = cls.env['product.product'].create({
            'name': 'Sodium chloride',
            'categ_id': chemical.id,
        })
        cls.plain_product = cls.env['product.product'].create({'name': 'Plain box'})

        groups = {
            xmlid: cls.env.ref(xmlid).id
            for xmlid in (
                'base.group_user',
                'base.group_allow_export',
                'stock.group_stock_user',
                'plm_custom.group_plm_standard',
                'plm_custom.group_plm_confidential',
            )
        }
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.standard_user = Users.create({
            'name': 'PLM Standard Tester',
            'login': 'plm_standard_tester',
            'groups_id': [(6, 0, [
                groups['base.group_user'],
                groups['base.group_allow_export'],
                groups['stock.group_stock_user'],
                groups['plm_custom.group_plm_standard'],
            ])],
        })
        # group_plm_confidential implies group_plm_standard, which is exactly
        # why _is_plm_standard_user checks "standard AND NOT confidential".
        cls.confidential_user = Users.create({
            'name': 'PLM Confidential Tester',
            'login': 'plm_confidential_tester',
            'groups_id': [(6, 0, [
                groups['base.group_user'],
                groups['base.group_allow_export'],
                groups['stock.group_stock_user'],
                groups['plm_custom.group_plm_confidential'],
            ])],
        })

        cls.bom = cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.plain_product.product_tmpl_id.id,
            'product_qty': 1.0,
        })

        cls.move = cls._make_move(cls.component)
        cls.move_no_synonym = cls._make_move(cls.component_no_synonym)
        cls.move_plain = cls._make_move(cls.plain_product)

    @classmethod
    def _make_move(cls, product):
        return cls.env['stock.move'].create({
            'name': product.name,
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': 1.0,
            'location_id': cls.env.ref('stock.stock_location_stock').id,
            'location_dest_id': cls.env.ref('stock.stock_location_customers').id,
            'description_picking': REAL_TEXT,
        })

    def _description(self, move, user):
        return move.with_user(user).read(['description_picking'])[0][
            'description_picking'
        ]

    # ── Parte A: máscara de description_picking ───────────────────────────

    def test_standard_user_sees_synonym(self):
        self.assertEqual(self._description(self.move, self.standard_user), 'Citrus')

    def test_confidential_user_sees_real_name(self):
        self.assertEqual(
            self._description(self.move, self.confidential_user), REAL_TEXT
        )

    def test_missing_synonym_blanks_instead_of_leaking(self):
        # The field's content IS the confidential name, so there is no safe
        # fallback to the real value here.
        self.assertEqual(
            self._description(self.move_no_synonym, self.standard_user), ''
        )

    def test_non_plm_product_is_untouched(self):
        self.assertEqual(
            self._description(self.move_plain, self.standard_user), REAL_TEXT
        )

    def test_search_read_is_masked(self):
        # search_read reaches _read_format WITHOUT going through read(), which
        # is why the override sits on _read_format and not on read().
        rows = self.env['stock.move'].with_user(self.standard_user).search_read(
            [('id', '=', self.move.id)], ['description_picking']
        )
        self.assertEqual(rows[0]['description_picking'], 'Citrus')

    def test_move_line_is_masked(self):
        line = self.env['stock.move.line'].create({
            'move_id': self.move.id,
            'product_id': self.component.id,
            'product_uom_id': self.component.uom_id.id,
            'location_id': self.move.location_id.id,
            'location_dest_id': self.move.location_dest_id.id,
            'description_picking': REAL_TEXT,
        })
        self.assertEqual(self._description(line, self.standard_user), 'Citrus')
        self.assertEqual(
            self._description(line, self.confidential_user), REAL_TEXT
        )

    # ── Parte B: guard de exportación ─────────────────────────────────────

    def test_export_bom_blocked_for_standard(self):
        with self.assertRaises(AccessError):
            self.bom.with_user(self.standard_user).export_data(['product_qty'])

    def test_export_bom_allowed_for_confidential(self):
        result = self.bom.with_user(self.confidential_user).export_data(
            ['product_qty']
        )
        self.assertIn('datas', result)

    def test_export_plm_component_blocked(self):
        template = self.component.product_tmpl_id.with_user(self.standard_user)
        with self.assertRaises(AccessError):
            template.export_data(['name'])

    def test_export_product_with_bom_blocked(self):
        template = self.plain_product.product_tmpl_id.with_user(self.standard_user)
        with self.assertRaises(AccessError):
            template.export_data(['name'])

    def test_export_ordinary_product_allowed(self):
        ordinary = self.env['product.product'].create({'name': 'Ordinary'})
        result = ordinary.product_tmpl_id.with_user(self.standard_user).export_data(
            ['name']
        )
        self.assertIn('datas', result)
