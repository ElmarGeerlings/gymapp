import logging
import json
from datetime import timezone as dt_timezone, datetime
from server.asgi import parse_form_data, send_json_response, parse_body
from server import orders

logger = logging.getLogger(__name__)

async def get_orders(scope, receive, send, session, seller_id):
    try:
        target_seller_id = int(seller_id)
    except ValueError:
        await send_json_response(send, scope, 400, {"code": 400, "message": "Invalid seller_id format. Must be an integer."})
        return

    query_params = scope.get("query_params", {})

    # Parse query parameters
    updated_since = None
    created_since = None
    status = None
    id_gt = None

    if "updated_since" in query_params:
        try:
            updated_since_ms = int(query_params["updated_since"])
            updated_since = datetime.fromtimestamp(updated_since_ms / 1000.0, dt_timezone.utc)
        except (ValueError, TypeError):
            await send_json_response(send, scope, 400, {"code": 400, "message": "Invalid updated_since format. Use milliseconds since epoch."})
            return

    if "created_since" in query_params:
        try:
            created_since_ms = int(query_params["created_since"])
            created_since = datetime.fromtimestamp(created_since_ms / 1000.0, dt_timezone.utc)
        except (ValueError, TypeError):
            await send_json_response(send, scope, 400, {"code": 400, "message": "Invalid created_since format. Use milliseconds since epoch."})
            return

    if "status" in query_params:
        valid_statuses = {
            "OPEN", "COMPLETE", "CANCELED", "BACKORDER", "RETURNED",
            "ERROR", "LVB", "FBA", "PICKUP", "APPOINTMENT",
            "WACHT OP BETALING", "WACHT OP ADRES", "AFHAALPUNT",
            "SENT TO PRINTER", "FRAUD", "ON-HOLD", "BOL.COM LABEL ERROR",
            "SHIPPING ERROR", "DRAFT", "CHECK ADRES"
        }
        if query_params["status"] not in valid_statuses:
            await send_json_response(send, scope, 400, {"code": 400, "message": "Invalid status."})
            return
        status = query_params["status"].upper()

    if "id_gt" in query_params:
        try:
            id_gt = int(query_params["id_gt"])
        except ValueError:
            await send_json_response(send, scope, 400, {"code": 400, "message": "Invalid id_gt format. Must be an integer."})
            return

    page_size = 20
    if "page_size" in query_params:
        try:
            page_size = int(query_params["page_size"])
            if not 1 <= page_size <= 100:
                await send_json_response(send, scope, 400, {"code": 400, "message": "page_size must be between 1 and 100."})
                return
        except ValueError:
            await send_json_response(send, scope, 400, {"code": 400, "message": "Invalid page_size format. Must be an integer."})
            return

    filters = {"os.seller_id": target_seller_id}
    if updated_since:
        filters["o.updated_at__gt"] = updated_since
    if created_since:
        filters["o.created_at__gt"] = created_since
    if status:
        filters["o.status"] = status
    if id_gt:
        filters["o.id__gt"] = id_gt

    # Check if API key ONLY has external role (not authenticated or other roles)
    # When API key auth is used, roles are set in scope
    roles = scope.get('roles', set())
    is_external = roles == {'external'} or roles == {'external', 'public'}

    try:
        response_orders, total_count = await orders.get_orders(
            filters=filters,
            limit=page_size,
            sorting="id",
            sorting_direction="ASC",
            include_profit=False,
            external=is_external
        )
        # Convert datetime fields to ISO format for API response
        for order in response_orders:
            for dt_field in ['created_at', 'updated_at', 'order_date']:
                if order.get(dt_field) and isinstance(order[dt_field], datetime):
                    order[dt_field] = order[dt_field].replace(tzinfo=dt_timezone.utc).isoformat()

        await send_json_response(send, scope, 200, response_orders)
    except Exception as e:
        logger.error(f"Error fetching orders for seller {target_seller_id}: {e}", exc_info=True)
        await send_json_response(send, scope, 500, {"code": 500, "message": "Internal server error fetching orders."})



async def get_order_by_id(scope, receive, send, session, seller_id, order_id):
    try:
        target_seller_id = int(seller_id)
        target_order_id = int(order_id)
    except ValueError:
        await send_json_response(send, scope, 400, {"code": 400, "message": "Invalid seller_id or order_id format. Must be integers."})
        return

    # Check if API key ONLY has external role
    roles = scope.get('roles', set())
    is_external = roles == {'external'} or roles == {'external', 'public'}

    try:
        order_dict = await orders.get_single_order(target_order_id, seller_id=target_seller_id, external=is_external)

        if not order_dict:
            await send_json_response(send, scope, 404, {"code": 404, "message": f"Order {target_order_id} not found for seller {target_seller_id}."})
            return

        # Convert datetime fields to ISO format for API response
        for dt_field in ['created_at', 'updated_at', 'order_date']:
            if order_dict.get(dt_field) and isinstance(order_dict[dt_field], datetime):
                order_dict[dt_field] = order_dict[dt_field].replace(tzinfo=dt_timezone.utc).isoformat()

        await send_json_response(send, scope, 200, order_dict)
    except Exception as e:
        logger.error(f"Error fetching order {target_order_id} for seller {target_seller_id}: {e}", exc_info=True)
        await send_json_response(send, scope, 500, {"code": 500, "message": "Internal server error fetching order."})

async def ship_order(scope, receive, send, session, seller_id, order_id):
    logger.info(f"Attempting to ship order_id: {order_id} for seller_id: {seller_id}")
    try:
        target_seller_id = int(seller_id)
        target_order_id = int(order_id)
    except ValueError:
        await send_json_response(send, scope, 400, {"code": 400, "message": "Invalid seller_id or order_id format. Must be integers."})
        return

    try:
        body = await parse_body(receive)
        data = json.loads(body)
        transporter_code = data.get("transporter")
        track_and_trace = data.get("track_and_trace")
        tracking_url = data.get("tracking_url")

        if not transporter_code:
            await send_json_response(send, scope, 400, {"code": 400, "message": "Missing transporter in request body."})
            return
        elif not track_and_trace:
            await send_json_response(send, scope, 400, {"code": 400, "message": "Missing track_and_trace in request body."})
            return
        elif not tracking_url:
            await send_json_response(send, scope, 400, {"code": 400, "message": "Missing tracking_url in request body."})
            return
    except json.JSONDecodeError:
        await send_json_response(send, scope, 400, {"code": 400, "message": "Invalid JSON in request body."})
        return
    except Exception as e:
        logger.error(f"Error processing request body for ship_order: {e}")
        await send_json_response(send, scope, 400, {"code": 400, "message": "Error processing request body."})
        return

    user_id = scope.get('user', {}).get('id')
    if not user_id:
        await send_json_response(send, scope, 401, {"code": 401, "message": "Unauthorized"})
        return

    process_id, error_message = await orders.ship_order_business(
        order_id=target_order_id,
        transporter_code=transporter_code,
        track_and_trace=track_and_trace,
        tracking_url=tracking_url,
        user_id=user_id,
        seller_id=target_seller_id
    )

    if error_message:
        if "not found" in error_message:
            await send_json_response(send, scope, 404, {"code": 404, "message": error_message})
        else:
            await send_json_response(send, scope, 400, {"code": 400, "message": error_message})
        return

    await send_json_response(send, scope, 202, {"code": 202, "message": f"Shipping process initiated for order {target_order_id}.", "process_id": process_id})

async def create_order(scope, receive, send, session, seller_id):
    try:
        target_seller_id = int(seller_id)
    except ValueError:
        await send_json_response(send, scope, 400, {"code": 400, "message": "Invalid seller_id format. Must be an integer."})
        return

    try:
        data = await parse_form_data(receive)
    except json.JSONDecodeError:
        await send_json_response(send, scope, 400, {"code": 400, "message": "Invalid JSON in request body."})
        return
    except Exception as e:
        logger.error(f"Error processing request body for create_order: {e}")
        await send_json_response(send, scope, 400, {"code": 400, "message": "Error processing request body."})
        return

    user_id = scope.get('user', {}).get('id')
    if not user_id:
        await send_json_response(send, scope, 401, {"code": 401, "message": "Unauthorized"})
        return

    order_id, error_message = await orders.create_new_order(
        user_id=user_id,
        channel='api',
        seller_id=target_seller_id,
        **data
    )

    if error_message:
        await send_json_response(send, scope, 400, {"code": 400, "message": error_message})
        return

    await get_order_by_id(scope, receive, send, session, seller_id, order_id)