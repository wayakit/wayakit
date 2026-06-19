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
    # @http.route(_return_url, type='http', auth='public', website=True, methods=['GET'], csrf=False, save_session=True)
    # def myfatoorah_checkout(self, **data):
    #     """ Function to redirect to the payment checkout"""
    #     _logger.info("Received MyFatoorah return data:\n%s",
    #                  pprint.pformat(data))
    #     tx_sudo = request.env[
    #         'payment.transaction'].sudo()._get_tx_from_notification_data(
    #         'myfatoorah', data)
    #     tx_sudo._handle_notification_data('myfatoorah', data)
    #
    #
    #     # My custom code starts from here
    #     PaymentPostProcessing.monitor_transaction(tx_sudo)
    #     # Restore the website order + tx in session so /payment/status and /shop/payment/validate work
    #     so = tx_sudo.sale_order_ids[:1]
    #     if so:
    #         request.session['sale_order_id'] = so.id
    #         request.session['sale_last_order_id'] = so.id
    #
    #     # This key is commonly used by website_sale to track the last payment tx
    #     request.session['__website_sale_last_tx_id'] = tx_sudo.id
    #
    #     # my custom code ends here
    #     return request.redirect('/payment/status')
    @http.route(_return_url, type='http', auth='public', website=True,
                methods=['GET'], csrf=False, save_session=True)
    def myfatoorah_checkout(self, **data):
        """Function to redirect to the payment checkout"""
        _logger.info("Received MyFatoorah return data:\n%s", pprint.pformat(data))

        try:
            tx_sudo = request.env['payment.transaction'].sudo() \
                ._get_tx_from_notification_data('myfatoorah', data)

            # ── Restore session BEFORE handling notification ──────────────────
            so = tx_sudo.sale_order_ids[:1]
            if so:
                request.session['sale_order_id'] = so.id
                request.session['sale_last_order_id'] = so.id
                request.session['__website_sale_last_tx_id'] = tx_sudo.id
                # This prevents website_sale from creating a new empty cart
                request.session['sale_order_id'] = so.id

            tx_sudo._handle_notification_data('myfatoorah', data)
            PaymentPostProcessing.monitor_transaction(tx_sudo)

            # ── Restore session AGAIN after handling (double safety) ──────────
            if so:
                request.session['sale_order_id'] = so.id
                request.session['sale_last_order_id'] = so.id
                request.session['__website_sale_last_tx_id'] = tx_sudo.id

            _logger.info(
                "MyFatoorah: TX %s state=%s, Order %s restored in session",
                tx_sudo.reference, tx_sudo.state, so.name if so else 'N/A'
            )

        except Exception as e:
            _logger.exception("MyFatoorah return URL error: %s", e)
            return request.redirect('/payment/myfatoorah/failed')

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

    @http.route('/payment/myfatoorah/applepay/check', type='json', auth='public',
                website=True, csrf=False)
    def myfatoorah_apple_pay_check(self, **kwargs):
        """Check if Apple Pay should be shown on the current website.
        Returns True only if a MyFatoorah provider exists for the same company as this website."""
        website = request.website
        provider = request.env['payment.provider'].sudo().search([
            ('code', '=', 'myfatoorah'),
            ('company_id', '=', website.company_id.id),
            ('state', 'in', ['enabled', 'test']),
        ], limit=1)
        return {'show': bool(provider)}

    @http.route('/payment/myfatoorah/applepay/pay', type='json', auth='public',
                website=True, csrf=False)
    def myfatoorah_apple_pay_pay(self, **kwargs):
        """
        Called when customer clicks 'Pay with Apple Pay' button.
        Flow: Get Order → Get Provider → Cancel stale TX → Create fresh TX
              → InitiatePayment (get real Apple Pay ID for SAR)
              → ExecutePayment → Return redirect URL
        """
        try:
            # ----------------------------------------------------------------
            # STEP 1: Get the current website sale order (shopping cart)
            # ----------------------------------------------------------------
            order = request.website.sale_get_order()
            if not order:
                return {'success': False, 'message': 'No active cart found.'}

            if not order.amount_total or order.amount_total <= 0:
                return {'success': False, 'message': 'Order amount is zero or invalid.'}

            # Force SAR — this is a Saudi-only Apple Pay integration
            currency_iso = order.currency_id.name  # Should be 'SAR'
            invoice_amount = round(order.amount_total, 2)

            _logger.info(
                "Apple Pay: Order=%s | Amount=%s | Currency=%s",
                order.name, invoice_amount, currency_iso
            )

            # ----------------------------------------------------------------
            # STEP 2: Fetch the MyFatoorah payment provider for this website's company
            # ----------------------------------------------------------------
            provider = request.env['payment.provider'].sudo().search(
                [('code', '=', 'myfatoorah'),
                 ('company_id', '=', request.website.company_id.id)], limit=1
            )
            if not provider or not provider.myfatoorah_token:
                return {'success': False, 'message': 'MyFatoorah provider or token missing.'}

            # ----------------------------------------------------------------
            # STEP 3: Cancel ALL existing draft/pending transactions for this
            # order to avoid stale amount/currency bugs
            # ----------------------------------------------------------------
            stale_txs = request.env['payment.transaction'].sudo().search([
                ('provider_code', '=', 'myfatoorah'),
                ('sale_order_ids', 'in', order.id),
                ('state', 'in', ['draft', 'pending']),
            ])
            if stale_txs:
                stale_txs.write({'state': 'cancel'})
                _logger.info("Apple Pay: Cancelled %d stale transaction(s) for order %s",
                             len(stale_txs), order.name)

            # ----------------------------------------------------------------
            # STEP 4: Create a fresh transaction with correct amount + currency
            # ----------------------------------------------------------------
            payment_method = request.env['payment.method'].sudo().search([
                ('provider_ids', 'in', provider.id),
            ], limit=1)

            # Generate a unique reference to avoid duplicate conflicts
            import uuid
            unique_ref = f"{order.name}-AP-{uuid.uuid4().hex[:6].upper()}"

            tx = request.env['payment.transaction'].sudo().create({
                'provider_id': provider.id,
                'provider_code': 'myfatoorah',
                'payment_method_id': payment_method.id,
                'reference': unique_ref,
                'amount': invoice_amount,  # Always fresh from order
                'currency_id': order.currency_id.id,  # Always from order
                'partner_id': order.partner_id.id,
                'partner_name': order.partner_id.name,
                'partner_email': order.partner_id.email or '',
                'partner_phone': order.partner_id.mobile or order.partner_id.phone or '',
                'partner_address': order.partner_id.street or '',
                'partner_city': order.partner_id.city or '',
                'partner_zip': order.partner_id.zip or '',
                'partner_country_id': order.partner_id.country_id.id,
                'partner_state_id': order.partner_id.state_id.id if order.partner_id.state_id else False,
                'operation': 'online_redirect',
            })
            tx.sale_order_ids = [(6, 0, [order.id])]

            _logger.info(
                "Apple Pay: Created TX ref=%s amount=%s currency=%s",
                tx.reference, tx.amount, tx.currency_id.name
            )

            # ----------------------------------------------------------------
            # STEP 5: API headers
            # ----------------------------------------------------------------
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': f'Bearer {provider.myfatoorah_token}',
            }

            base_url = provider._myfatoorah_get_api_url()  # ends with /

            # ----------------------------------------------------------------
            # STEP 6: Call InitiatePayment to get the REAL Apple Pay method ID
            # for SAR — never hardcode this ID, it differs per account/currency
            # ----------------------------------------------------------------
            initiate_payload = {
                "InvoiceAmount": invoice_amount,
                "CurrencyIso": currency_iso,  # "SAR"
            }
            initiate_resp = requests.post(
                f"{base_url}v2/InitiatePayment",
                headers=headers,
                json=initiate_payload,
                timeout=30
            )
            initiate_resp.raise_for_status()
            initiate_result = initiate_resp.json()

            _logger.info("InitiatePayment response: %s", initiate_result)

            if not initiate_result.get('IsSuccess'):
                return {
                    'success': False,
                    'message': initiate_result.get('Message') or 'InitiatePayment failed.'
                }

            # Find Apple Pay method (code = 'ap') from the returned list
            payment_methods = initiate_result.get('Data', {}).get('PaymentMethods', [])
            apple_pay_method = next(
                (m for m in payment_methods if m.get('PaymentMethodCode', '').lower() == 'ap'),
                None
            )

            if not apple_pay_method:
                _logger.error(
                    "Apple Pay not available for currency %s. Available methods: %s",
                    currency_iso,
                    [(m.get('PaymentMethodCode'), m.get('PaymentMethodId')) for m in payment_methods]
                )
                return {
                    'success': False,
                    'message': f'Apple Pay is not available for currency {currency_iso}.'
                }

            apple_pay_method_id = apple_pay_method['PaymentMethodId']
            _logger.info(
                "Apple Pay method ID for %s = %s", currency_iso, apple_pay_method_id
            )

            # ----------------------------------------------------------------
            # STEP 7: Clean phone number — max 11 digits, Saudi default
            # ----------------------------------------------------------------
            raw_phone = order.partner_id.mobile or order.partner_id.phone or '0500000000'
            phone = raw_phone.replace(' ', '').replace('-', '').replace('+', '')
            # Strip country code prefix if present
            mobile_country_code = str(order.partner_id.country_id.phone_code or '966')
            if phone.startswith(mobile_country_code):
                phone = phone[len(mobile_country_code):]
            phone = phone[-11:]  # Max 11 digits

            # ----------------------------------------------------------------
            # STEP 8: Build callback URLs
            # ----------------------------------------------------------------
            host = request.httprequest.host_url.rstrip('/')
            callback_url = f"{host}/payment/myfatoorah/_return_url"
            error_url = f"{host}/payment/myfatoorah/failed"

            # ----------------------------------------------------------------
            # STEP 9: ExecutePayment with the dynamically resolved method ID
            # ----------------------------------------------------------------
            execute_payload = {
                "PaymentMethodId": apple_pay_method_id,  # Dynamic — not hardcoded
                "CustomerName": tx.partner_name or order.partner_id.name or "Customer",
                "DisplayCurrencyIso": currency_iso,  # SAR
                "MobileCountryCode": mobile_country_code,  # e.g. "966"
                "CustomerMobile": phone,
                "CustomerEmail": tx.partner_email or '',
                "InvoiceValue": invoice_amount,  # Always from order.amount_total
                "CallBackUrl": callback_url,
                "ErrorUrl": error_url,
                "Language": "en",
                "CustomerReference": tx.reference,
                "SourceInfo": "Odoo Website Apple Pay",
            }

            _logger.info("ExecutePayment payload: %s", execute_payload)

            execute_resp = requests.post(
                f"{base_url}v2/ExecutePayment",
                headers=headers,
                json=execute_payload,
                timeout=30
            )

            _logger.info("ExecutePayment raw response: %s", execute_resp.text)

            execute_resp.raise_for_status()
            result = execute_resp.json()

            # ----------------------------------------------------------------
            # STEP 10: Validate response
            # ----------------------------------------------------------------
            if not result.get('IsSuccess'):
                return {
                    'success': False,
                    'message': result.get('Message') or 'ExecutePayment failed.'
                }

            invoice_url = result.get('Data', {}).get('PaymentURL')
            if not invoice_url:
                return {'success': False, 'message': 'No PaymentURL returned from MyFatoorah.'}

            # ----------------------------------------------------------------
            # STEP 11: Store MyFatoorah invoice ID on transaction for webhook
            # matching, then commit and return redirect URL to frontend JS
            # ----------------------------------------------------------------
            mf_invoice_id = result.get('Data', {}).get('InvoiceId')
            if mf_invoice_id:
                tx.sudo().write({'provider_reference': str(mf_invoice_id)})

            request.env.cr.commit()

            _logger.info(
                "Apple Pay: Success. TX=%s | InvoiceId=%s | URL=%s",
                tx.reference, mf_invoice_id, invoice_url
            )

            return {
                'success': True,
                'redirect_url': invoice_url,
                'order_id': order.id,
                'order_name': order.name,
            }

        except requests.exceptions.Timeout:
            _logger.error("Apple Pay: MyFatoorah API timeout")
            return {'success': False, 'message': 'Payment gateway timed out. Please try again.'}

        except requests.exceptions.RequestException as e:
            _logger.exception("Apple Pay: API request failed: %s", e)
            return {'success': False, 'message': 'Could not connect to payment gateway.'}

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