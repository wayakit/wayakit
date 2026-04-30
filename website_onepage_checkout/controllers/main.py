from odoo import http, _
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebsiteSaleOnepage(WebsiteSale):

    def _get_onepage_config(self):
        Config = request.env['onepage.checkout.config'].sudo()
        website = request.website
        config = Config.search([
            ('is_active', '=', True),
            ('for_all_website', '=', False),
            ('website_id', '=', website.id),
        ], limit=1)
        if not config:
            config = Config.search([
                ('is_active', '=', True),
                ('for_all_website', '=', True),
            ], limit=1)
        return config

    # ── Override Mandatory Fields ──────────────────────────────────────
    def _get_mandatory_fields_billing(self, country_id=False):
        config = self._get_onepage_config()
        if not config or not config.wk_billing_required:
            return super()._get_mandatory_fields_billing(country_id)
        req = list(config.wk_billing_required.mapped('field_name'))
        if country_id:
            country = request.env['res.country'].browse(country_id)
            if country.state_required and 'state_id' not in req:
                req.append('state_id')
            if country.zip_required and 'zip' not in req:
                req.append('zip')
        return req

    def _get_mandatory_fields_shipping(self, country_id=False):
        config = self._get_onepage_config()
        if not config or not config.wk_shipping_required:
            return super()._get_mandatory_fields_shipping(country_id)
        req = list(config.wk_shipping_required.mapped('field_name'))
        if country_id:
            country = request.env['res.country'].browse(country_id)
            if country.state_required and 'state_id' not in req:
                req.append('state_id')
            if country.zip_required and 'zip' not in req:
                req.append('zip')
        return req

    # ── Main Checkout Logic ───────────────────────────────────────────
    @http.route()
    def checkout(self, **post):
        config = self._get_onepage_config()
        if not config:
            return super().checkout(**post)

        order_sudo = request.website.sale_get_order()
        if not order_sudo:
            return request.redirect('/shop')

        request.session['sale_last_order_id'] = order_sudo.id
        redirection = self.checkout_redirection(order_sudo)
        if redirection:
            return redirection

        if order_sudo._is_public_order():
            return request.redirect('/shop/address?callback=/shop/checkout')

        redirection = self.checkout_check_address(order_sudo)
        if redirection:
            return redirection

        if post.get('xhr'):
            return 'ok'

        order_sudo._recompute_taxes()
        request.website.sale_get_order(update_pricelist=True)

        if not order_sudo.only_services and not order_sudo.carrier_id:
            order_sudo._check_carrier_quotation()

        # Get initial template values
        values = self.checkout_values(order_sudo, **post)

        # ─── WEBSITE LEVEL COUNTRY FILTER ───
        # Logic: If current website has the filter active, remove addresses not matching the country
        current_web = request.website
        if current_web.filter_website_addresses and current_web.allowed_country_ids:
            allowed_ids = current_web.allowed_country_ids.ids
            if values.get('shippings'):
                values['shippings'] = [p for p in values['shippings'] if p.country_id.id in allowed_ids]
            if values.get('billings'):
                values['billings'] = [p for p in values['billings'] if p.country_id.id in allowed_ids]

        payment_values = self._get_shop_payment_values(order_sudo, **post)
        values.update(payment_values)

        values.setdefault('deliveries', request.env['delivery.carrier'])
        values.setdefault('delivery_has_storable', False)
        values['display_submit_button'] = False
        values['submit_button_label'] = _("Pay now")
        values['config'] = config

        open_panel = post.get('open_panel', 'billing')
        if open_panel not in ('billing', 'shipping'):
            open_panel = 'billing'
        values['open_panel'] = open_panel

        return request.render('website_onepage_checkout.onepage_checkout', values)

    # ── Override Address Form ─────────────────────────────────────────
    @http.route(['/shop/address'], type='http', methods=['GET', 'POST'], auth="public", website=True, sitemap=False)
    def address(self, **kw):
        response = super(WebsiteSaleOnepage, self).address(**kw)
        if hasattr(response, 'qcontext'):
            current_web = request.website
            # Logic: Force the country dropdown to show only the selected country from Website settings
            if current_web.filter_website_addresses and current_web.allowed_country_ids:
                allowed_countries = current_web.allowed_country_ids
                response.qcontext['countries'] = allowed_countries
                response.qcontext['states'] = allowed_countries.mapped('state_ids')
                if len(allowed_countries) == 1:
                    response.qcontext['country_id'] = allowed_countries.id
        return response

    # ── AJAX Methods ──────────────────────────────────────────────────
    @http.route('/shop/onepage/select_address', type='json', auth='public', website=True)
    def onepage_select_address(self, partner_id, address_type='billing', **kw):
        order = request.website.sale_get_order()
        if not order:
            return {'error': _('No active order found.')}
        partner = request.env['res.partner'].sudo().browse(int(partner_id))
        if not partner.exists():
            return {'error': _('Address not found.')}
        if address_type == 'billing':
            order.partner_invoice_id = partner.id
        else:
            order.partner_shipping_id = partner.id
        order._recompute_taxes()
        return {'success': True, 'partner_id': partner.id}

    @http.route('/shop/onepage/get_totals', type='json', auth='public', website=True)
    def onepage_get_totals(self, **kw):
        order = request.website.sale_get_order()
        if not order: return {'error': 'No order'}
        if not order.only_services:
            order._check_carrier_quotation()
        order._recompute_taxes()
        Monetary = request.env['ir.qweb.field.monetary']
        fmt = lambda val: Monetary.value_to_html(val, {'display_currency': order.currency_id})
        lines = [{'id': l.id, 'qty': int(l.product_uom_qty), 'price_html': fmt(l.price_subtotal)}
                 for l in order.order_line if not l.is_delivery]
        return {
            'lines': lines,
            'delivery_html': fmt(order.amount_delivery) if order.carrier_id else '',
            'subtotal_html': fmt(order.amount_untaxed),
            'taxes_html': fmt(order.amount_tax),
            'total_html': fmt(order.amount_total),
            'has_delivery': bool(order.carrier_id),
        }