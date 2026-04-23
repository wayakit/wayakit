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
    @http.route('/payment/myfatoorah/response', type='http', auth='public',
                website=True, methods=['POST'], csrf=False)
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
        """Create Apple Pay payment URL and return it to JS."""
        try:
            order = request.website.sale_get_order()
            if not order:
                return {'success': False, 'message': _('No active cart found.')}

            provider = request.env['payment.provider'].sudo().search(
                [('code', '=', 'myfatoorah')], limit=1
            )
            if not provider:
                return {'success': False, 'message': _('MyFatoorah provider not found.')}

            if not provider.myfatoorah_token:
                return {'success': False, 'message': _('MyFatoorah token is missing.')}

            tx = request.env['payment.transaction'].sudo().search([
                ('provider_code', '=', 'myfatoorah'),
                ('reference', '=', order.name),
                ('state', 'in', ['draft', 'pending']),
            ], limit=1)

            if not tx:
                tx = request.env['payment.transaction'].sudo().create({
                    'provider_id': provider.id,
                    'provider_code': 'myfatoorah',
                    'reference': order.name,
                    'amount': order.amount_total,
                    'currency_id': order.currency_id.id,
                    'partner_id': order.partner_id.id,
                    'partner_name': order.partner_id.name,
                    'partner_email': order.partner_id.email,
                    'partner_phone': order.partner_id.mobile or order.partner_id.phone,
                    'partner_address': order.partner_id.street,
                    'partner_city': order.partner_id.city,
                    'partner_zip': order.partner_id.zip,
                    'partner_country_id': order.partner_id.country_id.id,
                    'partner_state_id': order.partner_id.state_id.id,
                    'operation': 'online_redirect',
                })
                tx.sale_order_ids = [(6, 0, [order.id])]

            mobile_country_code = str(order.partner_id.country_id.phone_code or '')
            phone_number = order.partner_id.mobile or order.partner_id.phone or ''

            if phone_number:
                phone_number = phone_number.replace(' ', '')
                if phone_number.startswith('+'):
                    phone_number = phone_number[1:]
                if mobile_country_code and phone_number.startswith(mobile_country_code):
                    phone_number = phone_number[len(mobile_country_code):]
                if len(phone_number) > 11:
                    phone_number = phone_number[-11:]

            initiate_url = f"{provider._myfatoorah_get_api_url()}v2/InitiatePayment"
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': f'Bearer {provider.myfatoorah_token}',
            }

            initiate_payload = json.dumps({
                "InvoiceAmount": tx.amount,
                "CurrencyIso": tx.currency_id.name,
            })

            initiate_response = requests.post(
                initiate_url, headers=headers, data=initiate_payload, timeout=60
            )

            _logger.info("InitiatePayment status code: %s", initiate_response.status_code)
            _logger.info("InitiatePayment response text: %s", initiate_response.text)

            initiate_response.raise_for_status()
            initiate_data = initiate_response.json()

            _logger.info("MyFatoorah InitiatePayment response:\n%s", pprint.pformat(initiate_data))

            if not initiate_data.get('IsSuccess'):
                return {
                    'success': False,
                    'message': initiate_data.get('Message') or _('InitiatePayment failed.')
                }

            methods = initiate_data.get('Data') or []
            if isinstance(methods, dict):
                methods = methods.get('PaymentMethods', [])

            apple_method_id = False
            for method in methods:
                name_en = (method.get('PaymentMethodEn') or '').strip().lower()
                name_ar = (method.get('PaymentMethodAr') or '').strip().lower()
                if 'apple' in name_en or 'apple' in name_ar:
                    apple_method_id = method.get('PaymentMethodId')
                    break

            if not apple_method_id:
                return {'success': False, 'message': _('Apple Pay method not found in MyFatoorah.')}

            callback_url = request.httprequest.host_url.rstrip('/') + self._return_url
            error_url = request.httprequest.host_url.rstrip('/') + '/payment/myfatoorah/failed'

            execute_url = f"{provider._myfatoorah_get_api_url()}v2/ExecutePayment"
            execute_payload = {
                "PaymentMethodId": apple_method_id,
                "CustomerName": tx.partner_name or "Website Customer",
                "DisplayCurrencyIso": tx.currency_id.name,
                "MobileCountryCode": mobile_country_code or "966",
                "CustomerMobile": phone_number,
                "CustomerEmail": tx.partner_email or "",
                "InvoiceValue": tx.amount,
                "CallBackUrl": callback_url,
                "ErrorUrl": error_url,
                "Language": "en",
                "CustomerReference": tx.reference,
                "CustomerAddress": {
                    "Address": "%s ,%s %s ,%s ,%s" % (
                        tx.partner_address or '',
                        tx.partner_city or '',
                        tx.partner_zip or '',
                        tx.partner_state_id.name if tx.partner_state_id else '',
                        tx.partner_country_id.name if tx.partner_country_id else '',
                    ),
                },
                "SourceInfo": "Odoo Website Apple Pay",
            }

            execute_response = requests.post(
                execute_url,
                headers=headers,
                data=json.dumps(execute_payload),
                timeout=60
            )
            execute_response.raise_for_status()
            execute_data = execute_response.json()

            _logger.info("MyFatoorah ExecutePayment response:\n%s", pprint.pformat(execute_data))

            if not execute_data.get('IsSuccess'):
                return {
                    'success': False,
                    'message': execute_data.get('Message') or _('ExecutePayment failed.')
                }

            invoice_url = execute_data.get('Data', {}).get('InvoiceURL')
            if not invoice_url:
                return {'success': False, 'message': _('MyFatoorah did not return InvoiceURL.')}

            tx._set_pending()
            request.env.cr.commit()

            return {
                'success': True,
                'redirect_url': invoice_url,
            }

        except Exception as e:
            _logger.exception("Apple Pay creation failed: %s", e)
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