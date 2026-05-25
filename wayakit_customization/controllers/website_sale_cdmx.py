# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

WAYAKIT_MX_WEBSITE_NAME = 'WAYAKIT MX'
CDMX_VISIBLE_ID = 493  # Ciudad de México, CMX - único visible en el dropdown


class WebsiteSaleCDMXFilter(WebsiteSale):

    @http.route(
        ['/shop/country_infos/<model("res.country"):country>'],
        type='json',
        auth="public",
        methods=['POST'],
        website=True,
    )
    def country_infos(self, country, mode, **kw):
        """Filtra estados en el dropdown dinámico (cuando el usuario cambia el país)."""
        result = super().country_infos(country, mode, **kw)

        website = request.website
        if not website or website.name != WAYAKIT_MX_WEBSITE_NAME:
            return result

        if result.get('states'):
            result['states'] = [
                state for state in result['states']
                if state[0] == CDMX_VISIBLE_ID
            ]

        return result

    @http.route(
        ['/shop/address'],
        type='http',
        methods=['GET', 'POST'],
        auth="public",
        website=True,
        sitemap=False,
    )
    def address(self, **kw):
        """Filtra estados en el render inicial del formulario (incluyendo ?mode=billing&partner_id=X)."""
        response = super().address(**kw)

        website = request.website
        if not website or website.name != WAYAKIT_MX_WEBSITE_NAME:
            return response

        if request.httprequest.method != 'GET':
            return response

        try:
            qcontext = response.qcontext
            if qcontext and 'country_states' in qcontext:
                qcontext['country_states'] = qcontext['country_states'].filtered(
                    lambda s: s.id == CDMX_VISIBLE_ID
                )
        except AttributeError:
            pass

        return response