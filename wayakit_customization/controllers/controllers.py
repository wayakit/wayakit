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
