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

import json
import requests
import werkzeug
import functools

from odoo import http, _
from odoo.tools import config, misc
from odoo.modules import get_resource_path
from odoo.http import Controller, Response, request, route

from odoo.addons.muk_rest.core.http import get_controllers
from odoo.addons.muk_rest.tools import common
from odoo.addons.muk_rest.tools import docs


class DocsController(Controller):
    
    #----------------------------------------------------------
    # Helper
    #----------------------------------------------------------
    
    def _get_base_url(self):
        return request.env['ir.config_parameter'].sudo().get_param('web.base.url')

    def _has_access_to_docs(self):
        security_group = request.env['ir.config_parameter'].sudo().get_param(
            'muk_rest.docs_security_group', False
        )
        if security_group:
            return request.env.user.has_group(security_group)
        elif common.DOCS_SECURITY_GROUP:
            return request.env.user.has_group(common.DOCS_SECURITY_GROUP)
        return True

    def _ensure_docs_access(self):
        if not self._has_access_to_docs():
            werkzeug.exceptions.abort(
                request.redirect('/web/login?error=access', 303)
            )

    def _get_api_docs(self):
        rest_docs = docs.generate_docs(
            self._get_base_url(), get_controllers()
        )
        paths, components = request.env['muk_rest.endpoint'].get_docs()
        if paths:
            rest_docs['paths'].update(paths)
            rest_docs['components']['schemas'].update(components)
        return rest_docs
    
    #----------------------------------------------------------
    # Routes
    #----------------------------------------------------------
    
    @route(
        route=['/rest/docs', '/rest/docs/index.html'],
        methods=['GET'],
        type='http',
        auth='public',
    )
    def docs_index(self, standalone=False, **kw):
        self._ensure_docs_access()
        template = (
            'muk_rest.docs_standalone'
            if misc.str2bool(standalone)
            else 'muk_rest.docs'
        )
        return request.render(template, {
            'db_header': config.get('rest_db_header', 'DATABASE'),
            'db_param': config.get('rest_db_param', 'db'),
            'base_url': self._get_base_url().strip('/'),
            'db_name': request.env.cr.dbname,
        })

    @route(
        route='/rest/docs/api.json',
        methods=['GET'],
        type='http',
        auth='public',
    )
    def docs_json(self, **kw):
        self._ensure_docs_access()
        return request.make_json_response(self._get_api_docs())

    @route(
        route='/rest/docs/oauth2/redirect',
        methods=['GET'],
        type='http',
        auth='none', 
        csrf=False,
    )
    def oauth_redirect(self, **kw):
        stream = http.Stream.from_path(get_resource_path(
            'muk_rest', 'static', 'lib', 'swagger-ui', 'oauth2-redirect.html'
        ))
        return stream.get_response()  
    
    @route(
        route=[
            '/rest/docs/client',
            '/rest/docs/client/<string:language>',
        ],
        methods=['GET'],
        type='http',
        auth='public',
    )
    def docs_client(self, language='python', options=None, **kw):
        self._ensure_docs_access()
        server_url = self._get_base_url()
        rest_docs = json.dumps(self._get_api_docs())
        attachment = request.env['ir.attachment'].sudo().create({
            'name': 'rest_api_docs.json', 'raw': rest_docs.encode(),
        })
        try:
            attachment.generate_access_token()
            docs_url = '{}/web/content/{}?access_token={}'.format(
                server_url, attachment.id, attachment.access_token
            )
            codegen_url = request.env['ir.config_parameter'].sudo().get_param(
                'muk_rest.docs_codegen_url', common.DOCS_CODEGEN_URL
            ) 
            response = requests.post(
                f'{codegen_url}/generate', 
                allow_redirects=True, 
                stream=True, 
                json={
                    'specURL' : docs_url, 
                    'lang' : language, 
                    'type' : 'CLIENT', 
                    'codegenVersion' : 'V3' ,
                    'options': common.parse_value(options, {}),
                }
            )
            headers = [
                ('Content-Type', response.headers.get('content-type')),
                ('Content-Disposition', response.headers.get('content-disposition')),
                ('Content-Length', response.headers.get('content-length')),
            ]
            return Response(response.raw, headers=headers, direct_passthrough=True)
        finally:
            attachment.unlink()

    @route(route='/rest/docs/check', type='json', auth='user')
    def docs_check(self, **kw):
        return self._has_access_to_docs()
        