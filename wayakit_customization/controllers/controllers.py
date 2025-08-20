# from odoo import http
# import json
#
# from odoo.http import request
#
#
# class Odoo17Crack(http.Controller):
#     @http.route('/api/services/availableslots', methods=['POST'], type='json', csrf=False, auth="public")
#     def available_slots(self, **post):
#         # Extract data from the request body
#         service_id = 8
#
#         extras_ids = ["3680", "3681"]
#
#         appointment_type_id = request.env['appointment.type'].sudo().search([
#             ('id', '=', service_id),
#         ])
#         if appointment_type_id & appointment_type_id.product_id:
#
#             product_varients_ids = appointment_type_id.product_id.product_variant_ids.search([('id', 'in', extras_ids)])
#             totalduration = appointment_type_id.appointment_duration * 60
#             for product in product_varients_ids:
#                 totalduration += product.duration
#             totalduration = totalduration / 60
#             total = appointment_type_id.appointment_duration
#             appointment_type_id.appointment_duration = totalduration
#             tinmezone = 'Asia/Karachi'
#             slots = appointment_type_id._get_appointment_slots(
#                 tinmezone,
#             )
#             appointment_type_id.appointment_duration = total
#             # Structure the response
#             response = {
#                 "availableslots": slots
#             }
#
#             return response

from odoo import http, fields
from odoo.http import request
from odoo.addons.appointment.controllers.appointment import AppointmentController
import re


class CustomAppointmentController(AppointmentController):

    def _handle_appointment_form_submission(
            self, appointment_type,
            date_start, date_end, duration,
            description, answer_input_values, name, customer, appointment_invite, guests=None,
            staff_user=None, asked_capacity=1, booking_line_values=None
    ):
        # First create the sale order (if logged in)
        sale_order = False
        if not request.env.user._is_public():
            sale_order = self._create_appointment_sale_order(
                appointment_type,
                customer,
                answer_input_values
            )

        # Call original method to create calendar event
        result = super()._handle_appointment_form_submission(
            appointment_type, date_start, date_end, duration,
            description, answer_input_values, name, customer, appointment_invite, guests,
            staff_user, asked_capacity, booking_line_values
        )

        # Link sale order to event if created
        if sale_order:
            event_token = result.location.split('/')[-1].split('?')[0]
            event = request.env['calendar.event'].sudo().search(
                [('access_token', '=', event_token)],
                limit=1
            )
            if event:
                event.sale_order_id = sale_order.id

        return result

    def _create_appointment_sale_order(self, appointment_type, customer, answer_input_values):
        """Create a sale order from appointment data with proper product matching"""
        # Find the service question and selected answer
        service_question, selected_answer = self._find_service_selection(answer_input_values)
        if not (service_question and selected_answer):
            return False

        # Find matching product based on answer
        product = self._find_matching_product(selected_answer.name)
        if not product:
            return False

        # Create the sales order
        order_vals = {
            'partner_id': customer.id,
            'user_id': request.env.user.id,
            'date_order': fields.Datetime.now(),
            'origin': f"Appointment: {appointment_type.name}",
            'order_line': [(0, 0, {
                'product_id': product.id,
                'name': product.name,
                'product_uom_qty': 1,
                'price_unit': product.list_price,
            })]
        }

        return request.env['sale.order'].sudo().create(order_vals)

    def _find_service_selection(self, answer_input_values):
        """Find the service selection question and answer"""
        for answer in answer_input_values:
            question = request.env['appointment.question'].browse(answer['question_id'])
            if 'service' in question.name.lower() and question.question_type == 'select':
                return (
                    question,
                    request.env['appointment.answer'].browse(answer['value_answer_id'])
                )
        return (None, None)

    def _find_matching_product(self, answer_name):
        """Match the appointment answer to an existing product"""
        # Clean and parse the answer text
        service_type = self._extract_service_type(answer_name)
        vehicle_type = self._extract_vehicle_type(answer_name)

        if not service_type or not vehicle_type:
            return None

        # Search for matching product
        domain = [
            ('name', 'ilike', vehicle_type),
            ('name', 'ilike', service_type),
            ('type', '=', 'service')
        ]

        return request.env['product.product'].sudo().search(domain, limit=1)

    def _extract_service_type(self, answer_name):
        """Extract service type from answer (e.g., 'Exterior', 'Interior')"""
        answer_name = answer_name.lower()
        if 'exterior' in answer_name and 'interior' in answer_name:
            return 'Exterior & Interior'
        elif 'exterior' in answer_name:
            return 'Exterior'
        elif 'interior' in answer_name:
            return 'Interior'
        return None

    def _extract_vehicle_type(self, answer_name):
        """Extract vehicle type from answer (e.g., 'SUV', 'Sedan')"""
        vehicle_types = ['suv', 'sedan', 'golfcart', 'motorcycle']
        answer_name = answer_name.lower()
        for v_type in vehicle_types:
            if v_type in answer_name:
                return v_type.capitalize()
        return None
