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

    # ── Override mandatory fields based on config ──────────────────────
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

    # @http.route()
    # def checkout(self, **post):
    #     config = self._get_onepage_config()
    #     if not config:
    #         return super().checkout(**post)
    #
    #     order_sudo = request.website.sale_get_order()
    #     if not order_sudo:
    #         return request.redirect('/shop')
    #     request.session['sale_last_order_id'] = order_sudo.id
    #
    #     redirection = self.checkout_redirection(order_sudo)
    #     if redirection:
    #         return redirection
    #
    #     if order_sudo._is_public_order():
    #         return request.redirect('/shop/address?callback=/shop/checkout')
    #
    #     redirection = self.checkout_check_address(order_sudo)
    #     if redirection:
    #         return redirection
    #
    #     if post.get('xhr'):
    #         return 'ok'
    #
    #     # ── Replicate native /shop/confirm_order + /shop/payment logic ──
    #     # 1. Recompute taxes (native confirm_order does this)
    #     order_sudo._recompute_taxes()
    #
    #     # 2. Update pricelist (native confirm_order does this)
    #     request.website.sale_get_order(update_pricelist=True)
    #
    #     # 3. Auto-select delivery carrier if not set (native shop_payment does this)
    #     if not order_sudo.only_services and not order_sudo.carrier_id:
    #         order_sudo._check_carrier_quotation()
    #
    #     # ── Collect template values ──────────────────────────────────────
    #     values = self.checkout_values(order_sudo, **post)
    #
    #     # _get_shop_payment_values already populates:
    #     # - payment_methods_sudo, tokens_sudo, errors
    #     # - deliveries, delivery_has_storable (when enabled_delivery)
    #     # - transaction_route, landing_route, access_token
    #     payment_values = self._get_shop_payment_values(order_sudo, **post)
    #     values.update(payment_values)
    #
    #     # Ensure delivery variables exist even when delivery is disabled
    #     values.setdefault('deliveries', request.env['delivery.carrier'])
    #     values.setdefault('delivery_has_storable', False)
    #
    #     # Payment button is rendered OUTSIDE payment.form (native pattern)
    #     values['display_submit_button'] = False
    #     values['submit_button_label'] = _("Pay now")
    #
    #     values['config'] = config
    #     open_panel = post.get('open_panel', 'billing')
    #     if open_panel not in ('billing', 'shipping'):
    #         open_panel = 'billing'
    #     values['open_panel'] = open_panel
    #
    #     return request.render(
    #         'website_onepage_checkout.onepage_checkout', values,
    #     )

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

        # 1. Collect standard template values
        values = self.checkout_values(order_sudo, **post)

        # 2. Apply custom filtering logic based on Company settings
        current_company = request.env.company
        if current_company.filter_website_addresses and current_company.allowed_address_company_id:
            allowed_id = current_company.allowed_address_company_id.id

            # Filter the 'shippings' list
            if values.get('shippings'):
                values['shippings'] = [
                    p for p in values['shippings']
                    if p.parent_id.id == allowed_id or p.id == allowed_id
                ]

            # Filter the 'billings' list
            if values.get('billings'):
                values['billings'] = [
                    p for p in values['billings']
                    if p.parent_id.id == allowed_id or p.id == allowed_id
                ]

        # Continue with the rest of your existing logic...
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

        return request.render(
            'website_onepage_checkout.onepage_checkout', values,
        )
    # ── AJAX: select an existing address without page-reload ─────────
    @http.route(
        '/shop/onepage/select_address',
        type='json', auth='public', website=True,
    )
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

        # Recompute taxes at order level (not line level)
        order._recompute_taxes()

        return {
            'success': True,
            'partner_id': partner.id,
        }

    # ── AJAX: get formatted order totals for inline update ───────────
    @http.route(
        '/shop/onepage/get_totals',
        type='json', auth='public', website=True,
    )
    def onepage_get_totals(self, **kw):
        order = request.website.sale_get_order()
        if not order:
            return {'error': 'No order'}

        # Native _cart_update removes delivery line on every qty change.
        # Re-add it by recalculating the carrier quotation.
        if not order.only_services:
            order._check_carrier_quotation()

        # Ensure taxes are fresh before returning values
        order._recompute_taxes()

        Monetary = request.env['ir.qweb.field.monetary']
        fmt = lambda val: Monetary.value_to_html(
            val, {'display_currency': order.currency_id},
        )

        lines = []
        for line in order.order_line:
            if not line.is_delivery:
                lines.append({
                    'id': line.id,
                    'qty': int(line.product_uom_qty),
                    'price_html': fmt(line.price_subtotal),
                })

        return {
            'lines': lines,
            'delivery_html': fmt(order.amount_delivery) if order.carrier_id else '',
            'subtotal_html': fmt(order.amount_untaxed),
            'taxes_html': fmt(order.amount_tax),
            'total_html': fmt(order.amount_total),
            'has_delivery': bool(order.carrier_id),
        }

    @http.route(['/shop/address'], type='http', methods=['GET', 'POST'], auth="public", website=True, sitemap=False)
    def address(self, **kw):
        response = super(WebsiteSaleOnepage, self).address(**kw)

        current_company = request.env.company
        # If filtering is active, we force the parent_id in the template values
        if current_company.filter_website_addresses and current_company.allowed_address_company_id:
            if 'partner_id' not in response.qcontext:  # It's a new address
                response.qcontext['parent_id'] = current_company.allowed_address_company_id.id

        return response

    def _checkout_form_save(self, mode, checkout, all_values):
        current_company = request.env.company

        # If your filter is ON, we force the parent_id into the save dictionary
        if current_company.filter_website_addresses and current_company.allowed_address_company_id:
            checkout['parent_id'] = current_company.allowed_address_company_id.id

        # Now we let Odoo save the record with our 'parent_id' included
        return super(WebsiteSaleOnepage, self)._checkout_form_save(mode, checkout, all_values)