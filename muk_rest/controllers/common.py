###################################################################################
#
#    Copyright (c) 2017-today MuK IT GmbH.
#
#    This file is part of MuK REST for Odoo
#    (see https://mukit.at).
#
#    MuK Proprietary License v1.0
#
#    This software and associated files (the "Software") may only be used
#    (executed, modified, executed after modifications) if you have
#    purchased a valid license from MuK IT GmbH.
#
#    The above permissions are granted for a single database per purchased
#    license. Furthermore, with a valid license it is permitted to use the
#    software on other databases as long as the usage is limited to a testing
#    or development environment.
#
#    You may develop modules based on the Software or that use the Software
#    as a library (typically by depending on it, importing it and using its
#    resources), but without copying any source code or material from the
#    Software. You may distribute those modules under the license of your
#    choice, provided that this license is compatible with the terms of the
#    MuK Proprietary License (For example: LGPL, MIT, or proprietary licenses
#    similar to this one).
#
#    It is forbidden to publish, distribute, sublicense, or sell copies of
#    the Software or modified copies of the Software.
#
#    The above copyright notice and this permission notice must be included
#    in all copies or substantial portions of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
#    OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
#    THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#    DEALINGS IN THE SOFTWARE.
#
###################################################################################

import werkzeug
import json
from odoo import http, tools, _, Command
from odoo.http import request
from odoo.tools.image import image_data_uri
import datetime
import time
import base64
from odoo import api, fields, models
from datetime import datetime, date, timezone, timedelta
from dateutil.relativedelta import relativedelta
from odoo.addons.muk_rest import core
from odoo.addons.muk_rest.tools.http import build_route
import json
from odoo import tools, _
from odoo import http
import pytz
from odoo.http import request

import logging


class CommonController(http.Controller):

    # ----------------------------------------------------------
    # Components
    # ----------------------------------------------------------

    @property
    def API_DOCS_COMPONENTS(self):
        return {
            'schemas': {
                'ModuleData': {
                    'type': 'object',
                    'properties': {
                        'model': {
                            'type': 'string',
                        },
                        'id': {
                            'type': 'integer',
                        },
                    },
                    'description': 'A map of the model name and the corresponding ID.'
                },
                'RecordXMLID': {
                    'type': 'object',
                    'properties': {
                        'model': {
                            'type': 'string',
                        },
                        'id': {
                            'type': 'integer',
                        },
                    },
                    'description': 'The model name and the ID of the record.'
                },
                'CurrentUser': {
                    'type': 'object',
                    'properties': {
                        'name': {
                            'type': 'string',
                        },
                        'uid': {
                            'type': 'integer',
                        },
                    },
                    'description': 'The name and ID of the current user.'
                },
                'UserInfo': {
                    'type': 'object',
                    'properties': {
                        'address': {
                            'type': 'object',
                            'properties': {
                                'country': {
                                    'type': 'string',
                                },
                                'formatted': {
                                    'type': 'string',
                                },
                                'locality': {
                                    'type': 'string',
                                },
                                'postal_code': {
                                    'type': 'string',
                                },
                                'region': {
                                    'type': 'string',
                                },
                                'street_address': {
                                    'type': 'string',
                                },
                            },
                        },
                        'email': {
                            'type': 'string',
                        },
                        'locale': {
                            'type': 'string',
                        },
                        'name': {
                            'type': 'string',
                        },
                        'phone_number': {
                            'type': 'string',
                        },
                        'picture': {
                            'type': 'string',
                        },
                        'sub': {
                            'type': 'integer',
                        },
                        'updated_at': {
                            'type': 'string',
                            'format': 'date-time',
                        },
                        'username': {
                            'type': 'string',
                        },
                        'website': {
                            'type': 'string',
                        },
                        'zoneinfo': {
                            'type': 'string',
                        },
                    },
                    'description': 'Information about the current user.'
                },
                'UserCompany': {
                    'type': 'object',
                    'properties': {
                        'allowed_companies': {
                            '$ref': '#/components/schemas/RecordTuples',
                        },
                        'current_company': {
                            '$ref': '#/components/schemas/RecordTuple',
                        },
                        'current_company_id': {
                            'type': 'integer',
                        },
                    },
                    'description': 'Information about the current company and allowed companies of the current user.'
                },
                'UserSession': {
                    'type': 'object',
                    'properties': {
                        'db': {
                            'type': 'string',
                        },
                        'uid': {
                            'type': 'integer',
                        },
                        'username': {
                            'type': 'string',
                        },
                        'name': {
                            'type': 'string',
                        },
                        'partner_id': {
                            'type': 'integer',
                        },
                        'company_id': {
                            'type': 'integer',
                        },
                        'user_context': {
                            '$ref': '#/components/schemas/UserContext',
                        },
                    },
                    'additionalProperties': True,
                    'description': 'Information about the current session.'
                },
                "BookingData": {
                    "type": "object",
                    "properties": {
                        "bookingid": {
                            "type": "string",
                            "description": "The unique identifier for the booking."
                        },
                        "customerkaustid": {
                            "type": "string",
                            "description": "The unique identifier for the customer (KAUST ID)."
                        },
                        "customername": {
                            "type": "string",
                            "description": "The name of the customer."
                        },
                        "totalcostvatinclusive": {
                            "type": "number",
                            "description": "The total cost of the booking, VAT inclusive."
                        },
                        "status": {
                            "type": "string",
                            "enum": ["confirmed", "pending", "canceled"],
                            "description": "The status of the booking."
                        }
                    },
                    "required": ["bookingid", "customerkaustid", "customername", "totalcostvatinclusive", "status"],
                    "description": "Details of the booking including customer information, total cost, and status."
                },
                'Services': {
                    'type': 'object',
                    'properties': {
                        'db': {
                            'type': 'string',
                        },
                        'uid': {
                            'type': 'integer',
                        },
                        'username': {
                            'type': 'string',
                        },
                        'name': {
                            'type': 'string',
                        },
                        'partner_id': {
                            'type': 'integer',
                        },
                        'company_id': {
                            'type': 'integer',
                        },
                        'user_context': {
                            '$ref': '#/components/schemas/UserContext',
                        },
                    },
                    'additionalProperties': True,
                    'description': 'Information about the current session.'
                },
                "AvailableSlots": {
                    "type": "object",
                    "properties": {
                        "from": {
                            "type": "string",
                            "format": "date-time"
                        },
                        "to": {
                            "type": "string",
                            "format": "date-time"
                        }
                    },
                    "description": "Available time slots for booking."
                },
                "ServiceData": {
                    "type": "object",
                    "properties": {
                        "serviceprovider": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string"
                                    },
                                    "description": {
                                        "type": "string"
                                    },
                                    "phonenumber": {
                                        "type": "string",
                                        "pattern": "^\\+?[0-9]{10,15}$"
                                    },
                                    "Termsandconditions": {
                                        "type": "string"
                                    },
                                    "Paymentoptions": {
                                        "type": "string",
                                        "enum": ["Card reader", "Online Payment", "STC Pay"]
                                    }
                                },
                                "required": ["name", "description", "phonenumber", "Termsandconditions",
                                             "Paymentoptions"]
                            }
                        },
                        "servicehours": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "dayoftheweek": {
                                        "type": "string",
                                        "enum": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                                                 "Saturday"]
                                    },
                                    "Opentime": {
                                        "type": "string",
                                        "pattern": "^(0?[1-9]|1[0-2]):[0-5][0-9] ?(am|pm)$"
                                    },
                                    "Closetime": {
                                        "type": "string",
                                        "pattern": "^(0?[1-9]|1[0-2]):[0-5][0-9] ?(am|pm)$"
                                    }
                                },
                                "required": ["dayoftheweek", "Opentime", "Closetime"]
                            }
                        },
                        "specialdays": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "startdate": {
                                        "type": "string",
                                        "pattern": "^([0-2][0-9]|3[0-1])(0[1-9]|1[0-2])\\d{4}$"
                                    },
                                    "enddate": {
                                        "type": "string",
                                        "pattern": "^([0-2][0-9]|3[0-1])(0[1-9]|1[0-2])\\d{4}$"
                                    },
                                    "isaholiday": {
                                        "type": "string",
                                        "enum": ["Yes", "No"]
                                    },
                                    "opentime": {
                                        "type": "string",
                                        "pattern": "^(0?[1-9]|1[0-2]):[0-5][0-9] ?(am|pm)?$",
                                        "nullable": True
                                    },
                                    "closetime": {
                                        "type": "string",
                                        "pattern": "^(0?[1-9]|1[0-2]):[0-5][0-9] ?(am|pm)?$",
                                        "nullable": True
                                    },
                                    "reason": {
                                        "type": "string",
                                        "nullable": True
                                    }
                                },
                                "required": ["startdate", "enddate", "isaholiday"]
                            }
                        }
                    },
                    "required": ["serviceprovider", "servicehours", "specialdays"]
                },

            }
        }

        # ----------------------------------------------------------
        # Utility
        # ----------------------------------------------------------

    @core.http.rest_route(

        routes=build_route('/<path:path>'),
        rest_access_hidden=True,
        disable_logging=True,

    )
    def catch(self, **kw):
        return request.not_found()

    # ----------------------------------------------------------
    # Common
    # ----------------------------------------------------------

    @core.http.rest_route(
        routes=build_route('/database'),
        methods=['GET'],
        ensure_db=True,
        docs=dict(
            tags=['Common'],
            summary='Database',
            description='Returns the current database.',
            responses={
                '200': {
                    'description': 'Current Database',
                    'content': {
                        'application/json': {
                            'schema': {
                                'type': 'object',
                                'properties': {
                                    'database': {
                                        'type': 'string',
                                    }
                                }
                            },
                            'example': {'database': 'mydb'}
                        }
                    }
                }
            },
            default_responses=['400', '401', '500'],
        )
    )
    def database(self, **kw):
        return request.make_json_response({'database': request.db})

    @core.http.rest_route(
        routes=build_route('/modules'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Common'],
            summary='Modules',
            description='Returns a list of installed modules.',
            parameter_context=False,
            parameter_company=False,
            responses={
                '200': {
                    'description': 'List of Modules',
                    'content': {
                        'application/json': {
                            'schema': {
                                '$ref': '#/components/schemas/ModuleData'
                            },
                            'example': {
                                'base': 1,
                                'web': 2,
                            }
                        }
                    }
                }
            },
            default_responses=['400', '401', '500'],
        ),
    )
    def modules(self):
        return request.make_json_response(
            request.registry._init_modules
        )

    @core.http.rest_route(
        routes=build_route([
            '/xmlid',
            '/xmlid/<string:xmlid>',
        ]),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Common'],
            summary='XML ID',
            description='Returns the XML ID record.',
            parameter={
                'xmlid': {
                    'name': 'xmlid',
                    'description': 'XML ID',
                    'schema': {
                        'type': 'string'
                    },
                    'example': 'base.main_company',
                },
            },
            parameter_context=False,
            parameter_company=False,
            responses={
                '200': {
                    'description': 'XML ID Record',
                    'content': {
                        'application/json': {
                            'schema': {
                                '$ref': '#/components/schemas/RecordXMLID'
                            },
                            'example': {
                                'model': 'res.company',
                                'id': 1,
                            }
                        }
                    }
                }
            },
            default_responses=['400', '401', '500'],
        ),
    )
    def xmlid(self, xmlid, **kw):
        record = request.env.ref(xmlid)
        return request.make_json_response({
            'model': record._name, 'id': record.id
        })

    # ----------------------------------------------------------
    # Session
    # ----------------------------------------------------------

    @core.http.rest_route(
        routes=build_route('/user'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Common'],
            summary='User',
            description='Returns the current user.',
            responses={
                '200': {
                    'description': 'Current User',
                    'content': {
                        'application/json': {
                            'schema': {
                                '$ref': '#/components/schemas/CurrentUser'
                            },
                            'example': {
                                'name': 'Admin',
                                'uid': 2,
                            }
                        }
                    }
                }
            },
            default_responses=['400', '401', '500'],
        ),
    )
    def user(self, **kw):
        return request.make_json_response({
            'uid': request.session and request.session.uid,
            'name': request.env.user and request.env.user.name
        })

    @core.http.rest_route(
        routes=build_route('/userinfo'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Common'],
            summary='User Information',
            description='Returns the user information.',
            responses={
                '200': {
                    'description': 'User Information',
                    'content': {
                        'application/json': {
                            'schema': {
                                '$ref': '#/components/schemas/UserInfo'
                            },
                            'example': {
                                'address': {
                                    'country': 'United States',
                                    'formatted': 'YourCompany\n215 Vine St\n\nScranton PA 18503\nUnited States',
                                    'locality': 'Scranton',
                                    'postal_code': '18503',
                                    'region': 'Pennsylvania (US)',
                                    'street_address': '215 Vine St'
                                },
                                'email': 'admin@yourcompany.example.com',
                                'locale': 'en_US',
                                'name': 'Mitchell Admin',
                                'phone_number': '+1 555-555-5555',
                                'picture': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=',
                                'sub': 2,
                                'updated_at': '2020-11-11 13:57:48',
                                'username': 'admin',
                                'website': False,
                                'zoneinfo': 'Europe/Vienna'
                            }
                        }
                    }
                }
            },
            default_responses=['400', '401', '500'],
        ),
    )
    def userinfo(self, **kw):
        user = request.env.user
        uid = request.session.uid
        return request.make_json_response({
            'sub': uid,
            'id': user.id,
            'company_id': user.company_id.id,
            'name': user.name,
            'locale': user.lang,
            'zoneinfo': user.tz,
            'username': user.login,
            'email': user.partner_id.email,
            'website': user.partner_id.website,
            'address': {
                'formatted': user.partner_id.contact_address if user.partner_id.contact_address else "",
                'street_address': user.partner_id.street if user.partner_id.street else "",
                'locality': user.partner_id.city if user.partner_id.city else "",
                'postal_code': user.partner_id.zip if user.partner_id.zip else "",
                'region': user.partner_id.state_id.display_name if user.partner_id.state_id.display_name else "",
                'country': user.partner_id.country_id.with_context(
                    lang=user.lang).display_name if user.partner_id.country_id.display_name else "",
            },
            'updated_at': user.partner_id.write_date,
            'profile': user.partner_id.image_1920 if user.partner_id.image_1920 else ""
            # 'picture': image_data_uri(user.partner_id.image_1024),
        })

    @core.http.rest_route(
        routes=build_route('/company'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Common'],
            summary='Company Information',
            description='Returns the current company.',
            responses={
                '200': {
                    'description': 'Current Company',
                    'content': {
                        'application/json': {
                            'schema': {
                                '$ref': '#/components/schemas/UserCompany'
                            },
                            'example': {
                                'allowed_companies': [[1, 'YourCompany']],
                                'current_company': [1, 'YourCompany'],
                                'current_company_id': 1
                            }
                        }
                    }
                }
            },
            default_responses=['400', '401', '500'],
        ),
    )
    def company(self, **kw):
        user = request.env.user
        suid = request.session.uid
        user_company_information = {
            'current_company_id': user.company_id.id if suid else None,
            'current_company': (user.company_id.id, user.company_id.name) if suid else None,
            'allowed_companies': []
        }
        if request.env.user and request.env.user.has_group('base.group_user'):
            user_company_information['allowed_companies'] = [
                (comp.id, comp.name) for comp in user.company_ids
            ]
        return request.make_json_response(user_company_information)

    @core.http.rest_route(
        routes=build_route('/session'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Common'],
            summary='Session Information',
            description='Returns the current session.',
            responses={
                '200': {
                    'description': 'Current Session',
                    'content': {
                        'application/json': {
                            'schema': {
                                '$ref': '#/components/schemas/UserSession'
                            },
                            'example': {
                                'db': 'mydb',
                                'user_id': 2,
                                'company_id': 1,
                                'user_context': {
                                    'lang': 'en_US',
                                    'tz': 'Europe/Vienna',
                                    'uid': 2
                                },
                            }
                        }
                    }
                }
            },
            default_responses=['400', '401', '500'],
        ),
    )
    def session(self, **kw):
        return request.make_json_response(request.env['ir.http'].session_info())

    @core.http.rest_route(
        routes=build_route('/services/availableslots'),
        methods=['POST'],
        protected=True,
        docs=dict(
            tags=['Common'],
            summary='Get Available Slots',
            description='Returns the available slots.',
            responses={
                '200': {
                    'description': 'Available Slots',
                    'content': {
                        'application/json': {
                            'schema': {
                                '$ref': '#/components/schemas/AvailableSlots'
                            },
                            'example': {
                                "availableslots": [
                                    {
                                        "from": "2024-09-27T09:00:00+03:00",
                                        "to": "2024-09-27T10:00:00+03:00"
                                    }
                                ]
                            }
                        }
                    }
                }
            },
            default_responses=['400', '401', '500'],
        ),
    )
    def get_available_slots(self, **kw):
        service_id = kw.get('serviceid')
        extras_ids = kw.get('extrasid')
        date = kw.get('Date')
        if service_id and date:
            date = datetime.strptime(date, '%d%m%Y').date()
            appointment_type_id = request.env['appointment.type'].sudo().browse(int(service_id)).exists()

            if appointment_type_id:
                total_duration = appointment_type_id.appointment_duration

                product_varients_ids = appointment_type_id.product_id.product_variant_ids.browse(extras_ids).exists()
                if (product_varients_ids):
                    total_duration += sum(product_varients_ids.mapped('duration'))
                total = appointment_type_id.appointment_duration
                appointment_type_id.appointment_duration = total_duration
                tinmezone = appointment_type_id.appointment_tz
                slots = appointment_type_id._get_appointment_slots(
                    tinmezone,
                )

                new_slots = next(
                    (day.get('slots') for month in slots for week in month.get('weeks') for day in week
                     if day.get('day') == date and day.get('slots')), []
                )
                if new_slots:
                    appointment_type_id.appointment_duration = total
                    availableslots = []
                    timezone = pytz.timezone(tinmezone)

                    for slot in new_slots:
                        from_time = datetime.strptime(slot['datetime'], '%Y-%m-%d %H:%M:%S')
                        from_time = timezone.localize(from_time)
                        slot_duration = float(slot['slot_duration'])
                        to_time = from_time + timedelta(hours=slot_duration)

                        availableslots.append({
                            'from': from_time.isoformat(),
                            'to': to_time.isoformat()
                        })
                    return request.make_json_response({
                        "availableslots": availableslots})
                else:
                    return "no slots is available"
            else:
                return "no service is available for this id"
        else:
            return "no service id or date is given"

    @core.http.rest_route(
        routes=build_route('/Serviceprovider'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Common'],
            summary='Serviceprovider Inf.',
            description='Serviceprovider Inf.',
            responses={
                '200': {
                    'description': 'Serviceprovider Info',
                    'content': {
                        'application/json': {
                            'schema': {
                                '$ref': '#/components/schemas/ServiceData'
                            },
                            'example': {
                                "serviceprovider": [
                                    {
                                        "name": "<value1>",
                                        "description": "<name1>",
                                        "phonenumber": "<phone number>",
                                        "Termsandconditions": "<T&C in html format or public URL>",
                                        "Paymentoptions": "<Card reader, Online Payment, STC Pay>"
                                    }
                                ],
                                "servicehours": [
                                    {
                                        "dayoftheweek": "Sunday",
                                        "Opentime": "8:00 am",
                                        "Closetime": "8:00 pm"
                                    },
                                    {
                                        "dayoftheweek": "Monday",
                                        "Opentime": "8:00 am",
                                        "Closetime": "8:00 pm"
                                    },
                                    {
                                        "dayoftheweek": "<value1>",
                                        "Opentime": "<value2>",
                                        "Closetime": "<value3>"
                                    },
                                    {
                                        "dayoftheweek": "<value1>",
                                        "Opentime": "<value2>",
                                        "Closetime": "<value3>"
                                    },
                                    {
                                        "dayoftheweek": "<value1>",
                                        "Opentime": "<value2>",
                                        "Closetime": "<value3>"
                                    },
                                    {
                                        "dayoftheweek": "Friday",
                                        "Opentime": "1:30 pm",
                                        "Closetime": "11:59 pm"
                                    },
                                    {
                                        "dayoftheweek": "<value1>",
                                        "Opentime": "<value2>",
                                        "Closetime": "<value3>"
                                    }
                                ],
                                "specialdays": [
                                    {
                                        "startdate": "<DDMMYYYY>",
                                        "enddate": "<DDMMYYYY>",
                                        "isaholiday": "Yes",
                                        "opentime": " ",
                                        "closetime": " ",
                                        "reason": " "
                                    },
                                    {
                                        "startdate": "<DDMMYYYY>",
                                        "enddate": "<DDMMYYYY>",
                                        "isaholiday": "No",
                                        "opentime": " 10:00 am",
                                        "closetime": " 4:00 pm",
                                        "reason": "Ramadan Hours"
                                    }
                                ]
                            }
                        }
                    }
                }
            },
            default_responses=['400', '401', '500'],
        ),
    )
    def get_service_provider(self, **kw):
        provider_companies = request.env['res.company'].sudo().search([('is_service_provider', '=', True)])
        service_hours = []
        special_hours = []
        service_providers = []

        for company in provider_companies:
            field_values = {}

            for field in company.related_fields_ids:
                field_name = field.name
                field_value = getattr(company, field_name, None)
                field_values[field_name] = field_value

            service_providers.append(field_values)

            for day in company.working_schedule_id.attendance_ids:
                open_time = self._convert_time_to_string(day.hour_from) or ""
                close_time = self._convert_time_to_string(day.hour_to) or ""

                service_hours.append({
                    "dayoftheweek": day.name or "",
                    "Opentime": open_time,
                    "Closetime": close_time
                })

            if company.working_schedule_id.global_leave_ids:
                for leave in company.working_schedule_id.global_leave_ids:
                    start_date = leave.date_from.strftime("%d%m%Y") or ""
                    end_date = leave.date_to.strftime("%d%m%Y") or ""
                    special_hours.append({
                        "startdate": start_date,
                        "enddate": end_date,
                        "isaholiday": "Yes",
                        "opentime": "",
                        "closetime": "",
                        "reason": leave.name or ""
                    })

            if company.working_schedule_specialdays_id:
                open_time = self._convert_time_to_string(company.working_schedule_specialdays_id.open_time) or ""
                close_time = self._convert_time_to_string(company.working_schedule_specialdays_id.close_time) or ""
                special_hours.append({
                    "startdate": company.working_schedule_specialdays_id.start_date or "",
                    "enddate": company.working_schedule_specialdays_id.end_date or "",
                    "isaholiday": "No",
                    "opentime": open_time,
                    "closetime": close_time,
                    "reason": company.working_schedule_specialdays_id.name or ""
                })

        return request.make_json_response({
            "serviceproviders": service_providers,
            "servicehours": service_hours,
            "specialdays": special_hours})

    def _convert_time_to_string(self, hour_float):
        # Convert float (e.g., 8.0) to string time format (e.g., '8:00 am')
        hours = int(hour_float)
        minutes = int((hour_float - hours) * 60)
        am_pm = 'am' if hours < 12 else 'pm'
        if hours == 0:
            hours = 12
        elif hours > 12:
            hours -= 12
        return f"{hours}:{minutes:02d} {am_pm}"

    @core.http.rest_route(
        routes=build_route('/services/<serviceid>/book'),
        methods=['POST'],
        protected=True,
        docs=dict(
            tags=['Common'],
            summary='Booking Data.',
            description='Booking Data.',
            responses={
                '200': {
                    'description': 'Booking Data',
                    'content': {
                        'application/json': {
                            'schema': {
                                '$ref': '#/components/schemas/BookingData'
                            },
                            'example': {

                            }
                        }
                    }
                }
            },
            default_responses=['400', '401', '500'],
        ),
    )
    def book_appointment(self, **kw):
        customer_kaust_id = kw.get('customerkaustid')
        customer_name = kw.get('customername')
        customer_email = kw.get('customeremail')
        customer_phone = kw.get('customerphone')
        service_id = kw.get('serviceid')
        vehicle_type_id = kw.get('vehicletypeid')
        vehicle_use_id = kw.get('vehicleuseid')
        vehicle_subtype_id = kw.get('vehiclesubtype')
        total_cost_vat_inclusive = kw.get('totalcostvatinclusive')
        slot_info = kw.get('slot', [])

        if not service_id:
            return {"status": "error", "message": "Service ID is required."}

        service_id = int(service_id)

        try:
            if slot_info:
                slot_from = datetime.fromisoformat(slot_info[0].get('from'))
                slot_to = datetime.fromisoformat(slot_info[0].get('to'))
            else:
                return {"status": "error", "message": "Slot information is required."}
        except (IndexError, ValueError):
            return {"status": "error", "message": "Invalid slot information."}

        duration = slot_to - slot_from
        duration_in_hours = duration.total_seconds() / 3600 if duration else 0

        appointment_type_id = request.env['appointment.type'].sudo().browse(service_id).exists()

        if not appointment_type_id:
            return {"status": "error", "message": "Invalid service ID."}

        timezone = appointment_type_id.appointment_tz or 'UTC'
        start_date1 = fields.Datetime.to_string(slot_from)
        tz_session = pytz.timezone(timezone)
        date_from = tz_session.localize(fields.Datetime.from_string(start_date1)).astimezone(pytz.utc).replace(
            tzinfo=None)
        date_to = date_from + relativedelta(hours=duration_in_hours)

        partner = request.env['res.partner'].sudo().search([('customer_kaust_id', '=', customer_kaust_id)], limit=1)
        if not partner:
            partner = request.env['res.partner'].sudo().create({
                'name': customer_name or 'Unknown',
                'customer_kaust_id': customer_kaust_id,
                'email': customer_email or '',
                'phone': customer_phone or '',
            })
        vehicle_type = request.env['service.type'].sudo().search([('id', '=', int(vehicle_type_id))])
        vehicle_subtype = request.env['vehicle.type'].sudo().search([('id', '=', int(vehicle_subtype_id))])
        asked_capacity = 1
        booking_line_values = []
        description = ""
        duration = duration_in_hours
        appointment_invite = request.env['appointment.invite'].sudo().search([('id', '=', 2222)])
        name = partner.name
        customer = partner
        staff_user = appointment_type_id.staff_user_ids[0]
        answer_input_values =[]
        guests = None


        meeting = request.env['calendar.event'].with_context(
            mail_notify_author=True,
            mail_create_nolog=True,
            mail_create_nosubscribe=True,

        ).sudo().create({
            'appointment_answer_input_ids': [Command.create(vals) for vals in answer_input_values],
            **appointment_type_id._prepare_calendar_event_values(
                asked_capacity, booking_line_values, description,duration ,
                appointment_invite, guests, name, customer, staff_user, date_from, date_to
            )
        })
        meeting.write({
            'vehicle_type_id': vehicle_type if vehicle_type else None,
            'service_type_id': vehicle_subtype if vehicle_subtype else None,
        })

        return request.make_json_response({
            "bookingid": meeting.id,
            "customerkaustid": customer_kaust_id,
            "customername": partner.name,
            "totalcostvatinclusive": total_cost_vat_inclusive,
            "status": "confirmed"
        })

    @core.http.rest_route(
        routes=build_route('/services'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Common'],
            summary='Fetch Services Info',
            description='Returns the available services info.',
            responses={
                '200': {
                    'description': 'Services Info',
                    'content': {
                        'application/json': {
                            'schema': {
                                '$ref': '#/components/schemas/Services'
                            },
                            'example': {
                                'db': 'mydb',
                                'user_id': 2,
                                'company_id': 1,
                                'user_context': {
                                    'lang': 'en_US',
                                    'tz': 'Europe/Vienna',
                                    'uid': 2
                                },
                            }
                        }
                    }
                }
            },
            default_responses=['400', '401', '500'],
        ),
    )
    def get_services(self, **kw):
        services = request.env['appointment.type'].sudo().search([])
        data = []
        for service in services:
            extras = []
            if service.product_id:
                for variant in service.product_id.product_variant_ids:
                    total_included = variant.taxes_id.compute_all(variant.lst_price, product=variant).get(
                        'total_included')
                    extras.append({
                        "extrasid": variant.id,
                        "extrasname": variant.product_template_variant_value_ids.name,
                        "slottimeinminutes": int(variant.duration *60) if variant.duration else 0,
                        "pricevatinclusive": total_included,
                    })
            vehicle_data_list = []

            if service.service_type:
                for service_type in service.service_type:
                    # Create a new dictionary for each service type
                    vehicle_data = {
                        "vehicletype": [],
                        "vehicleuse": [],
                        "vehiclesubtype": []
                    }

                    # Collect vehicle type information for 'vehicletype'
                    vehicle_data["vehicletype"].append({
                        "vehicletypeid": service_type.id,
                        "vehicletypename":  service_type.vehicle_type if service_type.vehicle_type else service_type.name
                    })

                    # Collect vehicle use information for 'vehicleuse'
                    vehicle_data["vehicleuse"].append({
                        "vehicleusename": service_type.in_use if service_type.in_use else ''
                    })

                    # Collect vehicle subtype information for 'vehiclesubtype'
                    for subtype in service_type.sub_type_ids:
                        vehicle_data["vehiclesubtype"].append({
                            "vehiclesubtypeid": subtype.id,
                            "vehiclesubtypename": subtype.name,
                            "pricevatinclusive": subtype.inclusive_tax_price
                        })

                    # Append the vehicle_data dictionary to the vehicle_data_list
                    vehicle_data_list.append(vehicle_data)

            data.append({
                "serviceid": service.id,
                "servicename": service.name,
                "description": service.website_meta_description,
                "slottimeinminutes": int(service.appointment_duration)*60,
                "extrasid": extras,
                "vehicledata": vehicle_data_list,
            })
        return request.make_json_response({
            "services": data})
