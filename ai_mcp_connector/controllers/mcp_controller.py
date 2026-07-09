"""Native MCP (Model Context Protocol) server for Odoo.

Speaks the MCP "Streamable HTTP" transport (JSON-RPC 2.0 over a single HTTP
endpoint) so remote MCP clients - including the Claude mobile/web apps - can talk
to Odoo directly, with no desktop bridge.

Security model
--------------
* Authentication uses Odoo's *native* API keys (res.users.apikeys, scope 'rpc').
  The token can be sent as ``Authorization: Bearer``, ``X-API-Key`` header, or
  embedded in the path (``/mcp/<token>``) for easy mobile use.
* Every tool runs with the access rights of the API key's user (no privilege
  escalation), AND is additionally gated by the per-model rules configured in
  ``ai.mcp.enabled.model``. Nothing is exposed unless an admin enables it.
"""

import base64
import datetime
import json
import logging
import secrets
import threading
import time

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

# In-memory sliding-window rate limiter: {user_id: [timestamps]}
_RL_CACHE = {}
_RL_LOCK = threading.Lock()

PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "ai-mcp-connector"
SERVER_VERSION = "2.0.0"

CORS_HEADERS = [
    ("Access-Control-Allow-Origin", "*"),
    ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
    ("Access-Control-Allow-Headers", "Content-Type, Authorization, X-API-Key, Mcp-Session-Id"),
    ("Access-Control-Expose-Headers", "Mcp-Session-Id"),
]

# Map each tool to the access operation it needs (None = no model check).
TOOL_OPERATION = {
    "list_models": None,
    "who_am_i": None,
    "fields_get": "read",
    "search_read": "read",
    "search_count": "read",
    "read_records": "read",
    "name_search": "read",
    "create_record": "create",
    "update_records": "write",
    "delete_records": "unlink",
    "call_method": "method",  # special: gated by the allow_method_calls setting
}


class McpAccessError(Exception):
    """Raised when a tool touches a model/operation that isn't enabled for MCP."""


# --------------------------------------------------------------------------- #
#  Serialization
# --------------------------------------------------------------------------- #
def _serialize(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return base64.b64encode(value).decode("ascii")
    if hasattr(value, "_name") and hasattr(value, "ids"):
        return value.ids
    if isinstance(value, dict):
        return {str(k): _serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize(v) for v in value]
    return str(value)


def _text_result(data, is_error=False):
    if isinstance(data, str) and is_error:
        text = data
    else:
        text = json.dumps(_serialize(data), indent=2, ensure_ascii=False)
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


# --------------------------------------------------------------------------- #
#  Tool registry
# --------------------------------------------------------------------------- #
def _tool_definitions():
    obj = {"type": "object"}
    return [
        {"name": "list_models",
         "description": "List the Odoo models exposed to MCP (only models an admin enabled).",
         "inputSchema": {**obj, "properties": {
             "filter": {"type": "string", "description": "Optional substring filter."}}}},
        {"name": "fields_get",
         "description": "Get field definitions (name, type, label, relation) of a model.",
         "inputSchema": {**obj, "properties": {
             "model": {"type": "string"},
             "attributes": {"type": "array", "items": {"type": "string"}}},
             "required": ["model"]}},
        {"name": "search_read",
         "description": "Search + read in one call. domain is an Odoo domain, e.g. "
                        "[[\"name\",\"ilike\",\"acme\"]].",
         "inputSchema": {**obj, "properties": {
             "model": {"type": "string"},
             "domain": {"type": "array"},
             "fields": {"type": "array", "items": {"type": "string"}},
             "limit": {"type": "integer", "default": 50},
             "offset": {"type": "integer", "default": 0},
             "order": {"type": "string"}},
             "required": ["model"]}},
        {"name": "search_count",
         "description": "Count records matching a domain.",
         "inputSchema": {**obj, "properties": {
             "model": {"type": "string"}, "domain": {"type": "array"}},
             "required": ["model"]}},
        {"name": "read_records",
         "description": "Read specific records by id.",
         "inputSchema": {**obj, "properties": {
             "model": {"type": "string"},
             "ids": {"type": "array", "items": {"type": "integer"}},
             "fields": {"type": "array", "items": {"type": "string"}}},
             "required": ["model", "ids"]}},
        {"name": "name_search",
         "description": "Fuzzy lookup returning (id, display_name) pairs.",
         "inputSchema": {**obj, "properties": {
             "model": {"type": "string"},
             "name": {"type": "string", "default": ""},
             "limit": {"type": "integer", "default": 20}},
             "required": ["model"]}},
        {"name": "create_record",
         "description": "Create a record. Returns the new id.",
         "inputSchema": {**obj, "properties": {
             "model": {"type": "string"}, "values": {"type": "object"}},
             "required": ["model", "values"]}},
        {"name": "update_records",
         "description": "Update (write) records by id.",
         "inputSchema": {**obj, "properties": {
             "model": {"type": "string"},
             "ids": {"type": "array", "items": {"type": "integer"}},
             "values": {"type": "object"}},
             "required": ["model", "ids", "values"]}},
        {"name": "delete_records",
         "description": "Delete (unlink) records by id. Irreversible.",
         "inputSchema": {**obj, "properties": {
             "model": {"type": "string"},
             "ids": {"type": "array", "items": {"type": "integer"}}},
             "required": ["model", "ids"]}},
        {"name": "call_method",
         "description": "Call a public method on an MCP-enabled model (requires the admin "
                        "'Allow Arbitrary Method Calls' setting). For a method that acts on "
                        "existing records - e.g. button_confirm, action_post, action_cancel - "
                        "put the target record ids in 'ids' (e.g. ids=[5]); the method runs on "
                        "exactly those records. Use 'args'/'kwargs' only for the method's own "
                        "extra parameters. Omit 'ids' only for model-level (@api.model) methods.",
         "inputSchema": {**obj, "properties": {
             "model": {"type": "string"},
             "method": {"type": "string"},
             "ids": {"type": "array", "items": {"type": "integer"},
                     "description": "Record ids the method runs on. Required for record "
                                    "methods like button_confirm; omit for @api.model methods."},
             "args": {"type": "array", "description": "Extra positional args for the method (not the ids)."},
             "kwargs": {"type": "object"}},
             "required": ["model", "method"]}},
        {"name": "who_am_i",
         "description": "Info about the Odoo user this connection acts as.",
         "inputSchema": {**obj, "properties": {}}},
    ]


_DEFAULT_FIELD_ATTRS = ["string", "type", "help", "required", "readonly", "relation", "selection"]


# --------------------------------------------------------------------------- #
#  Access enforcement helpers
# --------------------------------------------------------------------------- #
def _config(env, key, default):
    return env["ir.config_parameter"].sudo().get_param("ai_mcp_connector." + key, default)


def _rate_limit_ok(env, user_id):
    """Sliding-window per-user limiter. Returns False if the user is over the limit."""
    if _config(env, "enable_rate_limiting", "True") != "True":
        return True
    try:
        limit = int(_config(env, "request_limit", "300"))
    except (ValueError, TypeError):
        limit = 300
    if limit <= 0:  # 0 = unlimited
        return True
    now = time.time()
    window_start = now - 60
    with _RL_LOCK:
        times = [t for t in _RL_CACHE.get(user_id, []) if t > window_start]
        if len(times) >= limit:
            _RL_CACHE[user_id] = times
            return False
        times.append(now)
        _RL_CACHE[user_id] = times
        return True


def _enforce_access(env, tool_name, model):
    """Raise McpAccessError unless this tool is allowed on this model."""
    operation = TOOL_OPERATION.get(tool_name, "read")
    if operation is None:
        return
    if not model:
        raise McpAccessError("'model' is required for tool '%s'." % tool_name)
    Enabled = env["ai.mcp.enabled.model"].sudo()
    if operation == "method":
        if _config(env, "allow_method_calls", "False") != "True":
            raise McpAccessError(
                "Arbitrary method calls are disabled. An admin must enable "
                "'Allow Arbitrary Method Calls' in MCP settings.")
        # method calls still require the model to be MCP-enabled (read minimum)
        if not Enabled.check_operation(model, "read"):
            raise McpAccessError("Model '%s' is not enabled for MCP access." % model)
        return
    if not Enabled.check_operation(model, operation):
        raise McpAccessError(
            "MCP %s access to model '%s' is not enabled. Enable it under "
            "Settings -> AI MCP Connector -> MCP Models." % (operation, model))


def _execute_tool(env, name, args):
    """Run a tool against ``env`` (scoped to the API key's user). Access already checked."""
    args = args or {}

    if name == "who_am_i":
        u = env.user
        groups = getattr(u, "group_ids", False) or getattr(u, "groups_id", env["res.groups"])
        return {"uid": u.id, "name": u.name, "login": u.login,
                "company": u.company_id.display_name, "groups": groups.mapped("display_name")}

    if name == "list_models":
        flt = (args.get("filter") or "").lower()
        enabled = env["ai.mcp.enabled.model"].sudo().search([("active", "=", True)])
        out = []
        for e in enabled:
            m = e.model_id
            if not flt or flt in (m.model or "").lower() or flt in (m.name or "").lower():
                out.append({"model": m.model, "name": m.name,
                            "can_read": e.allow_read, "can_create": e.allow_create,
                            "can_write": e.allow_write, "can_unlink": e.allow_unlink})
        return {"count": len(out), "models": sorted(out, key=lambda x: x["model"])}

    model = args.get("model")
    if model not in env:
        raise ValueError("Unknown model: %s" % model)
    Model = env[model]

    if name == "fields_get":
        return Model.fields_get(attributes=args.get("attributes") or _DEFAULT_FIELD_ATTRS)
    if name == "search_read":
        return Model.search_read(
            domain=args.get("domain") or [], fields=args.get("fields") or None,
            offset=args.get("offset") or 0, limit=args.get("limit") or 50,
            order=args.get("order") or None)
    if name == "search_count":
        return {"count": Model.search_count(args.get("domain") or [])}
    if name == "read_records":
        return Model.browse(args.get("ids") or []).read(args.get("fields") or None)
    if name == "name_search":
        pairs = Model.name_search(name=args.get("name") or "", limit=args.get("limit") or 20)
        return [{"id": p[0], "display_name": p[1]} for p in pairs]
    if name == "create_record":
        rec = Model.create(args.get("values") or {})
        return {"id": rec.id, "display_name": rec.display_name}
    if name == "update_records":
        recs = Model.browse(args.get("ids") or [])
        recs.write(args.get("values") or {})
        return {"updated": recs.ids}
    if name == "delete_records":
        recs = Model.browse(args.get("ids") or [])
        ids = recs.ids
        recs.unlink()
        return {"deleted": ids}
    if name == "call_method":
        method = args.get("method")
        if not method or method.startswith("_"):
            raise ValueError("Refusing to call missing/private method '%s'." % method)
        # Route through Odoo's own call_kw so record methods (button_confirm, etc.)
        # are invoked on the browsed recordset, not on an empty model. For non
        # @api.model methods call_kw takes the record ids as the first positional
        # arg; we expose those as a dedicated 'ids' field for clarity.
        from odoo.api import call_kw
        call_args = list(args.get("args") or [])
        ids = args.get("ids")
        if ids is not None:
            call_args = [ids] + call_args
        try:
            return call_kw(Model, method, call_args, args.get("kwargs") or {})
        except IndexError:
            if not call_args:
                raise ValueError(
                    "Method '%s' runs on records - pass the target record ids in "
                    "'ids' (e.g. ids=[5])." % method)
            raise

    raise ValueError("Unknown tool: %s" % name)


# --------------------------------------------------------------------------- #
#  JSON-RPC / MCP dispatch
# --------------------------------------------------------------------------- #
def _rpc_result(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _rpc_error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _handle_rpc(env, user, message):
    method = message.get("method")
    req_id = message.get("id")
    params = message.get("params") or {}

    if req_id is None and method and method.startswith("notifications/"):
        return None

    if method == "initialize":
        return _rpc_result(req_id, {
            "protocolVersion": params.get("protocolVersion") or PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": "Odoo MCP server. Use list_models to see what's exposed, "
                            "search_read to query. All actions run as Odoo user '%s'." % user.name,
        })
    if method == "ping":
        return _rpc_result(req_id, {})
    if method == "tools/list":
        return _rpc_result(req_id, {"tools": _tool_definitions()})
    if method in ("resources/list", "prompts/list"):
        return _rpc_result(req_id, {method.split("/")[0]: []})

    if method == "tools/call":
        if _config(env, "enabled", "True") != "True":
            return _rpc_result(req_id, _text_result(
                "Error: the MCP server is disabled by the administrator.", is_error=True))
        tool_name = params.get("name")
        tool_args = params.get("arguments") or {}
        model = tool_args.get("model")
        Log = env["ai.mcp.log"].sudo()
        ip = request.httprequest.remote_addr
        try:
            _enforce_access(env, tool_name, model)
            result = _execute_tool(env, tool_name, tool_args)
            env.cr.flush()
            Log.log_event("model_access", user_id=user.id, ip_address=ip,
                          model_name=model, operation=TOOL_OPERATION.get(tool_name),
                          tool_name=tool_name)
            return _rpc_result(req_id, _text_result(result))
        except McpAccessError as exc:
            env.cr.rollback()
            Log.log_event("permission_denied", user_id=user.id, ip_address=ip,
                          model_name=model, tool_name=tool_name, error_message=str(exc))
            return _rpc_result(req_id, _text_result("Access denied: %s" % exc, is_error=True))
        except Exception as exc:  # noqa: BLE001
            env.cr.rollback()
            _logger.warning("MCP tool '%s' failed: %s", tool_name, exc)
            Log.log_event("error", user_id=user.id, ip_address=ip,
                          model_name=model, tool_name=tool_name, error_message=str(exc))
            return _rpc_result(req_id, _text_result("Error: %s" % exc, is_error=True))

    return _rpc_error(req_id, -32601, "Method not found: %s" % method)


CLAUDE_CONNECTORS_URL = "https://claude.ai/settings/connectors"


class McpController(http.Controller):

    # ---- helpers -------------------------------------------------------- #
    def _extract_token(self, token):
        if token:
            return token
        h = request.httprequest.headers
        auth = h.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return h.get("X-API-Key")

    def _authenticate(self, token):
        """Return a res.users record for a valid native API key, else None."""
        if not token:
            return None
        try:
            uid = request.env["res.users.apikeys"].sudo()._check_credentials(
                scope="rpc", key=token)
        except Exception as e:  # noqa: BLE001
            _logger.debug("API key check error: %s", e)
            return None
        if not uid:
            return None
        user = request.env["res.users"].sudo().browse(uid).exists()
        return user if (user and user.active) else None

    def _json_response(self, payload, status=200, extra_headers=None):
        headers = list(CORS_HEADERS) + [("Content-Type", "application/json")]
        if extra_headers:
            headers.extend(extra_headers)
        body = "" if payload is None else json.dumps(payload, ensure_ascii=False)
        return Response(body, status=status, headers=headers)

    # ---- MCP endpoint --------------------------------------------------- #
    @http.route(["/mcp", "/mcp/<token>"], type="http", auth="none",
                methods=["POST", "GET", "OPTIONS"], csrf=False, save_session=False)
    def mcp_endpoint(self, token=None, **kwargs):
        req = request.httprequest
        if req.method == "OPTIONS":
            return Response(status=204, headers=list(CORS_HEADERS))
        if req.method == "GET":
            return self._json_response({
                "server": SERVER_NAME, "version": SERVER_VERSION,
                "protocol": PROTOCOL_VERSION, "transport": "streamable-http",
                "status": "ok", "hint": "POST JSON-RPC 2.0 MCP messages to this URL."})

        token = self._extract_token(token)
        user = self._authenticate(token)
        if not user:
            request.env["ai.mcp.log"].sudo().log_event(
                "auth_failure", ip_address=req.remote_addr,
                error_message="Invalid or missing API key")
            return self._json_response(
                _rpc_error(None, -32001, "Unauthorized: invalid or missing API key."),
                status=401)

        try:
            raw = req.get_data(as_text=True) or ""
            message = json.loads(raw) if raw else {}
        except (ValueError, json.JSONDecodeError):
            return self._json_response(_rpc_error(None, -32700, "Parse error"), status=400)

        env = request.env(user=user.id, su=False)

        # Per-user rate limiting
        if not _rate_limit_ok(env, user.id):
            env["ai.mcp.log"].sudo().log_event(
                "rate_limit", user_id=user.id, ip_address=req.remote_addr,
                error_message="Rate limit exceeded")
            return self._json_response(
                _rpc_error(None, -32002, "Rate limit exceeded. Please slow down."),
                status=429)

        session_id = req.headers.get("Mcp-Session-Id") or secrets.token_hex(16)
        extra = [("Mcp-Session-Id", session_id)]

        if isinstance(message, list):
            responses = [r for r in (_handle_rpc(env, user, m) for m in message) if r is not None]
            if not responses:
                return Response(status=202, headers=list(CORS_HEADERS) + extra)
            return self._json_response(responses, extra_headers=extra)

        response = _handle_rpc(env, user, message)
        if response is None:
            return Response(status=202, headers=list(CORS_HEADERS) + extra)
        return self._json_response(response, extra_headers=extra)
