import asyncio
import importlib
import json
import logging
import logging.handlers
from server.log_rotation import UnlimitedRotatingFileHandler
import mimetypes
import os
import random
import string
import time
import urllib.parse
from datetime import datetime, timezone as dt_timezone
import uuid
import base64
from server.task_registry import get_cron_jobs

import jinja2
import pickle
from server.background_worker import worker_loop
from jad.settings import BASE_DIR, JAD_VERSION, LOCAL_SERVER_INSTANCE_ID, REDIS_URL, DEBUG, JAD_ID
from jad import settings

from server import auth
from server.pools import get_pg, get_redis
from server.routing import get_handler_for_path, ROUTE_HANDLERS, REGEX_ROUTE_HANDLERS, ROLE_PRIORITIES
from server.template_filters import currency_symbol, status_color, sublocation_format
from siu_base.json import SiuJSONEncoder

from server.auth import get_api_key_permissions
from server.frontend import start_frontend_monitoring, stop_frontend_monitoring
from server.ws import update_connection as ws_update_connection, cleanup_connection as ws_cleanup_connection, ws_health_check_cleanup

from server.sentry import SentryAsgiMiddleware
from server.background_worker import enqueue_job
from server.background_worker import initiate_shutdown
from server.misc import get_next_run_ts
from markupsafe import Markup


if DEBUG:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(pathname)s:%(lineno)d - %(name)s - %(levelname)s - %(message)s"
    )
else:
    timestamp = int(time.time())
    unique_worker_id = f"{timestamp}_{os.getpid()}"

    rotating_handler = UnlimitedRotatingFileHandler(
        os.path.expanduser(f"/home/jad{JAD_ID}/log/uvicorn_{unique_worker_id}.log"),
        maxBytes=100 * 1024 * 1024  # 100MB
    )
    rotating_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(pathname)s:%(lineno)d - %(name)s - %(levelname)s - %(message)s"
    ))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(pathname)s:%(lineno)d - %(name)s - %(levelname)s - %(message)s",
        handlers=[rotating_handler]
    )

    # Configure uvicorn's internal loggers to use the same rotating file handler
    file_handler = rotating_handler

    # Configure uvicorn access logger (handles HTTP request logs)
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.handlers = [file_handler]
    uvicorn_access.setLevel(logging.INFO)
    uvicorn_access.propagate = False

    # Configure uvicorn error logger
    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_error.handlers = [file_handler]
    uvicorn_error.setLevel(logging.INFO)
    uvicorn_error.propagate = False

    # Configure main uvicorn logger
    uvicorn_main = logging.getLogger("uvicorn")
    uvicorn_main.handlers = [file_handler]
    uvicorn_main.setLevel(logging.INFO)
    uvicorn_main.propagate = False


logger = logging.getLogger(__name__)

WORKER_ID = str(os.getpid())
SCHEDULER_LOCK_KEY = "siu:scheduler:lock"
SCHEDULER_LOCK_TIMEOUT_SECONDS = 15
NUM_WORKER_TASKS_PER_PROCESS = 2


def setup_jinja2_env():
    """Setup Jinja2 environment with custom filters and globals."""
    template_loader = jinja2.FileSystemLoader(os.path.join(BASE_DIR, "server", "templates"))

    env = jinja2.Environment(
        loader=template_loader,
        autoescape=True,
        extensions=["jinja2.ext.do", "jinja2.ext.loopcontrols"],
        variable_start_string="{{",
        variable_end_string="}}",
        block_start_string="{%",
        block_end_string="%}",
    )

    def safe_filter(value):
        return Markup(value)

    def default_if_none(value, default=""):
        return value if value is not None else default

    def static(path):
        """Generate URL for static file"""
        return f"/static/{path}"

    def settings_value(name):
        """Get a value from Django settings"""
        from jad import settings

        return getattr(settings, name, "")

    def urlencode_path(p):
        return urllib.parse.quote(p)

    def extract_route_from_path(p):
        return p.strip("/").split("/")[0]

    def strftime_filter(date, format_string):
        """Format datetime using strftime - compatible with Django date filter"""
        if date is None:
            return ""
        try:
            return date.strftime(format_string)
        except (ValueError, AttributeError):
            return str(date)

    env.filters.update(
        {
            "safe": safe_filter,
            "default_if_none": default_if_none,
            "urlencode_path": urlencode_path,
            "extract_route_from_path": extract_route_from_path,
            "currency_symbol": currency_symbol,
            "sublocation_format": sublocation_format,
            "status_color": status_color,
            "strftime": strftime_filter,
        }
    )

    env.globals.update(
        {
            "static": static,
            "settings_value": settings_value,
            "get_static_prefix": lambda: "/static/",
            "JAD_VERSION": JAD_VERSION,
            "current_year": datetime.now(dt_timezone.utc).year,
        }
    )

    return env


jinja2_env = setup_jinja2_env()


def get_cookie_from_scope(scope, cookie_name):
    """Extract cookie value from ASGI scope for both HTTP and WebSocket."""
    if "cookies" in scope:
        return scope["cookies"].get(cookie_name)

    headers = dict(scope["headers"])
    if b"cookie" in headers:
        cookie_string = headers[b"cookie"].decode()
        cookies = dict(cookie.split("=", 1) for cookie in cookie_string.split("; "))
        return cookies.get(cookie_name)
    return None


async def parse_body(receive):
    """Parse the request body."""
    body = b""
    more_body = True

    while more_body:
        message = await receive()
        body += message.get("body", b"")
        more_body = message.get("more_body", False)
        if message.get("type") == "http.disconnect":
            return None

    return body

async def parse_form_data(receive):
    """Parse the request body as form data."""
    body = await parse_body(receive)
    form_data = urllib.parse.parse_qs(body.decode())
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {k: (v[0] if isinstance(v, list) and v else '') for k, v in form_data.items()}

def get_query_params(scope):
    """Extract query parameters from ASGI scope."""
    query_string = scope.get("query_string", b"").decode()
    if not query_string:
        return {}
    return dict(urllib.parse.parse_qsl(query_string))




async def send_html_response(send, scope, status, html_content, headers=None, multi_body=False, first_body=False, last_body=False):
    """Helper function to send HTML responses."""

    if scope["type"] == "http":
        if headers is None:
            headers = []

        headers.append([b"content-type", b"text/html"])
        if not multi_body or first_body:
            await send(
                {
                    "type": "http.response.start",
                    "status": status,
                    "headers": headers,
                }
            )
        await send(
            {
                "type": "http.response.body",
                "body": html_content.encode(),
                "more_body": multi_body and not last_body,
            }
        )
    elif scope["type"] == "websocket":
        await send(
            {
                "type": "websocket.send",
                "text": json.dumps(
                    {"request_id": scope.get("request_id"), "html_content": html_content, "status": status, "headers": headers}, cls=SiuJSONEncoder
                ),
            }
        )


async def send_json_response(send, scope, status, json_content, headers=None):
    """Helper function to send JSON responses."""

    if scope["type"] == "http":
        if headers is None:
            headers = []

        headers.append([b"content-type", b"application/json"])

        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": headers,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": json.dumps(json_content, cls=SiuJSONEncoder).encode(),
            }
        )
    elif scope["type"] == "websocket":
        await send(
            {"type": "websocket.send", "text": json.dumps({"request_id": scope.get("request_id"), "json_content": json_content}, cls=SiuJSONEncoder)}
        )


async def send_raw_response(send, scope, status, content, headers=None):
    """Helper function to send raw responses with provided headers."""
    if headers is None:
        headers = []

    if scope["type"] == "http":
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": headers,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": content.encode() if isinstance(content, str) else content,
            }
        )
    elif scope["type"] == "websocket":
        # Decide on a WebSocket representation if needed, or raise an error
        # For now, let's assume raw responses are not sent over WebSockets
        pass


async def get_user(user_id):
    """Get user data from database."""
    async with get_pg().acquire() as conn:
        return await conn.fetchrow(
            "SELECT id, is_external, supply_rights, order_rights, profit_rights, suggestions_rights, marketing_rights, integration_rights, is_authenticated, username, is_siu_employee, is_dev, butt_key FROM accounts_user WHERE id = $1",
            int(user_id),
        )


async def default_context_data():
    return {
        "FAVICON_FILE": "favicon.ico",
    }

async def http_handler(scope, receive, send):
    cpu_counter = time.process_time()
    time_counter = time.perf_counter()
    handler_name = "unknown_handler"
    session = None
    path_args = {}
    roles = frozenset()
    headers = []
    sessionid = None
    new_sessionid = None
    request_id = None
    auth_header_val = None
    basic_auth_passed = False

    try:
        path = scope["path"]
        method = scope["method"]
        accept_header = next((value.decode() for key, value in scope.get("headers", []) if key.lower() == b"accept"), "")
        scope["is_browser"] = "text/html" in accept_header.lower()

        logger.info(f"HTTP Request: {method} {path}")

        scope["query_params"] = get_query_params(scope)
        for h_name, h_value in scope.get("headers", []):
            if h_name == b'authorization' or h_name == b'api-key':
                auth_header_val = h_value.decode('utf-8', errors='ignore')
                break

        if path.startswith("/doorgelezen/v1/"):
            username = await get_redis().get("siu:doorgelezen:api:username")
            password = await get_redis().get("siu:doorgelezen:api:password")
            if not username or not password:
                await send_json_response(send, scope, 401, {"error": "Unauthorized"}, headers=headers)
                return
            if auth_header_val and auth_header_val.lower().startswith("basic "):
                credentials_b64 = auth_header_val.split(" ", 1)[1]
                credentials_str = base64.b64decode(credentials_b64).decode("utf-8")
                if credentials_str != f"{username.decode()}:{password.decode()}":
                    await send_json_response(send, scope, 401, {"error": "Unauthorized"}, headers=headers)
                    return
        elif auth_header_val and auth_header_val.lower().startswith("basic "):
            try:
                basic_auth_passed = True
                credentials_b64 = auth_header_val.split(" ", 1)[1]
                credentials_bytes = base64.b64decode(credentials_b64)
                credentials_str = credentials_bytes.decode('utf-8')
                client_id, client_secret = credentials_str.split(":", 1)

                auth_result = await get_api_key_permissions(client_id, client_secret)

                if auth_result:
                    roles, user, api_id = auth_result
                    scope['user'] = user
                    scope['roles'] = roles
                    scope['api_id'] = api_id
                    logger.info(f"Basic authentication successful for client_id: {client_id}. Roles: {roles}")
                else:
                    session, roles, new_sessionid, user = await auth.get_user_session_and_roles(None)

            except Exception as e:
                logger.error(f"Error processing Basic Auth header: {e}", exc_info=True)
                await send_json_response(send, scope, 400, {"error": "Malformed Authorization header"}, headers=headers)
                return
        elif auth_header_val and auth_header_val.lower().startswith('bearer '):
            # Skip bearer validation for goedgepickt customprovider endpoint that handles its own authentication
            if path == '/goedgepickt/customprovider/':
                pass
            else:
                token = auth_header_val.split(' ', 1)[1]
                bearer_roles, bearer_user = await auth.validate_bearer_token(token)
                if not bearer_roles and not bearer_user:
                    logger.warning("Invalid bearer token provided")
                    await send_json_response(send, scope, 401, {"error": "Invalid or expired token"})
                    return
                roles = bearer_roles
                scope['user'] = bearer_user
                logger.info(f"Bearer token auth successful for user {bearer_user['id'] if bearer_user else 'None'}. Roles: {roles}")
        elif auth_header_val == 'gYhS7jjLjHkJvjDiTW42oUyvh9fAt76n': # TODO(danilo) v0.0.1 tumfur, delete this
            scope['user'] = 55
            scope['api_id'] = 71
            roles = {'external', 'authenticated'}
        else:
            sessionid = get_cookie_from_scope(scope, "sessionid")
            scope["sessionid"] = sessionid

            session, roles, new_sessionid, user = await auth.get_user_session_and_roles(sessionid)

            if user:
                scope['user'] = user
                scope['roles'] = roles
                logger.info(f"Session authentication for user_id: {user['id']}. Roles: {roles}")
            else:
                logger.info(f"Anonymous session. Roles: {roles}")

            if new_sessionid:
                cookie_val_str = f"sessionid={new_sessionid}; Path=/; HttpOnly; SameSite=Lax"
                headers.append([b"set-cookie", cookie_val_str.encode()])

        subdomain = None
        subdomain_role = None
        host_header = next((value for key, value in scope['headers'] if key == b'host'), None)
        if host_header:
            host = host_header.decode('utf-8').split(':')[0]
            parts = host.split('.')
            if settings.DEBUG:
                if len(parts) == 2:
                    subdomain = parts[0]
                elif len(parts) == 3:
                    subdomain_role = parts[0]
                    subdomain = parts[1]
            else:
                if len(parts) >= 3:
                    subdomain_role = parts[0]
                    subdomain = parts[1]
                elif len(parts) == 2:
                    subdomain = parts[0]

        # Get the appropriate handler for this path and roles
        handler_info = get_handler_for_path(path, roles, subdomain=subdomain, subdomain_role=subdomain_role)
        if not handler_info:
            if scope.get("is_browser") and roles == frozenset({"public"}):
                all_roles_set = set(ROLE_PRIORITIES) - {"public"}
                if get_handler_for_path(path, all_roles_set, subdomain=subdomain, subdomain_role=subdomain_role):
                    quoted_next_path = urllib.parse.quote(path)
                    login_location = f"/inloggen/?next={quoted_next_path}"

                    redirect_headers = headers + [[b"location", login_location.encode()]]
                    await send_html_response(send, scope, 302, "", redirect_headers)
                    return
            elif basic_auth_passed:
                return await send_json_response(send, scope, 401, {"error": f"Invalid or unauthorized API key, only {', '.join(roles)} endpoints are allowed"}, headers=headers)
            await send_json_response(send, scope, 404, {"error": f"Not found: {path} for user with roles {roles}"}, headers=headers)
            return
        elif handler_info == "ROLE_MISMATCH":
            logger.warning(roles)
            logger.warning(roles)
            logger.warning(roles)
            # If it's a browser, redirect to login instead of JSON 403
            if scope.get("is_browser"):
                quoted_next_path = urllib.parse.quote(scope.get("path", "/"))
                login_location = f"/inloggen/?next={quoted_next_path}"
                redirect_headers = headers + [[b"location", login_location.encode()]]
                await send_html_response(send, scope, 302, "", redirect_headers)
                return
            await send_json_response(send, scope, 403, {"error": "Forbidden - Insufficient permissions"}, headers=headers)
            return
        else:
            role, handler_name, path_args, rights_required = handler_info
            if rights_required != "NO_RIGHTS_REQUIRED":
                for right_required in rights_required.split(","):
                    if not user[right_required]:
                        await send_html_response(send, scope, 403, "Forbidden, the user has the correct role but is missing permissions", headers)
                        return

        # Split the handler path into parts
        parts = handler_name.split(".")
        function = parts[-1]  # Last part is always the function name
        module = ".".join(parts[:-1])  # Everything else is the module path

        handler_module = importlib.import_module(f"server.{role}.{module}")
        handler_function = getattr(handler_module, function, None)

        if handler_function:
            try:
                scope["response_headers"] = headers
                if sessionid:
                    request_id = "".join(random.choices(string.ascii_letters + string.digits, k=16))
                    scope["request_id"] = request_id

                from server.sentry import sentry_sdk
                current_scope = sentry_sdk.get_current_scope()
                if current_scope and current_scope.transaction:
                    current_scope.transaction.name = f"uvicorn.{handler_name}"
                    with sentry_sdk.start_span(op="uvicorn", description=handler_name) as span:
                        await handler_function(scope, receive, send, session, **path_args)
                else:
                    with sentry_sdk.start_transaction(op="uvicorn", name=f"uvicorn.{handler_name}") as transaction:
                        with sentry_sdk.start_span(op="uvicorn", description=handler_name) as span:
                            await handler_function(scope, receive, send, session, **path_args)
            except jinja2.exceptions.TemplateNotFound as e:
                logger.exception(f"Template not found for {scope.get('path', 'unknown path')}: {e}")
                template = jinja2_env.get_template("404.html")
                context = await default_context_data()
                html_content = template.render(context)
                await send_html_response(send, scope, 404, html_content, headers)
            except Exception as e:
                current_handler_name = handler_name if handler_name != "unknown_handler" else f"(lookup failed for {scope.get('path', 'unknown path')})"
                logger.exception(f"Unhandled exception in handler {current_handler_name} for {scope.get('method', 'unknown method')} {scope.get('path', 'unknown path')}", exc_info=True)
                try:
                    await send_html_response(send, scope, 500, "Internal Server Error", headers)
                except Exception as send_exc:
                    logger.error(f"Failed to send error response: {send_exc}")
        else:
            logger.error(f"Handler function {function} not found in module {module} for handler {handler_name}")
            await send_html_response(send, scope, 500, f"Handler {handler_name} not implemented", headers)

    finally:
        # --- Performance Recording ---
        cpu_time = (time.process_time() - cpu_counter) * 1000
        wall_time = (time.perf_counter() - time_counter) * 1000

        # Log performance
        request_info = f"{scope.get('method', '?')} {scope.get('path', '?')}"
        request_id_info = f" (req_id: {request_id})" if request_id else ""
        logger.info(f"UVI {handler_name} {request_info}{request_id_info} cpu: {cpu_time:6.2f}ms, wall: {wall_time:6.2f}ms")

async def websocket_handler(scope, receive, send):
    path = scope["path"]


    sessionid = get_cookie_from_scope(scope, "sessionid")
    scope["sessionid"] = sessionid
    logger.debug((f"sessionid: {sessionid}", path))
    session, roles, new_sessionid, user = await auth.get_user_session_and_roles(sessionid)

    if not user:
        await send({"type": "websocket.close", "code": 1008})
        return
    pubsub_listener_task = None
    connection_id = uuid.uuid4().hex
    scope['connection_id'] = connection_id
    scope['user'] = user
    scope['roles'] = roles
    user_id = user['id']
    async def update_connection_location(current_page_identifier):
        nonlocal connection_id, user_id
        ttl_seconds = 3600
        await ws_update_connection(connection_id, user_id, current_page_identifier, ttl_seconds)

    async def redis_listen_and_forward():
        ps = None
        try:
            ps = get_redis().pubsub()
            subscribe_channel = f"ws_messages:{connection_id}"
            await ps.subscribe(subscribe_channel)
            while True:
                message = await ps.get_message(ignore_subscribe_messages=True, timeout=2.0)
                if message and message.get("type") == "message":
                    data_to_send_bytes = message["data"]
                    if data_to_send_bytes:
                        data_str = data_to_send_bytes.decode('utf-8')
                        await send({"type": "websocket.send", "text": data_str})
        except Exception as e:
            logger.error(f"WebSocket {connection_id}: Error in redis_listen_and_forward: {e}", exc_info=True)
        finally:
            if ps:
                await ps.unsubscribe(subscribe_channel)
                await ps.close()

    if path.endswith('/ws/') or path == '/ws':
        handler_info = get_handler_for_path(path, roles)
        if handler_info and path != "/ws/":
            role, handler_name, path_args, rights_required = handler_info
            if rights_required != "NO_RIGHTS_REQUIRED":
                for right_required in rights_required.split(","):
                    if not user[right_required]:
                        await send({"type": "websocket.close", "code": 1008})
                        return
            parts = handler_name.split(".")
            function = parts[-1]
            module = ".".join(parts[:-1])
            try:
                handler_module = importlib.import_module(f"server.{role}.{module}")
                handler_function = getattr(handler_module, function, None)
                if handler_function and hasattr(handler_function, '__name__') and 'websocket' in handler_function.__name__:
                    await handler_function(scope, receive, send, session, **path_args)
                    return
            except Exception as e:
                logger.error(f"Error handling WebSocket route {path}: {e}")
                await send({"type": "websocket.close", "code": 1011})
                return

    if path == "/ws/":
        await send({"type": "websocket.accept"})
        pubsub_listener_task = asyncio.create_task(redis_listen_and_forward())

        try:
            while True:
                event = await receive()
                if event["type"] == "websocket.receive":
                    data = json.loads(event.get("text", ""))
                    if requested_endpoint := data.get("endpoint"):
                        if request_id := data.get("requestId"):
                            scope["request_id"] = request_id
                        if attributes := data.get("attributes"):
                            scope["attributes"] = attributes
                            # These attributes should be also filled in with form data in post requests

                        handler_info = get_handler_for_path(requested_endpoint, roles)
                        if not handler_info:
                            await send({"type": "websocket.close", "code": 1008})
                            return
                        logger.info(f"WS handler_info {requested_endpoint} {handler_info}")
                        if handler_info == "ROLE_MISMATCH":
                            await send({"type": "websocket.close", "code": 1008})
                            return
                        role, handler_name, path_args, rights_required = handler_info
                        if rights_required != "NO_RIGHTS_REQUIRED":
                            for right_required in rights_required.split(","):
                                if not user[right_required]:
                                    await send({"type": "websocket.close", "code": 1008})
                                    return
                        parts = handler_name.split(".")
                        function = parts[-1]
                        module = ".".join(parts[:-1])
                        handler_module = importlib.import_module(f"server.{role}.{module}")
                        handler_function = getattr(handler_module, function, None)
                        if handler_function:
                            original_path = scope.get("path")
                            scope["path"] = requested_endpoint
                            await handler_function(scope, receive, send, session, **path_args)
                            scope["path"] = original_path
                        else:
                            await send({"type": "websocket.close", "code": 1008})
                            return
                    elif data.get("function") == "ping":
                        await update_connection_location(data.get("location"))

                elif event["type"] == "websocket.disconnect":
                    break
            return
        except Exception as e:
            raise e
        finally:
            try:
                await ws_cleanup_connection(connection_id)
            except Exception as e:
                logger.warning(f"presence cleanup failed for {connection_id}: {e}")

            if pubsub_listener_task and not pubsub_listener_task.done():
                pubsub_listener_task.cancel()
    else:
        await send({"type": "websocket.close", "code": 1008})


async def static_file_handler(scope, receive, send):
    """Handle static file requests."""
    path = scope["path"]
    if not path.startswith("/static/"):
        return False

    relative_path = path[8:]
    static_root = os.path.join(BASE_DIR, "static")
    file_path = os.path.join(static_root, relative_path)

    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        await send_html_response(send, scope, 404, "File not found")
        return True

    content_type, _ = mimetypes.guess_type(file_path)
    content_type = content_type or "application/octet-stream"

    with open(file_path, "rb") as f:
        content = f.read()

    headers = [
        [b"content-type", content_type.encode()],
        [b"content-length", str(len(content)).encode()],
    ]
    if not DEBUG and content_type == "text/css":
        headers.append([b"Cache-Control", b"public, max-age=604800"])

    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": headers,
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": content,
        }
    )
    return True


def get_application():
    """Create and return the ASGI application."""
    is_scheduler_leader = False
    scheduler_task = None
    worker_tasks = []

    async def run_scheduler():
        """Periodically checks and schedules cron jobs if this instance is the leader."""
        logger.info(f"Scheduler {WORKER_ID} starting up...")

        # Initial random sleep to allow worker start and prevent thundering herd on restart
        # Cursor idea, maybe unnecessary
        await asyncio.sleep(1)

        lock_value = await get_redis().get(SCHEDULER_LOCK_KEY)
        if not (lock_value and lock_value.decode() == WORKER_ID):
            raise Exception(f"Scheduler {WORKER_ID} is not the leader or lost lock. Current leader: {lock_value.decode() if lock_value else 'None'}. Stopping.")

        for job_function, job_info in (await get_cron_jobs()).items():
            if not job_info["enabled"]:
                continue

            job_queue = job_info["queue"]

            calculated_next_run_ts, job_type = await get_next_run_ts(job_info, job_function)

            await enqueue_job(job_function, job_info["args"], job_info["kwargs"], job_queue, calculated_next_run_ts, job_type)


    async def app(scope, receive, send):
        nonlocal is_scheduler_leader, scheduler_task, worker_tasks
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    try:
                        logger.info(f"Worker {WORKER_ID} starting lifespan.startup")
                        from server.pools import create_and_init_pools
                        await create_and_init_pools()
                        logger.info(f"Worker {WORKER_ID} pools created successfully")

                        try:
                            hc = await ws_health_check_cleanup()
                            logger.info(f"Presence health cleanup: {hc}")
                        except Exception as e:
                            logger.warning(f"Presence health cleanup failed: {e}")

                        await start_frontend_monitoring()
                        logger.info(f"Worker {WORKER_ID} frontend monitoring started")

                        acquired_lock = await get_redis().set(
                            SCHEDULER_LOCK_KEY,
                            WORKER_ID,
                            nx=True,
                            ex=SCHEDULER_LOCK_TIMEOUT_SECONDS
                        )
                        if acquired_lock:
                            is_scheduler_leader = True
                            logger.info(f"Worker {WORKER_ID} acquired scheduler lock and is the leader.")
                            scheduler_task = asyncio.create_task(run_scheduler())
                        else:
                            logger.info(f"Worker {WORKER_ID} did not acquire scheduler lock. Will run as worker only.")

                        for i in range(NUM_WORKER_TASKS_PER_PROCESS):
                            task = asyncio.create_task(worker_loop(i + 1))
                            worker_tasks.append(task)

                        await send({"type": "lifespan.startup.complete"})
                    except Exception as e:
                        logger.error(f"Worker {WORKER_ID} lifespan startup failed: {type(e).__name__}: {e}", exc_info=True)
                        await send({"type": "lifespan.startup.failed", "message": f"Worker {WORKER_ID} startup failed: {e}"})
                elif message["type"] == "lifespan.shutdown":
                    initiate_shutdown()

                    await stop_frontend_monitoring()

                    if scheduler_task and not scheduler_task.done():
                        scheduler_task.cancel()
                        try:
                            logger.info(f"Worker {WORKER_ID} awaiting scheduler_task cancellation...")
                            await scheduler_task
                            logger.info(f"Worker {WORKER_ID} scheduler_task cancelled and awaited.")
                        except asyncio.CancelledError:
                            logger.info(f"Scheduler task ({WORKER_ID}) cancelled successfully during shutdown.")
                        except Exception:
                            logger.exception(f"Exception during scheduler task ({WORKER_ID}) cancellation.")

                    for task in worker_tasks:
                        if task and not task.done():
                            task.cancel()
                    if worker_tasks:
                        logger.info(f"Worker {WORKER_ID} awaiting cancellation of {len(worker_tasks)} job worker tasks...")
                        results = await asyncio.gather(*[task for task in worker_tasks if task], return_exceptions=True)
                        logger.info(f"Worker {WORKER_ID} finished awaiting job worker tasks.")
                        for i, result in enumerate(results):
                            if isinstance(result, Exception):
                                logger.error(f"Worker {WORKER_ID} - Job worker task {i+1} failed with an exception:", exc_info=result)

                    if is_scheduler_leader and get_redis():
                        logger.info(f"Worker {WORKER_ID} attempting to release scheduler lock...")
                        lock_value = await get_redis().get(SCHEDULER_LOCK_KEY)
                        if lock_value and lock_value.decode() == WORKER_ID:
                            await get_redis().delete(SCHEDULER_LOCK_KEY)
                        logger.info(f"Worker {WORKER_ID} scheduler lock release attempt finished.")

                    logger.info(f"Worker {WORKER_ID} closing pools...")
                    from server.pools import close_pools
                    await close_pools()
                    logger.info(f"Worker {WORKER_ID} pools closed.")
                    logger.info(f"Worker {WORKER_ID} sending lifespan.shutdown.complete...")
                    await send({"type": "lifespan.shutdown.complete"})
                    logger.info(f"Worker {WORKER_ID} lifespan.shutdown.complete sent.")
                    return
        elif scope["type"] == "http":
            if scope["path"] == "/service-worker.js":
                scope["path"] = "/static/service_worker.js"
            if await static_file_handler(scope, receive, send):
                return
            await http_handler(scope, receive, send)
        elif scope["type"] == "websocket":
            await websocket_handler(scope, receive, send)

    return app


async def save_session(session):
    session_id = session.get("session_key")
    if not session_id:
        raise Exception("Session ID not found")
    session_key = f":1:django.contrib.sessions.cache{session_id}"
    await get_redis().set(session_key, pickle.dumps(session), ex=86400)  # expire in 1 day

async def delete_session(scope):
    session_id = scope.get("sessionid")
    session_key = f":1:django.contrib.sessions.cache{session_id}"
    await get_redis().delete(session_key)

application = get_application()
application = SentryAsgiMiddleware(application)
