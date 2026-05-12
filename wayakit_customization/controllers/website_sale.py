# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebsiteSaleCustom(WebsiteSale):

    @http.route(
        ['/shop/address'],
        type='http', methods=['GET', 'POST'],
        auth="public", website=True, sitemap=False
    )
    def address(self, **kw):
        response = super().address(**kw)

        # Solo para WAYAKIT MX
        if request.website.name != 'WAYAKIT MX':
            return response

        # Solo en POST (usuario acaba de guardar dirección)
        if request.httprequest.method == 'POST':
            if hasattr(response, 'location'):
                location = response.location
                # Si va a redirigir al checkout nativo, interceptar
                if '/shop/checkout' in location:
                    return request.redirect('/shop/checkout')

        return response