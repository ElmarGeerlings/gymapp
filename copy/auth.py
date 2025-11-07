import base64
import datetime
import hashlib
import json
import pickle
import secrets
import uuid
from typing import Optional, Dict, Tuple, Set
import logging

import bcrypt

from jad.settings import JAD_API_KEY
from server.pools import get_pg, get_redis
from siu_base.http import req
from secrets import token_urlsafe
from jad import settings
from server.encryption import decrypt

logger = logging.getLogger(__name__)

# Bearer/OAuth token settings
TOKEN_TTL_SECONDS = 3600*24*30  # 30 days default expiry for access tokens

_PROTECTED_TYPES = (
    type(None),
    int,
    float,
    datetime.datetime,
    datetime.date,
    datetime.time,
)


def is_protected_type(obj):
    """Determine if the object instance is of a protected type.

    Objects of protected types are preserved as-is when passed to
    force_str(strings_only=True).
    """
    return isinstance(obj, _PROTECTED_TYPES)


def force_bytes(s, encoding="utf-8", strings_only=False, errors="strict"):
    """
    Similar to smart_bytes, except that lazy instances are resolved to
    strings, rather than kept as lazy objects.

    If strings_only is True, don't convert (some) non-string-like objects.
    """
    # Handle the common case first for performance reasons.
    if isinstance(s, bytes):
        if encoding == "utf-8":
            return s
        else:
            return s.decode("utf-8", errors).encode(encoding, errors)
    if strings_only and is_protected_type(s):
        return s
    if isinstance(s, memoryview):
        return bytes(s)
    return str(s).encode(encoding, errors)


def pbkdf2(password, salt, iterations, dklen=0, digest=None):
    """Return the hash of password using pbkdf2."""
    if digest is None:
        digest = hashlib.sha256
    dklen = dklen or None
    password = force_bytes(password)
    salt = force_bytes(salt)
    return hashlib.pbkdf2_hmac(
        digest().name,
        password,
        salt,
        iterations,
        dklen,
    )


async def check_user_exists(username: str) -> bool:
    """Check if user exists in database"""
    async with get_pg().acquire() as conn:
        result = await conn.fetchrow(
            "SELECT id FROM accounts_user WHERE username = $1", username
        )
        return result is not None


async def create_siu_employee_user(username: str, post_data: dict) -> bool:
    """Handle @stockitup.nl user creation from external service"""
    try:
        # Convert form data to dict for external API
        if isinstance(post_data, dict):
            data = post_data
        else:
            # Convert parsed form data to regular dict
            data = {k: v[0] if isinstance(v, list) and v else v for k, v in post_data.items()}

        res, response, ex, req_event = req(
            "json",
            method="post",
            url="https://buttler.stockitup.nl/login-siu/",
            data=data,
            skip_event=True,
        )

        if res and res.get("user"):
            user_data = res.get("user")

            # Create user in database
            async with get_pg().acquire() as conn:
                await conn.execute("""
                    INSERT INTO accounts_user (
                        username, password, email, first_name, last_name,
                        is_active, is_siu_employee, is_dev, change_roles,
                        supply_rights, orders_rights, profit_rights, suggestions_rights,
                        marketing_rights, integration_rights, dashboard_orders_rights,
                        dashboard_returns_rights, dashboard_products_rights,
                        dashboard_suggestions_rights, dashboard_planning_rights,
                        dashboard_sales_rights, cashier_rights, account_creation_rights,
                        is_staff, butt_key
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25)
                    ON CONFLICT (username) DO UPDATE SET
                        password = EXCLUDED.password,
                        email = EXCLUDED.email,
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        is_active = EXCLUDED.is_active,
                        butt_key = EXCLUDED.butt_key
                """,
                    user_data.get("username"),
                    user_data.get("password"),
                    user_data.get("email"),
                    user_data.get("first_name"),
                    user_data.get("last_name"),
                    user_data.get("is_active", True),
                    True,  # is_siu_employee
                    True,  # is_dev
                    True,  # change_roles
                    True,  # supply_rights
                    True,  # orders_rights
                    True,  # profit_rights
                    True,  # suggestions_rights
                    True,  # marketing_rights
                    True,  # integration_rights
                    True,  # dashboard_orders_rights
                    True,  # dashboard_returns_rights
                    True,  # dashboard_products_rights
                    True,  # dashboard_suggestions_rights
                    True,  # dashboard_planning_rights
                    True,  # dashboard_sales_rights
                    True,  # cashier_rights
                    True,  # account_creation_rights
                    True,  # is_staff
                    user_data.get("butt_key")
                )

            logger.warning(f'Created user {user_data.get("username")}')
            return True

        elif ex:
            logger.error(f"Failed to auth buttler user: {username} - {ex}")
        else:
            logger.error(f"Failed to auth buttler user: {username} - {response}")

    except Exception as e:
        logger.error(f"Error creating external user: {e}")

    return False


async def get_api_key_permissions(client_id: str, client_secret: str):
    """
    Validates an API client_id and client_secret.

    If successful, returns a tuple containing the user's granted roles (a set of strings),
    the full user record, and the client_id.

    Args:
        client_id: The API client ID.
        client_secret: The plain text API client secret.

    Returns:
        A tuple (roles, user_record, client_id) on success.
        Returns None if validation fails at any point.
    """
    async with get_pg().acquire() as conn:
        api_roles_map = {
            "dev_routes": "dev",
            "sellfiller_routes": "sellfiller",
            "external_routes": "external",
            "thirdparty_routes": "thirdparty",
            "authenticated_routes": "authenticated",
        }

        role_fields_to_select = ", ".join([f"ak.{field_name}" for field_name in api_roles_map.keys()])

        # Query by client_id, fetch the stored client_secret, and join with user table
        query = f"""
            SELECT
                ak.id,
                ak.client_id,
                ak.client_secret,
                u.*,
                {role_fields_to_select}
            FROM api_key ak
            JOIN accounts_user u ON ak.user_id = u.id
            WHERE ak.client_id = $1
        """

        user_record = await conn.fetchrow(query, client_id)
        if not user_record:
            logger.warning(f"API key lookup failed for client_id: '{client_id}'")
            return None

        client_secret_encrypted = user_record["client_secret"]

        if client_secret_encrypted:
            try:
                client_secret_decrypted = decrypt(client_secret_encrypted)
            except Exception as e:
                logger.error(f"Error decoding/decrypting client_secret for client_id '{client_id}': {e}", exc_info=True)
                return None # Error during decryption means failure
        else:
            logger.warning(f"Stored client_secret is empty for client_id: '{client_id}'")
            return None


        if client_secret_decrypted == client_secret:
            roles = {'public'}
            for db_field_name, role_name in api_roles_map.items():
                if user_record.get(db_field_name):
                    roles.add(role_name)

            logger.info(f"API client_id '{client_id}' validated successfully for user_id: {user_record['id']}. Roles: {roles}")
            return roles, user_record, user_record['id']
        else:
            logger.warning(f"API client_secret mismatch for client_id: '{client_id}'")
            return None


async def authenticate(username: str, password: str):
    """
    Authenticate a user with username and password.
    Returns user data if credentials are valid, None otherwise.
    """
    logger.debug(f"Attempting authentication for username: {username}")

    query = """
        SELECT id, username, password, email, first_name, last_name, is_active, two_factor_enabled
        FROM accounts_user WHERE username = $1
    """
    async with get_pg().acquire() as conn:
        row = await conn.fetchrow(query, username)

        if not row:
            logger.info(f"No user found with username: {username}")
            return None

        # Check if password matches using bcrypt
        encoded = row["password"]
        if not encoded.startswith("bcrypt$") and not encoded.startswith("pbkdf2_sha256$"):
            logger.error(f"Invalid password format for user {username}")
            return None

        if encoded.startswith("bcrypt$"):
            logger.debug(f"Using bcrypt authentication for user {username}")
            _, salt, hashed = encoded.split("$")
            if bcrypt.hashpw(password.encode(), salt.encode()).decode() != hashed:
                logger.info(f"Invalid bcrypt password for user {username}")
                return None
        else:  # pbkdf2_sha256
            logger.debug(f"Using pbkdf2_sha256 authentication for user {username}")
            # Split the hash into its components
            algorithm, iterations, salt, hash = encoded.split("$", 3)
            decoded = {
                "algorithm": algorithm,
                "hash": hash,
                "iterations": int(iterations),
                "salt": salt,
            }
            assert password is not None
            assert salt and "$" not in salt
            iterations = int(iterations) if iterations else 260000
            hash = pbkdf2(password, salt, iterations, digest=hashlib.sha256)
            hash = base64.b64encode(hash).decode("ascii").strip()
            encoded_2 = "%s$%d$%s$%s" % ("pbkdf2_sha256", iterations, salt, hash)

            logger.debug(f"Expected hash: {encoded}")
            logger.debug(f"Computed hash: {encoded_2}")

            if not secrets.compare_digest(force_bytes(encoded), force_bytes(encoded_2)):
                logger.info(f"Invalid pbkdf2_sha256 password for user {username}")
                return None

        logger.debug(f"Successfully authenticated user {username}")
        return {
            "id": row["id"],
            "username": row["username"],
            "email": row["email"],
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "is_active": row["is_active"],
            "two_factor_enabled": row["two_factor_enabled"],
        }


async def get_user_id_from_session(session):
    if "_auth_user_id" in session:
        try:
            return int(session["_auth_user_id"])
        except:
            return 0
    return 0


async def get_user_session_and_roles(sessionid: str = None):
    """Get user session and roles from Redis. Returns (session, roles, new_sessionid) where new_sessionid is only set if a new anonymous session was created."""
    needs_anonymous = True
    new_sessionid = None

    if sessionid:
        # Django's session key format with :1: prefix for database 1
        session_key = f":1:django.contrib.sessions.cache{sessionid}"
        session_data = await get_redis().get(session_key)

        if session_data:
            try:
                session = pickle.loads(session_data)
                if user_id := await get_user_id_from_session(session):
                    roles, user = await get_user_role(user_id)
                    result = session, roles, None, user
                else:
                    result = session, {"public"}, None, None
                needs_anonymous = False
            except Exception:
                logger.error("Invalid session data", exc_info=True)

    if needs_anonymous:
        new_sessionid = str(uuid.uuid4())
        session = {"anonymous": True, "session_key": new_sessionid, "_auth_user_id": None}
        session_key = f":1:django.contrib.sessions.cache{new_sessionid}"
        await get_redis().set(session_key, pickle.dumps(session), ex=86400)  # expire in 1 day
        result = session, {"public"}, new_sessionid, None

    if settings.DEBUG:
        first_user = await get_pg().fetchrow("SELECT id FROM accounts_user WHERE is_active = TRUE ORDER BY id LIMIT 1")
        if first_user:
            user_id = first_user['id']
            roles, user = await get_user_role(user_id)
            result = result[0], roles, result[2], user
            logger.info(f"DEBUG auto-login for user_id: {user_id}. Roles: {roles}")

    if "session_key" not in session:
        from server.asgi import save_session
        session["session_key"] = sessionid
        await save_session(session)

    return result


async def get_user_role(user_id: int) -> Set[str]:
    """Determine user roles based on session data."""
    roles = set()

    # Query user properties from database
    async with get_pg().acquire() as conn:
        user = await conn.fetchrow(
            """
            SELECT *
            FROM accounts_user
            WHERE id = $1 AND is_active = TRUE
        """,
            user_id,
        )

        if not user:
            return {"public"}, None

        roles.add("authenticated")

        # Add all applicable roles
        if user["is_dev"]:
            roles.add("dev")
        if user["is_seller"]:
            if user["is_fulfiller"]:
                roles.add("sellfiller")
            roles.add("seller")
        if user["is_fulfiller"]:
            roles.add("fulfiller")
        if user["is_external"]:
            roles.add("external")

    return roles, user

async def issue_access_token(user_id: int, roles: Set[str]) -> Tuple[str, int]:
    """Generate and store an access token for the given user.

    Returns a tuple (token, expires_in_seconds).
    """
    token = token_urlsafe(32)
    # Store user_id and roles as a small JSON payload
    token_payload = {
        "uid": user_id,
        "roles": list(roles),
    }
    key = f"auth:token:{token}"
    try:
        await get_redis().set(key, json.dumps(token_payload).encode(), ex=TOKEN_TTL_SECONDS)
    except Exception as e:
        logger.error(f"Failed to store access token in Redis: {e}")
        raise
    return token, TOKEN_TTL_SECONDS


async def validate_bearer_token(token: str):
    """Validate a bearer token and return (roles, user_dict) or (None, None) if invalid."""
    if token == JAD_API_KEY:
        return {"buttler"}, None

    key = f"auth:token:{token}"
    try:
        token_data_bytes = await get_redis().get(key)
    except Exception as e:
        logger.error(f"Redis error during bearer token validation: {e}")
        return None, None

    if not token_data_bytes:
        return None, None

    try:
        token_data = json.loads(token_data_bytes)
        user_id = int(token_data.get("uid"))
        roles = set(token_data.get("roles", []))
    except Exception as e:
        logger.error(f"Invalid token payload: {e}")
        return None, None

    # Fetch user to ensure still active
    async with get_pg().acquire() as conn:
        user_row = await conn.fetchrow(
            "SELECT id, username, is_active FROM accounts_user WHERE id = $1",
            user_id,
        )

    if not user_row or not user_row["is_active"]:
        return None, None

    user_dict = {
        "id": user_row["id"],
        "username": user_row["username"],
        "is_authenticated": True,
    }

    return roles, user_dict

async def has_user_access_to_seller(user, seller_id):
    if not user["is_external"]:
        return True
    async with get_pg().acquire() as conn:
        result = await conn.fetchrow(
            "SELECT id FROM accounts_user_sellers WHERE user_id = $1 AND seller_id = $2",
            user["id"],
            seller_id,
        )
        return result is not None