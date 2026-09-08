from odoo import _, models
from odoo.exceptions import AccessError


class PlmMaskMixin(models.AbstractModel):
    """Shared PLM confidentiality helpers.

    Mixed into every model that either masks a chemical name or must refuse to
    export one. `_is_plm_standard_user` used to be copy-pasted verbatim in
    product.template, product.product, mrp.bom and mrp.bom.line; it lives here
    now so stock.move and stock.move.line don't make it six copies.
    """

    _name = 'plm.mask.mixin'
    _description = 'PLM Masking Mixin'

    def _is_plm_standard_user(self):
        is_confidential = self.env.user.has_group(
            'plm_custom.group_plm_confidential'
        )
        is_standard = self.env.user.has_group(
            'plm_custom.group_plm_standard'
        )
        return is_standard and not is_confidential

    def _plm_export_blocked(self):
        """True when exporting THIS recordset would leak a formula.

        Overridden per model. The default refuses nothing, so mixing the helper
        into a model just to reuse `_is_plm_standard_user` never turns into an
        accidental export block.
        """
        return False

    def export_data(self, fields_to_export):
        # The single server-side chokepoint. /web/export/csv and /web/export/xlsx
        # both reach it through ExportFormat.base -- the plain branch directly
        # and the grouped branch via GroupsTreeNode.insert_leaf -- and it is a
        # public method, so a direct call_kw RPC lands here too. Same pattern as
        # mail.message.export_data in the core.
        if self._is_plm_standard_user() and self._plm_export_blocked():
            raise AccessError(_(
                "PLM Restriction: Standard users are not allowed to export "
                "formula data."
            ))
        return super().export_data(fields_to_export)
