# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Subina (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
# -*- coding: utf-8 -*-
import logging
import pprint
import ast
import json
import requests

from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing
from odoo import http, _
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

class PaymentMyFatoorahController(http.Controller):
    """ Instance for the myfatoorah controller """

    _return_url = '/payment/myfatoorah/_return_url'
    # I just removed save_session from here it was core code
    # @http.route('/payment/myfatoorah/response', type='http', auth='public', website=True, methods=['GET'], csrf=False, save_session=False)
    # @http.route('/payment/myfatoorah/response', type='http', auth='public',
    #             website=True, methods=['POST'], csrf=False)
    # def myfatoorah_payment_response(self, **data):
    #     """Function to get the payment response"""
    #
    #     payment_data = ast.literal_eval(data["data"])
    #     vals = {
    #         'customer': payment_data["CustomerName"],
    #         'currency': payment_data["DisplayCurrencyIso"],
    #         'mobile': payment_data["CustomerMobile"],
    #         'invoice_amount': payment_data["InvoiceValue"],
    #         'address': payment_data["CustomerAddress"]["Address"],
    #         'payment_url': payment_data["InvoiceURL"],
    #     }
    #     return request.render(
    #         "myfatoorah_payment_gateway.myfatoorah_payment_gateway_form", vals)
    @http.route('/payment/myfatoorah/response', type='http', auth='public',
                website=True, methods=['POST'], csrf=False)
    def myfatoorah_payment_response(self, **data):
        """Function to get the payment response and redirect immediately"""

        # Parse the incoming data
        payment_data = ast.literal_eval(data["data"])

        # Extract the payment URL from the data
        payment_url = payment_data.get("InvoiceURL")

        if payment_url:
            # Redirect directly to the external payment page
            return request.redirect(payment_url, local=False)
        else:
            # Fallback to the failed template if no URL is present
            return request.render("myfatoorah_payment_gateway.myfatoorah_payment_gateway_failed_form")
    # It is core code i just added csrf and save_Session
    # @http.route(_return_url, type='http', auth='public', methods=['GET'])
    @http.route(_return_url, type='http', auth='public', website=True, methods=['GET'], csrf=False, save_session=True)
    def myfatoorah_checkout(self, **data):
        """ Function to redirect to the payment checkout"""
        _logger.info("Received MyFatoorah return data:\n%s",
                     pprint.pformat(data))
        tx_sudo = request.env[
            'payment.transaction'].sudo()._get_tx_from_notification_data(
            'myfatoorah', data)
        tx_sudo._handle_notification_data('myfatoorah', data)


        # My custom code starts from here
        PaymentPostProcessing.monitor_transaction(tx_sudo)
        # Restore the website order + tx in session so /payment/status and /shop/payment/validate work
        so = tx_sudo.sale_order_ids[:1]
        if so:
            request.session['sale_order_id'] = so.id
            request.session['sale_last_order_id'] = so.id

        # This key is commonly used by website_sale to track the last payment tx
        request.session['__website_sale_last_tx_id'] = tx_sudo.id

        # my custom code ends here
        return request.redirect('/payment/status')

    @http.route('/payment/myfatoorah/failed', type='http', auth='public',
                website=True)
    def payment_failed(self):
        """ Function to render the payment failed cases"""
        return request.render(
            "myfatoorah_payment_gateway.myfatoorah_payment_gateway_failed_form")

    @http.route(
        '/.well-known/apple-developer-merchantid-domain-association',
        type='http',
        auth='public',
        website=True,
        csrf=False
    )
    # Arehman's code start fo apple pay verification and apple pay button in checkout
    def apple_pay_domain_verification(self, **kwargs):
        """Serve Apple Pay domain verification file"""
        content = request.env['ir.config_parameter'].sudo().get_param(
            'myfatoorah.apple_domain_file_content', ''
        )
        return Response(content or '', content_type='text/plain')

    @http.route('/payment/myfatoorah/applepay/pay', type='json', auth='public',
                website=True, csrf=False)
    def myfatoorah_apple_pay_pay(self, **kwargs):
        """
        Called when customer clicks 'Pay with Apple Pay' button.
        Flow: Get Order → Get Provider → Get/Create Transaction → ExecutePayment → Return redirect URL
        """
        try:
            # ----------------------------------------------------------------
            # STEP 1: Get the current website sale order (shopping cart)
            # If no active cart exists, abort immediately
            # ----------------------------------------------------------------
            order = request.website.sale_get_order()
            if not order:
                return {'success': False, 'message': 'No active cart found.'}

            # ----------------------------------------------------------------
            # STEP 2: Fetch the MyFatoorah payment provider from Odoo config
            # This gives us the API token and base URL (test vs live)
            # ----------------------------------------------------------------
            provider = request.env['payment.provider'].sudo().search(
                [('code', '=', 'myfatoorah')], limit=1
            )
            if not provider or not provider.myfatoorah_token:
                return {'success': False, 'message': 'MyFatoorah provider or token missing.'}

            # ----------------------------------------------------------------
            # STEP 3: Get existing draft/pending transaction for this order
            # or create a new one if none exists.
            # This transaction tracks the payment state inside Odoo.
            # ----------------------------------------------------------------
            tx = request.env['payment.transaction'].sudo().search([
                ('provider_code', '=', 'myfatoorah'),
                ('reference', '=', order.name),
                ('state', 'in', ['draft', 'pending']),
            ], limit=1)

            if not tx:
                # ----------------------------------------------------------------
                # Odoo 17 requires payment_method_id when creating a transaction
                # Fetch the payment method linked to the MyFatoorah provider
                # ----------------------------------------------------------------
                payment_method = request.env['payment.method'].sudo().search([
                    ('provider_ids', 'in', provider.id),
                ], limit=1)

                tx = request.env['payment.transaction'].sudo().create({
                    'provider_id': provider.id,
                    'provider_code': 'myfatoorah',
                    'payment_method_id': payment_method.id,  # Required in Odoo 17
                    'reference': order.name,
                    'amount': order.amount_total,
                    'currency_id': order.currency_id.id,
                    'partner_id': order.partner_id.id,
                    'partner_name': order.partner_id.name,
                    'partner_email': order.partner_id.email,
                    'partner_phone': order.partner_id.mobile or order.partner_id.phone or '',
                    'partner_address': order.partner_id.street or '',
                    'partner_city': order.partner_id.city or '',
                    'partner_zip': order.partner_id.zip or '',
                    'partner_country_id': order.partner_id.country_id.id,
                    'partner_state_id': order.partner_id.state_id.id,
                    'operation': 'online_redirect',
                })
                # Link this transaction to the sale order
                tx.sale_order_ids = [(6, 0, [order.id])]

            # ----------------------------------------------------------------
            # STEP 4: Prepare API headers for MyFatoorah
            # Authorization uses the token stored in Odoo provider config
            # ----------------------------------------------------------------
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': f'Bearer {provider.myfatoorah_token}',
            }

            # ----------------------------------------------------------------
            # STEP 5: Build callback URLs
            # CallBackUrl → where MyFatoorah redirects after successful payment
            # ErrorUrl    → where MyFatoorah redirects if payment fails
            # ----------------------------------------------------------------
            callback_url = request.httprequest.host_url.rstrip('/') + '/payment/myfatoorah/_return_url'
            error_url = request.httprequest.host_url.rstrip('/') + '/payment/myfatoorah/failed'

            # ----------------------------------------------------------------
            # STEP 6: Clean phone number to max 11 digits (MyFatoorah requirement)
            # Strips country code, spaces, dashes, and leading + sign
            # ----------------------------------------------------------------
            raw_phone = order.partner_id.mobile or order.partner_id.phone or '0500000000'
            phone = raw_phone.replace(' ', '').replace('-', '')
            if phone.startswith('+'):
                phone = phone[1:]
            country_code = str(order.partner_id.country_id.phone_code or '')
            if country_code and phone.startswith(country_code):
                phone = phone[len(country_code):]
            phone = phone[-11:]  # MyFatoorah max length is 11 digits

            # ----------------------------------------------------------------
            # STEP 7: Build ExecutePayment payload
            # PaymentMethodId 11 = Apple Pay (confirmed from InitiatePayment logs)
            # We skip InitiatePayment entirely since we already know the ID
            # ----------------------------------------------------------------
            execute_payload = {
                "PaymentMethodId": 11,  # Apple Pay method ID (code: 'ap')
                "CustomerName": tx.partner_name or "Customer",
                "DisplayCurrencyIso": tx.currency_id.name,
                "MobileCountryCode": country_code or '966',
                "CustomerMobile": phone,
                "CustomerEmail": tx.partner_email or '',
                "InvoiceValue": tx.amount,
                "CallBackUrl": callback_url,
                "ErrorUrl": error_url,
                "Language": "en",
                "CustomerReference": tx.reference,
                "SourceInfo": "Odoo Website Apple Pay",
            }

            # ----------------------------------------------------------------
            # STEP 8: Call MyFatoorah ExecutePayment API
            # This creates the invoice on MyFatoorah side and returns a PaymentURL
            # provider._myfatoorah_get_api_url() returns:
            #   → https://apitest.myfatoorah.com/ (if provider state = Test)
            #   → https://api-sa.myfatoorah.com/ (if provider state = Live)
            # ----------------------------------------------------------------
            execute_url = f"{provider._myfatoorah_get_api_url()}v2/ExecutePayment"
            response = requests.post(execute_url, headers=headers,
                                     json=execute_payload, timeout=30)

            _logger.info("ExecutePayment raw response: %s", response.text)

            response.raise_for_status()
            result = response.json()

            # ----------------------------------------------------------------
            # STEP 9: Check if MyFatoorah successfully created the invoice
            # ----------------------------------------------------------------
            if not result.get('IsSuccess'):
                return {
                    'success': False,
                    'message': result.get('Message') or 'ExecutePayment failed.'
                }

            # ----------------------------------------------------------------
            # STEP 10: Extract the PaymentURL from the response
            # This is the MyFatoorah hosted page where Apple Pay sheet opens
            # JS will redirect the customer to this URL
            # ----------------------------------------------------------------
            invoice_url = result.get('Data', {}).get('PaymentURL')
            if not invoice_url:
                return {'success': False, 'message': 'No PaymentURL returned.'}

            # ----------------------------------------------------------------
            # STEP 11: Mark transaction as pending in Odoo and commit
            # Then return the URL to frontend JS which does window.location.href
            # ----------------------------------------------------------------
            request.env.cr.commit()

            return {'success': True, 'redirect_url': invoice_url}

        except Exception as e:
            _logger.exception("Apple Pay payment failed: %s", e)
            return {'success': False, 'message': str(e)}

    @http.route('/payment/myfatoorah/applepay/register_domain', type='json', auth='user', website=True, csrf=False)
    def register_apple_pay_domain(self, **kwargs):
        provider = request.env['payment.provider'].sudo().search([('code', '=', 'myfatoorah')], limit=1)

        if not provider or not provider.myfatoorah_token:
            _logger.error("MyFatoorah Apple Pay: Provider or Token missing.")
            return {'success': False, 'message': 'Provider or Token missing.'}

        raw_domain = kwargs.get('domain_name') or request.httprequest.host
        domain_name = raw_domain.split('//')[-1].split(':')[0].split('/')[0].lower().strip()

        url = f"{provider._myfatoorah_get_api_url()}v2/RegisterApplePayDomain"
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {provider.myfatoorah_token}',
        }
        payload = {"DomainName": domain_name}

        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()

            # LOGIC: Check if the API returned a failure
            if not result.get('IsSuccess'):
                # This logs the specific reason MyFatoorah rejected the domain
                error_msg = result.get('Message') or result.get('ValidationErrors') or 'Unknown API Error'
                _logger.error(
                    "MyFatoorah Apple Pay Registration Failed for domain [%s]. Reason: %s",
                    domain_name, error_msg
                )
            else:
                _logger.info("MyFatoorah Apple Pay: Domain [%s] registered successfully.", domain_name)

        except requests.exceptions.RequestException as e:
            _logger.error("MyFatoorah Apple Pay: Connection error during registration: %s", str(e))
            return {'success': False, 'message': f'API Connection Error: {str(e)}'}
        except Exception as e:
            _logger.error("MyFatoorah Apple Pay: Unexpected error: %s", str(e))
            return {'success': False, 'message': 'Invalid response from MyFatoorah'}

        return {
            'success': result.get('IsSuccess', False),
            'result': result,
            'domain_sent': domain_name
        }