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
        # Create customer contact from form data and sales order
        sale_order = False
        customer_partner = self._create_or_update_customer_partner(name, description)

        if customer_partner:
            # Check appointment type and handle accordingly
            if appointment_type.name.lower() == "curtain and furniture care":
                sale_order = self._create_curtain_furniture_sale_order(
                    appointment_type,
                    customer_partner,
                    answer_input_values
                )
            else:
                # For Car Wash Care and other types, use the existing logic
                sale_order = self._create_appointment_sale_order(
                    appointment_type,
                    customer_partner,  # Use the created/updated customer
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

    def _create_appointment_sale_order(self, appointment_type, customer_partner, answer_input_values):
        """Create a sale order from appointment data with proper product matching"""
        # Only process if this is a Car Wash Care appointment
        if appointment_type.name.lower() != "car wash care":
            return False

        # Find the service question and selected answer
        service_question, selected_answer = self._find_service_selection(answer_input_values)
        if not (service_question and selected_answer):
            return False

        # Find matching product based on answer
        product = self._find_matching_product(selected_answer.name)
        if not product:
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
        # Only process if this is a Car Wash Care appointment
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