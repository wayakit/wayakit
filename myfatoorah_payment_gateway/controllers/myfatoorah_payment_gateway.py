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
import logging
import pprint
# I imported this library
from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing

from odoo import http
from odoo.http import request
import ast

_logger = logging.getLogger(__name__)


class PaymentMyFatoorahController(http.Controller):
    """ Instance for the myfatoorah controller """

    _return_url = '/payment/myfatoorah/_return_url'
    # I just removed save_session from here it was core code
    # @http.route('/payment/myfatoorah/response', type='http', auth='public', website=True, methods=['GET'], csrf=False, save_session=False)
    @http.route('/payment/myfatoorah/response', type='http', auth='public',
                website=True, methods=['POST'], csrf=False)
    def myfatoorah_payment_response(self, **data):
        """Function to get the payment response"""

        payment_data = ast.literal_eval(data["data"])
        vals = {
            'customer': payment_data["CustomerName"],
            'currency': payment_data["DisplayCurrencyIso"],
            'mobile': payment_data["CustomerMobile"],
            'invoice_amount': payment_data["InvoiceValue"],
            'address': payment_data["CustomerAddress"]["Address"],
            'payment_url': payment_data["InvoiceURL"],
        }
        return request.render(
            "myfatoorah_payment_gateway.myfatoorah_payment_gateway_form", vals)
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

    @http.route('/payment/myfatoorah/failed', type='http', auth='user',
                website=True, )
    def payment_failed(self):
        """ Function to render the payment failed cases"""
        return request.render(
            "myfatoorah_payment_gateway.myfatoorah_payment_gateway_failed_form")
