import json

from werkzeug.datastructures import FileStorage

from odoo import _, http
from odoo.http import request

from odoo.addons.web.controllers.export import CSVExport, ExcelExport
from odoo.addons.web.controllers.pivot import TableExporter

# A formula, or one query away from one.
PLM_FORMULA_MODELS = {'mrp.bom', 'mrp.bom.line'}
PLM_PRODUCT_MODELS = {'product.template', 'product.product'}


def _denial_message():
    return _(
        "PLM Restriction: Standard users are not allowed to export formula data."
    )


def _plm_export_denied(model, ids=None, domain=None):
    """None when the export may proceed, else the refusal message.

    The ORM guard in plm.mask.mixin.export_data is the real protection -- it
    also covers a direct call_kw RPC. This exists so the HTTP routes answer a
    clean 403 instead of the 500 they would produce by letting an AccessError
    escape into their own `except Exception` wrapper.
    """
    if not model:
        return None
    env = request.env
    if not env['plm.mask.mixin']._is_plm_standard_user():
        return None
    if model in PLM_FORMULA_MODELS:
        return _denial_message()
    if model in PLM_PRODUCT_MODELS:
        records = env[model].browse(ids) if ids else env[model].search(domain or [])
        if records._plm_export_blocked():
            return _denial_message()
    return None


def _denied_from_export_payload(data):
    try:
        params = json.loads(data)
    except (TypeError, ValueError):
        # Let the core surface its own parse error rather than masking it.
        return None
    return _plm_export_denied(
        params.get('model'), params.get('ids'), params.get('domain')
    )


class PlmCSVExport(CSVExport):

    @http.route()
    def web_export_csv(self, data):
        denied = _denied_from_export_payload(data)
        if denied:
            return request.make_response(denied, status=403)
        return super().web_export_csv(data)


class PlmExcelExport(ExcelExport):

    @http.route()
    def web_export_xlsx(self, data):
        denied = _denied_from_export_payload(data)
        if denied:
            return request.make_response(denied, status=403)
        return super().web_export_xlsx(data)


class PlmTableExporter(TableExporter):

    @http.route()
    def export_xlsx(self, data, **kw):
        # /web/pivot/export_xlsx never touches the ORM: the payload carries the
        # already-rendered table, with no domain and no ids, so the model name
        # is all there is to decide on. The core route has no access check of
        # any kind -- not even base.group_allow_export.
        try:
            if isinstance(data, FileStorage):
                jdata = json.load(data)
                data.seek(0)  # the core re-reads this same stream
            else:
                jdata = json.loads(data)
        except (TypeError, ValueError):
            return super().export_xlsx(data, **kw)

        model = jdata.get('model')
        if model in PLM_FORMULA_MODELS | PLM_PRODUCT_MODELS:
            if request.env['plm.mask.mixin']._is_plm_standard_user():
                return request.make_response(_denial_message(), status=403)
        return super().export_xlsx(data, **kw)
