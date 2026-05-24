# -*- coding: utf-8 -*-
"""
Override del endpoint /shop/country_infos para filtrar los estados
devueltos al formulario de dirección, limitándolos a CDMX cuando
el website activo es 'WAYAKIT MX'.
"""

from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

WAYAKIT_MX_WEBSITE_NAME = 'WAYAKIT MX'

# IDs de todos los registros que representan CDMX en esta instancia
CDMX_STATE_IDS = {493, 1684, 1391}


class WebsiteSaleCDMXFilter(WebsiteSale):

    @http.route(
        ['/shop/country_infos/<model("res.country"):country>'],
        type='json',
        auth="public",
        methods=['POST'],
        website=True,
    )
    def country_infos(self, country, mode, **kw):
        """
        Intercepts the standard country_infos endpoint.
        When on WAYAKIT MX, filters returned states to CDMX only.
        """
        result = super().country_infos(country, mode, **kw)

        website = request.website
        if not website or website.name != WAYAKIT_MX_WEBSITE_NAME:
            return result

        # result['states'] es una lista de tuplas (id, name, code)
        if result.get('states'):
            result['states'] = [
                state for state in result['states']
                if state[0] in CDMX_STATE_IDS
            ]

        return result