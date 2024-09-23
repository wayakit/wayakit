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
from odoo import http, tools, _
from odoo.http import request
from odoo.tools.image import image_data_uri
import datetime
import time
import base64
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
                'AvailableSlots': {
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
        routes=build_route('/api/services/availableslots'),
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
    def get_available_slots(self, **kw):
        service_id = kw.get('serviceid')
        extras_ids = kw.get('extrasid')
        date = kw.get('Date')
        if service_id and date:
            day = date[0:2]
            month = date[2:4]
            year = date[4:8]
            formatted_date = f"{year}-{month}-{day}"

            appointment_type_id = request.env['appointment.type'].sudo().search([
                ('id', '=', service_id),
            ])
            if appointment_type_id :

                totalduration = appointment_type_id.appointment_duration
                product_varients_ids = appointment_type_id.product_id.product_variant_ids.search(
                    [('id', 'in', extras_ids)])
                if (product_varients_ids):
                    # mapped
                    for product in product_varients_ids:
                        totalduration += product.duration
                total = appointment_type_id.appointment_duration
                appointment_type_id.appointment_duration = totalduration
                tinmezone = appointment_type_id.appointment_tz
                slots = appointment_type_id._get_appointment_slots(
                    tinmezone,
                )
                target_date = datetime.strptime(formatted_date, '%Y-%m-%d').date()

                new_slots = []
                for month in slots:
                    weeks = month.get('weeks')
                    for week in weeks:
                        for day in week:
                            if day.get('day') == target_date and day.get('slots'):
                                new_slots = day.get('slots')
                                break
                if new_slots:
                    appointment_type_id.appointment_duration = total
                    availableslots = []
                    timezone = pytz.timezone(tinmezone)

                    availableslots = []

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
                "no service is available for this id"
        else:
            return "no service id or date is given"
