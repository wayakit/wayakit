# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

WAYAKIT_MX_WEBSITE_NAME = 'WAYAKIT MX'
CDMX_VISIBLE_ID = 493  # Ciudad de México, CMX - único visible en el dropdown


class WebsiteSaleCustom(WebsiteSale):

    @http.route(
        ['/shop/address'],
        type='http', methods=['GET', 'POST'],
        auth="public", website=True, sitemap=False
    )
    def address(self, **kw):
        response = super().address(**kw)

        if request.website.name != WAYAKIT_MX_WEBSITE_NAME:
            return response

        # Solo en POST: interceptar redirección al checkout
        if request.httprequest.method == 'POST':
            if hasattr(response, 'location'):
                if '/shop/checkout' in response.location:
                    return request.redirect('/shop/checkout')

        return response

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

        if not request.website or request.website.name != WAYAKIT_MX_WEBSITE_NAME:
            return result

        if result.get('states'):
            result['states'] = [
                state for state in result['states']
                if state[0] == CDMX_VISIBLE_ID
            ]

        return result

    def _get_country_related_render_values(self, kw, render_values):
        """Filtra estados en el render inicial del formulario (incluyendo ?mode=billing&partner_id=X)."""
        res = super()._get_country_related_render_values(kw, render_values)

        if not request.website or request.website.name != WAYAKIT_MX_WEBSITE_NAME:
            return res

        res['country_states'] = res['country_states'].filtered(
            lambda s: s.id == CDMX_VISIBLE_ID
        )

        return res