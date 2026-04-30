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

    # ── Override mandatory fields ──────────────────────────────────────
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
        config = self._get_onepage_config()  # Retrieve the custom onepage configuration
        if not config:  # If no custom config exists
            return super().checkout(**post)  # Fall back to the standard Odoo checkout method

        order_sudo = request.website.sale_get_order()  # Get the current sale order from the session
        if not order_sudo:  # If there is no active cart
            return request.redirect('/shop')  # Send the user back to the shop page

        request.session['sale_last_order_id'] = order_sudo.id  # Store the order ID in the session for reference
        redirection = self.checkout_redirection(
            order_sudo)  # Check if Odoo requires any specific redirection (e.g., empty cart)
        if redirection:  # If a redirection is needed
            return redirection  # Execute the redirect

        if order_sudo._is_public_order():  # If the user is a guest (public user)
            return request.redirect('/shop/address?callback=/shop/checkout')  # Force them to fill an address first

        redirection = self.checkout_check_address(
            order_sudo)  # Validate that the existing order has necessary address info
        if redirection:  # If address validation fails
            return redirection  # Redirect to the address fix page

        if post.get('xhr'):  # If the request is an AJAX call (XMLHTTPRequest)
            return 'ok'  # Return a simple success message

        order_sudo._recompute_taxes()  # Recalculate taxes to ensure totals are accurate before payment
        request.website.sale_get_order(
            update_pricelist=True)  # Refresh the pricelist to apply any active discounts/promotions

        if not order_sudo.only_services and not order_sudo.carrier_id:  # If the order needs shipping and no carrier is set
            order_sudo._check_carrier_quotation()  # Attempt to auto-select a default delivery carrier

        # Get standard values
        values = self.checkout_values(order_sudo,
                                      **post)  # Collect standard template variables (shippings, billings, etc.)

        # ─── COUNTRY FILTER LOGIC FOR SAVED CARDS ───
        current_company = request.env.company  # Access the current company record
        if current_company.filter_website_addresses and current_company.allowed_country_id:  # Check if our custom filter is active
            allowed_cid = current_company.allowed_country_id.id  # Get the database ID of the allowed country
            if values.get('shippings'):  # If there is a list of shipping addresses
                # Keep only addresses where the country ID matches our restricted country
                values['shippings'] = [p for p in values['shippings'] if p.country_id.id == allowed_cid]
            if values.get('billings'):  # If there is a list of billing addresses
                # Keep only addresses where the country ID matches our restricted country
                values['billings'] = [p for p in values['billings'] if p.country_id.id == allowed_cid]
        # ─────────────────────────────────────────────

        payment_values = self._get_shop_payment_values(order_sudo, **post)  # Get standard payment provider data
        values.update(payment_values)  # Merge payment data into our template values dictionary

        values.setdefault('deliveries',
                          request.env['delivery.carrier'])  # Ensure deliveries variable exists to avoid template errors
        values.setdefault('delivery_has_storable', False)  # Ensure storable check variable exists
        values['display_submit_button'] = False  # Hide standard submit button (Onepage uses its own)
        values['submit_button_label'] = _("Pay now")  # Set the text for the final payment button
        values['config'] = config  # Pass our onepage config to the frontend template

        open_panel = post.get('open_panel', 'billing')  # Determine which accordion panel should be open by default
        if open_panel not in ('billing', 'shipping'):  # Validation for the panel name
            open_panel = 'billing'  # Default back to billing if invalid
        values['open_panel'] = open_panel  # Pass the panel state to the template

        return request.render('website_onepage_checkout.onepage_checkout',
                              values)  # Render the custom Onepage Checkout template

    # ── Override Address Form (Country Dropdown restriction) ──────────
    @http.route(['/shop/address'], type='http', methods=['GET', 'POST'], auth="public", website=True, sitemap=False)
    def address(self, **kw):
        response = super(WebsiteSaleOnepage, self).address(**kw)  # Call the original Odoo address method
        if hasattr(response,
                   'qcontext'):  # Check if the response is a rendered page (has context) rather than a redirect
            current_company = request.env.company  # Get current company settings
            if current_company.filter_website_addresses and current_company.allowed_country_id:  # If filtering is active
                allowed_country = current_company.allowed_country_id  # Get the restricted country record

                # Force dropdown to show ONLY the allowed country
                response.qcontext['countries'] = allowed_country  # Limit the country dropdown list to just this one
                response.qcontext[
                    'states'] = allowed_country.state_ids  # Limit states/provinces to those within that country
                response.qcontext['country_id'] = allowed_country.id  # Pre-select the allowed country in the form
        return response  # Return the modified (or original) response

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