import logging
import xmlrpc.client as xmlrpclib
from datetime import datetime

import odoo.addons.base.controllers.rpc  # noqa: F401
from odoo import http
from odoo.http import request
from odoo.service import common as common_service_root, db as db_service_root, model as model_service_root, security

from . import auth, utils
from .rate_limiting import check_rate_limit, record_api_request

_logger = logging.getLogger(__name__)

# Store the original security check function
_original_security_check = security.check


def _mcp_security_check(db, uid, passwd):
    """
    Custom security check that supports API key authentication for MCP.

    This is a workaround for Odoo 17's limitation where API keys cannot be used
    as passwords in XML-RPC execute_kw calls.
    """
    # Check if this is an MCP API key (special marker)
    if passwd == "__mcp_api_key__" and hasattr(request, "context") and request.context.get("mcp_api_key_auth"):
        # This is an API key authenticated request from MCP
        # The user has already been validated, so we bypass the password check
        expected_uid = request.context.get("mcp_api_key_user_id")
        if uid == expected_uid:
            _logger.debug(f"MCP API key authentication bypass for user {uid}")
            return True
        else:
            _logger.warning(f"MCP API key UID mismatch: expected {expected_uid}, got {uid}")
            return False

    # For all other cases, use the original security check
    return _original_security_check(db, uid, passwd)


# Apply the monkey patch
security.check = _mcp_security_check

# XML-RPC fault codes aligned with HTTP status codes
XMLRPC_FAULT_CODES = {
    "bad_request": 400,
    "unauthorized": 401,
    "forbidden": 403,
    "not_found": 404,
    "rate_limit": 429,
    "internal_error": 500,
}


def _generate_xmlrpc_fault(code: int, message: str) -> str:
    """
    Helper to generate an XML-RPC fault string with standardized codes.

    :param code: The fault code (HTTP status code)
    :type code: int
    :param message: The fault message
    :type message: str
    :return: XML-RPC fault response string
    :rtype: str
    """
    fault = xmlrpclib.Fault(code, message)
    return xmlrpclib.dumps(fault, methodresponse=1, allow_none=1)


class MCPCommonController(http.Controller):
    @http.route("/mcp/xmlrpc/common", type="http", auth="none", methods=["POST"], csrf=False)
    def index(self, **kwargs):
        # Check if MCP is globally enabled
        if not utils.is_mcp_enabled():
            fault_response = _generate_xmlrpc_fault(
                XMLRPC_FAULT_CODES["forbidden"],
                "MCP Server is disabled globally.",
            )
            return request.make_response(fault_response, [("Content-Type", "text/xml")])

        data = request.httprequest.data
        try:
            params, method = xmlrpclib.loads(data)
            result = common_service_root.dispatch(method, params)
            response_data = xmlrpclib.dumps((result,), methodresponse=1, allow_none=1)
            return request.make_response(response_data, [("Content-Type", "text/xml")])
        except xmlrpclib.Fault as e:
            _logger.warning(f"MCPCommonController XML-RPC Fault: Code {e.faultCode}, String: {e.faultString}")
            return request.make_response(
                xmlrpclib.dumps(e, methodresponse=1, allow_none=1),
                [("Content-Type", "text/xml")],
            )
        except Exception as e:
            error_msg = str(e)
            _logger.error("Error in MCPCommonController: %s", error_msg, exc_info=True)
            fault_response = _generate_xmlrpc_fault(
                XMLRPC_FAULT_CODES["internal_error"],
                f"MCPCommonController Error: {error_msg}",
            )
            return request.make_response(fault_response, [("Content-Type", "text/xml")])


class MCPDatabaseController(http.Controller):
    @http.route("/mcp/xmlrpc/db", type="http", auth="none", methods=["POST"], csrf=False)
    def index(self, **kwargs):
        # Check if MCP is globally enabled
        if not utils.is_mcp_enabled():
            fault_response = _generate_xmlrpc_fault(
                XMLRPC_FAULT_CODES["forbidden"],
                "MCP Server is disabled globally.",
            )
            return request.make_response(fault_response, [("Content-Type", "text/xml")])

        data = request.httprequest.data
        try:
            params, method = xmlrpclib.loads(data)
            result = db_service_root.dispatch(method, params)
            response_data = xmlrpclib.dumps((result,), methodresponse=1, allow_none=1)
            return request.make_response(response_data, [("Content-Type", "text/xml")])
        except xmlrpclib.Fault as e:
            _logger.warning(f"MCPDatabaseController XML-RPC Fault: Code {e.faultCode}, String: {e.faultString}")
            return request.make_response(
                xmlrpclib.dumps(e, methodresponse=1, allow_none=1),
                [("Content-Type", "text/xml")],
            )
        except Exception as e:
            error_msg = str(e)
            _logger.error("Error in MCPDatabaseController: %s", error_msg, exc_info=True)
            fault_response = _generate_xmlrpc_fault(
                XMLRPC_FAULT_CODES["internal_error"],
                f"MCPDatabaseController Error: {error_msg}",
            )
            return request.make_response(fault_response, [("Content-Type", "text/xml")])


class MCPObjectController(http.Controller):
    def _mcp_object_dispatch(self, xmlrpc_method: str, params: list):
        """
        Dispatch XML-RPC object calls with MCP access control.

        :param xmlrpc_method: The XML-RPC method name
        :type xmlrpc_method: str
        :param params: The XML-RPC parameters
        :type params: list
        :return: The result from Odoo's model service
        :raises xmlrpclib.Fault: If access is denied or parameters are invalid
        """
        if xmlrpc_method != "execute_kw":
            _logger.warning(f"MCPObjectController received non-execute_kw method: {xmlrpc_method}")
            # Log error only if we have a request context
            if request and hasattr(request, "env"):
                request.env["mcp.log"].sudo().log_error(
                    error_message=f"MCPObjectController: Unsupported method {xmlrpc_method}. Only execute_kw is allowed.",
                    error_code="E400",
                    endpoint="/mcp/xmlrpc/object",
                    operation=xmlrpc_method,
                    ip_address=request.httprequest.remote_addr if hasattr(request, "httprequest") else None,
                )
            raise xmlrpclib.Fault(
                XMLRPC_FAULT_CODES["bad_request"],
                f"MCPObjectController: Unsupported method {xmlrpc_method}. Only execute_kw is allowed.",
            )

        if len(params) < 5:  # db, uid, pass, model, method, ...
            raise xmlrpclib.Fault(
                XMLRPC_FAULT_CODES["bad_request"],
                "MCPObjectController: Insufficient parameters for execute_kw.",
            )

        # Standard params for execute_kw: (db_name, uid, password, model_name, model_method, args_array, kwargs_dict)
        # db_name = params[0]  # Not currently used but available if needed
        uid = params[1]
        auth_token = params[2]  # This is the password or API key
        model_name = params[3]
        model_method = params[4]

        # Validate model name
        try:
            model_name = utils.sanitize_model_name(model_name)
        except ValueError as e:
            raise xmlrpclib.Fault(XMLRPC_FAULT_CODES["bad_request"], f"Invalid model name: {e}") from e

        # Rate Limiting: Attempt to identify user from API key for rate limiting
        user_obj_for_rate_limit = None
        user_id_for_rate_limit = None

        # First try to get user from API key if it looks like one
        if isinstance(auth_token, str) and len(auth_token) > 20:  # API keys are typically longer
            user_obj_for_rate_limit = auth.get_user_from_api_key(auth_token)
            if user_obj_for_rate_limit:
                user_id_for_rate_limit = user_obj_for_rate_limit.id
                _logger.debug(f"MCP XML-RPC: Identified user {user_id_for_rate_limit} from API key for rate limiting.")

        # If no user from API key and uid is provided, use uid for rate limiting
        if not user_id_for_rate_limit and uid:
            user_id_for_rate_limit = uid

        # Apply rate limiting if enabled
        if request.env["ir.config_parameter"].sudo().get_param("mcp_server.enable_rate_limiting", "True") == "True":
            if user_id_for_rate_limit:
                if not check_rate_limit(user_id_for_rate_limit):
                    _logger.warning(
                        f"MCP XML-RPC: Rate limit exceeded for user ID {user_id_for_rate_limit} on {model_name}.{model_method}."
                    )
                    # Log rate limit exceeded
                    env_for_check = request.env
                    if user_obj_for_rate_limit:
                        env_for_check = request.env(user=user_obj_for_rate_limit.id)
                    env_for_check["mcp.log"].sudo().log_rate_limit_exceeded(
                        user_id=user_id_for_rate_limit,
                        endpoint="/mcp/xmlrpc/object",
                        ip_address=request.httprequest.remote_addr if request else None,
                    )
                    raise xmlrpclib.Fault(
                        XMLRPC_FAULT_CODES["rate_limit"],
                        "Too many requests. Rate limit exceeded.",
                    )
                record_api_request(user_id_for_rate_limit)
            else:
                # Apply anonymous rate limiting
                anonymous_id = -1
                if not check_rate_limit(anonymous_id):
                    raise xmlrpclib.Fault(
                        XMLRPC_FAULT_CODES["rate_limit"],
                        "Too many requests. Rate limit exceeded.",
                    )
                record_api_request(anonymous_id)

        # Create environment for MCP access check
        # If we have a user from API key, use their environment
        # Otherwise, use the default environment which will use the uid from params
        env_for_check = request.env
        if user_obj_for_rate_limit:
            env_for_check = request.env(user=user_obj_for_rate_limit.id)
        elif uid:
            # Try to create environment with the provided uid
            try:
                env_for_check = request.env(user=uid)
            except Exception:
                # If creating environment with uid fails, use default
                env_for_check = request.env

        # Track start time for performance logging
        start_time = datetime.now()

        # MCP Access Checks
        if not utils.check_mcp_access(env_for_check, model_name, model_method):
            # utils.check_mcp_access logs the specific reason for denial
            # Log permission denied
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            env_for_check["mcp.log"].sudo().log_permission_denied(
                model_name=model_name,
                operation=model_method,
                user_id=user_id_for_rate_limit,
                endpoint="/mcp/xmlrpc/object",
                ip_address=request.httprequest.remote_addr if request else None,
                error_message=f"Access denied by MCP for model '{model_name}' method '{model_method}'.",
            )
            raise xmlrpclib.Fault(
                XMLRPC_FAULT_CODES["forbidden"],
                f"Access denied by MCP for model '{model_name}' method '{model_method}'.",
            )

        # If all checks pass, dispatch to Odoo's standard model service
        _logger.info(
            f"MCP XML-RPC: Access GRANTED for {model_name}.{model_method} (User ID: {user_id_for_rate_limit if user_id_for_rate_limit else 'N/A'})"
        )

        try:
            # Check if we're using API key authentication
            # API keys are typically longer than regular passwords
            if isinstance(auth_token, str) and len(auth_token) > 20:
                # Try to validate as API key
                user_from_key = auth.get_user_from_api_key(auth_token)
                if user_from_key:
                    # API key is valid - use workaround for Odoo 17's limitation
                    _logger.debug(f"Using API key authentication workaround for user {user_from_key.id}")

                    # Set context flag and replace password with placeholder
                    request.update_context(mcp_api_key_auth=True, mcp_api_key_user_id=user_from_key.id)
                    modified_params = list(params)
                    modified_params[2] = "__mcp_api_key__"  # Special marker
                    result = model_service_root.dispatch(xmlrpc_method, modified_params)
                else:
                    # Not a valid API key, fall back to standard dispatch
                    result = model_service_root.dispatch(xmlrpc_method, params)
            else:
                # Regular password authentication - use standard dispatch
                result = model_service_root.dispatch(xmlrpc_method, params)

            # Log successful model access
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            # Extract record IDs if available
            record_ids = None
            if len(params) > 5 and isinstance(params[5], list):
                # For methods like read, write that have record IDs in params[5]
                record_ids = params[5] if (params[5] and isinstance(params[5][0], int)) else None

            env_for_check["mcp.log"].sudo().log_model_access(
                model_name=model_name,
                operation=model_method,
                user_id=user_id_for_rate_limit,
                record_ids=record_ids,
                endpoint="/mcp/xmlrpc/object",
                http_method="POST",
                duration_ms=duration_ms,
                ip_address=request.httprequest.remote_addr if request else None,
            )

            return result
        except Exception as e:
            # Log error
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            env_for_check["mcp.log"].sudo().log_error(
                error_message=str(e),
                error_code="E500",
                endpoint="/mcp/xmlrpc/object",
                model_name=model_name,
                operation=model_method,
                user_id=user_id_for_rate_limit,
                ip_address=request.httprequest.remote_addr if request else None,
            )
            raise

    @http.route("/mcp/xmlrpc/object", type="http", auth="none", methods=["POST"], csrf=False)
    def index(self, **kwargs):
        # Check if MCP is globally enabled
        if not utils.is_mcp_enabled():
            fault_response = _generate_xmlrpc_fault(
                XMLRPC_FAULT_CODES["forbidden"],
                "MCP Server is disabled globally.",
            )
            return request.make_response(fault_response, [("Content-Type", "text/xml")])

        data = request.httprequest.data
        try:
            params, method = xmlrpclib.loads(data)
            result = self._mcp_object_dispatch(method, params)
            response_data = xmlrpclib.dumps((result,))
            return request.make_response(response_data, [("Content-Type", "text/xml")])
        except xmlrpclib.Fault as e:
            _logger.warning(f"MCPObjectController XML-RPC Fault: Code {e.faultCode}, String: {e.faultString}")
            return request.make_response(
                xmlrpclib.dumps(e, methodresponse=1, allow_none=1),
                [("Content-Type", "text/xml")],
            )
        except Exception as e:
            error_msg = str(e)
            _logger.error(
                "Critical error in MCPObjectController dispatch: %s",
                error_msg,
                exc_info=True,
            )
            fault_response = _generate_xmlrpc_fault(
                XMLRPC_FAULT_CODES["internal_error"],
                f"Internal Server Error in MCPObjectController: {error_msg}",
            )
            return request.make_response(fault_response, [("Content-Type", "text/xml")])
