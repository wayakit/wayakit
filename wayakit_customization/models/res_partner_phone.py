# -*- coding: utf-8 -*-
import re
from odoo import api, models

_WHITESPACE_RE = re.compile(r"\s+", flags=re.UNICODE)

class ResPartner(models.Model):
    _inherit = "res.partner"

    @staticmethod
    def _strip_all_spaces(value):
        # Removes spaces, tabs, NBSP, etc. Keeps +, digits, parentheses, dashes, etc.
        # (so we don't unexpectedly change other formatting/validation behavior)
        return _WHITESPACE_RE.sub("", value) if isinstance(value, str) and value else value

    def _sanitize_phone_vals(self, vals):
        vals = dict(vals or {})
        for field in ("phone", "mobile"):
            if field in vals and vals[field]:
                vals[field] = self._strip_all_spaces(vals[field])
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._sanitize_phone_vals(v) for v in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        vals = self._sanitize_phone_vals(vals)
        return super().write(vals)
