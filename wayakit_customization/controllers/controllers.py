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

import logging
from datetime import timedelta

from odoo import http, fields
from odoo.http import request
from odoo.addons.appointment.controllers.appointment import AppointmentController
import re

_logger = logging.getLogger(__name__)


class CustomAppointmentController(AppointmentController):

    # Only these two service variants should override the appointment
    # duration and force a 2-hour booking. Any other product (or no
    # product match at all) keeps the original appointment_type
    # duration / date_end untouched.
    DURATION_OVERRIDE_PRODUCT_CODES = [
        'FP-CWS-00102',  # Car Wash Sedan [Exterior & Interior Deep cleaning]
        'FP-CWS-00202',  # Car Wash SUV [Exterior & Interior Deep cleaning]
    ]

    def _handle_appointment_form_submission(
            self, appointment_type,
            date_start, date_end, duration,
            description, answer_input_values, name, customer, appointment_invite, guests=None,
            staff_user=None, asked_capacity=1, booking_line_values=None
    ):
        # Create customer contact from form data and sales order
        sale_order = False
        customer_partner = self._create_or_update_customer_partner(name, description)
        # Resolve the selected service product once; reused for both the sale
        # order and the duration override below
        product = self._get_selected_service_product(appointment_type, answer_input_values)

        if customer_partner:
            # Check appointment type and handle accordingly
            if appointment_type.name.lower() == "curtain and furniture care":
                sale_order = self._create_curtain_furniture_sale_order(
                    appointment_type,
                    customer_partner,
                    answer_input_values
                )
            elif product:
                # For Car Wash Care and other types, use the existing logic
                sale_order = self._create_appointment_sale_order(
                    appointment_type,
                    customer_partner,  # Use the created/updated customer
                    product
                )

        # Only the two configured service variants (by internal reference
        # code) force the appointment to a fixed 2-hour slot. Any other
        # product, or no product match, leaves duration/date_end exactly as
        # passed in (i.e. the original appointment type duration).
        if product and product.default_code in self.DURATION_OVERRIDE_PRODUCT_CODES:
            duration = 2
            date_end = date_start + timedelta(hours=2)

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

    def _create_or_update_customer_partner(self, name, description):
        """Create or update customer partner from form data"""
        try:
            # Extract email and phone from description (HTML format)
            email = phone = None

            # Parse the description HTML to extract email and phone
            if description and '<ul>' in description:
                # Example description format:
                # <ul><li>Phone: +1234567890</li><li>Email: customer@example.com</li></ul>
                import re
                phone_match = re.search(r'Phone:? ([^<]+)', description)
                email_match = re.search(r'Email:? ([^<]+)', description)

                if phone_match:
                    phone = phone_match.group(1).strip()
                if email_match:
                    email = email_match.group(1).strip()

            # Search for existing partner by email or phone
            partner_obj = request.env['res.partner'].sudo()
            existing_partner = False

            if email:
                existing_partner = partner_obj.search([
                    '|', ('email', '=ilike', email), ('email_normalized', '=ilike', email)
                ], limit=1)

            if not existing_partner and phone:
                existing_partner = partner_obj.search([
                    ('phone', '=ilike', phone),
                    ('mobile', '=ilike', phone)
                ], limit=1, order='id desc')

            partner_vals = {
                'name': name,
                'phone': phone,
                'email': email,
            }

            if existing_partner:
                # Update existing partner
                existing_partner.write(partner_vals)
                return existing_partner
            else:
                # Create new partner
                return partner_obj.create(partner_vals)

        except Exception as e:
            # Fallback: create partner with just the name
            return request.env['res.partner'].sudo().create({'name': name})

    def _get_selected_service_product(self, appointment_type, answer_input_values):
        """Return the service product variant selected in the booking form, if any"""
        if appointment_type.name.lower() != "car wash care":
            return None

        try:
            service_question, selected_answer = self._find_service_selection(answer_input_values)
            if not (service_question and selected_answer and selected_answer.name):
                return None
            # Read the vehicle type from its own dedicated "Type of car"
            # question rather than parsing it out of the service-selection
            # text, which can mention multiple vehicle types at once
            # (e.g. "Exterior + Interior deep cleaning (Sedan SAR 260, SUV SAR 330)")
            vehicle_type_answer = self._find_vehicle_type_selection(answer_input_values)
            return self._find_matching_product(selected_answer.name, vehicle_type_answer)
        except Exception:
            # Never block a booking on the custom product matching; fall back
            # to the standard appointment duration / no sale order
            _logger.exception(
                "Failed to resolve service product for appointment type %s",
                appointment_type.name,
            )
            return None

    def _create_appointment_sale_order(self, appointment_type, customer_partner, product):
        """Create a sale order from appointment data with proper product matching"""
        # Only process if this is a Car Wash Care appointment
        if appointment_type.name.lower() != "car wash care":
            return False

        # Create the sales order with the customer partner (not logged-in user)
        order_vals = {
            'partner_id': customer_partner.id,  # Use the customer from form
            'user_id': request.env.user.id,  # Keep logged-in user as salesperson
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

    def _create_curtain_furniture_sale_order(self, appointment_type, customer_partner, answer_input_values):
        """Create a sale order for Curtain and Furniture Care appointment type"""
        # Only process if this is a Curtain and Furniture Care appointment
        if appointment_type.name.lower() != "curtain and furniture care":
            return False

        # Extract product quantities from the answers
        product_quantities = self._extract_curtain_furniture_quantities(answer_input_values)

        if not product_quantities:
            print("No product quantities found for Curtain and Furniture Care")
            return False

        # Create order lines based on the extracted quantities
        order_lines = []
        for question_text, quantity in product_quantities.items():
            if quantity > 0:
                product = self._find_curtain_furniture_product(question_text)
                if product:
                    order_lines.append((0, 0, {
                        'product_id': product.id,
                        'name': product.name,
                        'product_uom_qty': quantity,
                        'price_unit': product.list_price,
                    }))
                    print(f"Added product: {product.name}, Quantity: {quantity}")
                else:
                    print(f"Product not found for: {question_text}")

        if not order_lines:
            print("No order lines created for Curtain and Furniture Care")
            return False

        # Create the sales order
        order_vals = {
            'partner_id': customer_partner.id,
            'user_id': request.env.user.id,
            'date_order': fields.Datetime.now(),
            'origin': f"Appointment: {appointment_type.name}",
            'order_line': order_lines
        }

        return request.env['sale.order'].sudo().create(order_vals)

    def _extract_curtain_furniture_quantities(self, answer_input_values):
        """Extract product quantities from Curtain and Furniture Care appointment answers"""
        product_quantities = {}

        for answer in answer_input_values:
            question = request.env['appointment.question'].browse(answer['question_id'])

            # Skip basic info questions (name, email, phone, area, unit number)
            basic_info_fields = ['full name', 'email', 'phone number', 'area', 'unit number']
            if question.name.lower() in basic_info_fields:
                continue

            # For selection questions with quantities (0-10)
            if question.question_type == 'select' and 'value_answer_id' in answer:
                answer_record = request.env['appointment.answer'].browse(answer['value_answer_id'])
                if answer_record:
                    # Extract quantity from answer (e.g., "6" from "6")
                    quantity_match = re.match(r'^(\d+)', answer_record.name)
                    if quantity_match:
                        quantity = int(quantity_match.group(1))
                        # Use the question text to identify the product
                        question_text = question.name

                        if question_text and quantity > 0:
                            product_quantities[question_text] = quantity
                            print(f"Extracted product: {question_text}, Quantity: {quantity}")

        return product_quantities

    def _find_curtain_furniture_product(self, question_text):
        """Find matching product for Curtain and Furniture Care items based on question text"""
        # Map form question text to search terms for products
        product_search_terms = {
            "Curtain set [SAR 350 VAT included]": "Curtain set",
            "Dining chair [SAR 62 VAT included]": "Dining Chair",
            "Blue Chair Oasis [SAR 56.15 VAT included]": "Blue Dining chair",
            "Small Sofa [SAR 350 VAT included]": "Small Sofa",
            "Big Sofa [SAR 420 VAT included]": "Big Sofa",
            "Mattresses [SAR 336.89 VAT included]": "Mattress",
            "Small Carpet up to 2 sqm [SAR 40 VAT included]": "Small up to 2 sqm",
            "Medium Carpet 2.1 to 6 sqm [SAR 160 VAT included]": "Medium 2.1-6 sqm",
            "Big Carpet 7 to 20 sqm [SAR 240 VAT included]": "Big 7-20 sqm"
        }

        # Get the search term for this question
        search_term = product_search_terms.get(question_text)

        if not search_term:
            print(f"No search term found for question: {question_text}")
            return None

        # Search for the product using ilike for case-insensitive search
        domain = [
            ('name', 'ilike', search_term),
            ('type', '=', 'service')
        ]

        product = request.env['product.product'].sudo().search(domain, limit=1)
        print(f"Searching for product with term: '{search_term}', Found: {product.name if product else 'None'}")
        return product

    def _find_service_selection(self, answer_input_values):
        """Find the service selection question and answer"""
        if not answer_input_values:
            return (None, None)
        # Load every asked question in one query; browsing them one by one
        # below would trigger a separate read per answer. Map by id because
        # several answers (checkbox questions) can share the same question.
        questions = request.env['appointment.question'].browse(
            list(dict.fromkeys(answer['question_id'] for answer in answer_input_values))
        )
        questions_by_id = {question.id: question for question in questions}
        for answer in answer_input_values:
            question = questions_by_id.get(answer['question_id'])
            if question and 'service' in question.name.lower() and question.question_type == 'select':
                return (
                    question,
                    request.env['appointment.answer'].browse(answer['value_answer_id'])
                )
        return (None, None)

    def _find_vehicle_type_selection(self, answer_input_values):
        """Find the answer to the dedicated 'Type of car' question (Sedan/SUV/etc.)

        The service-selection answer text can mention multiple vehicle types
        at once for pricing display (e.g. "...(Sedan SAR 260, SUV SAR 330)"),
        so the vehicle type must be read from its own question instead.
        """
        if not answer_input_values:
            return None
        questions = request.env['appointment.question'].browse(
            list(dict.fromkeys(answer['question_id'] for answer in answer_input_values))
        )
        questions_by_id = {question.id: question for question in questions}
        for answer in answer_input_values:
            question = questions_by_id.get(answer['question_id'])
            if question and 'type of car' in question.name.lower() and question.question_type == 'select':
                answer_record = request.env['appointment.answer'].browse(answer['value_answer_id'])
                return answer_record.name if answer_record else None
        return None

    def _find_matching_product(self, answer_name, vehicle_type_answer=None):
        """Match the appointment answer to an existing product"""
        if not answer_name:
            return None

        # Only process if this is a Car Wash Care appointment
        # Clean and parse the answer text
        service_type = self._extract_service_type(answer_name)
        # Prefer the vehicle type read from the dedicated "Type of car"
        # question; only fall back to parsing it out of the service answer
        # text if that question wasn't found (keeps old behavior as a
        # safety net)
        vehicle_type = self._extract_vehicle_type(vehicle_type_answer or answer_name)

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