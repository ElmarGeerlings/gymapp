import json
import logging
import math
from collections import defaultdict
from secrets import token_urlsafe

from jad import settings

from server.encryption import decrypt_order_dict, encrypt
from server.filters import contains_object, build_filter_clause
from server.pools import get_pg, get_redis

logger = logging.getLogger(__name__)

from datetime import datetime, timedelta

from django_rq import get_queue

from server.siu_webhooks import create_siu_process_status
from server.fulfilment import full_auto_print_helper, order_ship_functions, parcel_ship_functions
from server.misc import async_debounce
from server.profit import picking_data_simplified, purchase_price_with_suppliers, set_order_profit
from siu_base.http import alog_event

# try because of signalclient
try:
    from jad.settings import JAD_ID
except:
    pass


async def get_orders(
    filters=None,
    limit=50,
    offset=0,
    sorting="order_date",
    sorting_direction="DESC",
    include_profit=False,
    external=False,
):
    """
    Get orders with flexible filtering.

    Args:
        filters: Dict with filter conditions. Keys should be column names with optional operators.
            Examples: {"os.seller_id": 123, "o.status": "OPEN", "o.updated_at__gt": datetime(...)}
        limit: Maximum number of orders to return
        offset: Number of orders to skip
        sorting: Field to sort by
        sorting_direction: ASC or DESC
        include_profit: Whether to include profit data
        external: If True, return limited fields for external users
    Returns:
        Tuple of (orders list, total count)
    """
    if filters is None:
        filters = {}

    async with get_pg().acquire() as conn:
        # Build WHERE clause using the utility function
        where_clause, params, param_idx = build_filter_clause(filters)

        # If we have a WHERE clause, prepend WHERE
        if where_clause:
            where_clause = f"WHERE {where_clause}"
        else:
            where_clause = ""

        # Get total count first - same for both external and internal
        count_query = f"""
            SELECT COUNT(*)
            FROM uni_order o
            JOIN order_seller os ON o.id = os.order_id
            {where_clause}
        """
        total_count = await conn.fetchval(count_query, *params)

        # sanitize ORDER BY inputs
        allowed_sort_columns = {
            "id",
            "order_date",
            "created_at",
            "updated_at",
            "status",
            "store_id",
            "visible_store_id",
            "sales_channel_id",
            "price",
        }
        if sorting not in allowed_sort_columns:
            sorting = "order_date"
        sorting_direction = (sorting or "order_date") and (sorting_direction or "DESC").upper()
        if sorting_direction not in {"ASC", "DESC"}:
            sorting_direction = "DESC"

        if external:
            order_query = f"""
                SELECT o.id, o.created_at, o.updated_at, o.order_date,
                    o.sales_channel_id, o.status, o.store_id, o.visible_store_id, o.is_pickup,
                    o.pickup_id, o.pickup_name, o.pickup_street, o.pickup_housenumber,
                    o.pickup_housenumber_extended, o.pickup_postcode, o.pickup_city, o.pickup_country,
                    o.customer_firstname, o.customer_lastname, o.customer_company, o.customer_street,
                    o.customer_housenumber, o.customer_housenumber_extended, o.customer_postcode, o.customer_city,
                    o.customer_country, o.customer_email, o.customer_phone, o.customer_delivery_instructions,
                    o.billing_firstname, o.billing_lastname, o.billing_company, o.billing_kvk, o.billing_vat,
                    o.billing_street, o.billing_housenumber, o.billing_housenumber_extended, o.billing_postcode,
                    o.billing_city, o.billing_country, o.billing_email, o.billing_phone,
                    o.price, o.raw, o.package_type_programming,
                    sc.name as sales_channel_name, sc.meta_data_id as sales_channel_meta_data_id,
                    scm.logo_path as sales_channel_logo_path
                FROM uni_order o
                LEFT JOIN order_seller os ON o.id = os.order_id
                LEFT JOIN uni_saleschannel sc ON o.sales_channel_id = sc.id
                LEFT JOIN uni_saleschannelmetadata scm ON sc.meta_data_id = scm.id
                {where_clause}
                ORDER BY o.{sorting} {sorting_direction}
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """
            orders = await conn.fetch(order_query, *params, limit, offset)

            # Convert orders to list of dicts
            orders = [decrypt_order_dict(dict(order)) for order in orders]

            order_ids = [order["id"] for order in orders]

            # Fetch parcels for external users
            parcels = await conn.fetch(
                """
                SELECT p.carrier,
                       p.carrier_track,
                       p.carrier_url,
                       po.order_id
                FROM uni_parcel p
                JOIN uni_parcel_orders po ON p.id = po.parcel_id
                WHERE po.order_id = ANY($1::int[])
                AND p.is_valid IS TRUE
                ORDER BY p.created_at DESC
            """,
                order_ids,
            )

            parcels_dict = {}
            for parcel in parcels:
                order_id = parcel["order_id"]
                if order_id not in parcels_dict:
                    parcels_dict[order_id] = []
                parcels_dict[order_id].append(dict(parcel))

            for order in orders:
                order["parcels"] = parcels_dict.get(order["id"], [])
        else:
            order_query = f"""
                SELECT o.id, o.created_at, o.updated_at, o.order_date,
                    o.sales_channel_id, o.status, o.store_id, o.visible_store_id, o.is_pickup,
                    o.pickup_id, o.pickup_name, o.pickup_street, o.pickup_housenumber,
                    o.pickup_housenumber_extended, o.pickup_postcode, o.pickup_city, o.pickup_country,
                    o.customer_firstname, o.customer_lastname, o.customer_company, o.customer_street,
                    o.customer_housenumber, o.customer_housenumber_extended, o.customer_postcode, o.customer_city,
                    o.customer_country, o.customer_email, o.customer_phone, o.customer_delivery_instructions,
                    o.billing_firstname, o.billing_lastname, o.billing_company, o.billing_kvk, o.billing_vat,
                    o.billing_street, o.billing_housenumber, o.billing_housenumber_extended, o.billing_postcode,
                    o.billing_city, o.billing_country, o.billing_email, o.billing_phone,
                    o.price, o.raw, o.package_type_programming,
                    sc.name as sales_channel_name, sc.meta_data_id as sales_channel_meta_data_id,
                    scm.logo_path as sales_channel_logo_path
                FROM uni_order o
                LEFT JOIN order_seller os ON o.id = os.order_id
                LEFT JOIN uni_saleschannel sc ON o.sales_channel_id = sc.id
                LEFT JOIN uni_saleschannelmetadata scm ON sc.meta_data_id = scm.id
                {where_clause}
                ORDER BY o.{sorting} {sorting_direction}
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """
            orders = await conn.fetch(order_query, *params, limit, offset)

            # Convert orders to list of dicts
            orders = [decrypt_order_dict(dict(order)) for order in orders]

            order_ids = [order["id"] for order in orders]

            # Fetch and process order_items, supplies, etc. for internal users
            order_items = await conn.fetch(
                """
                SELECT oi.order_id,
                        oi.id,
                        iuv.image_url as product_image_url,
                        p.id as product_id,
                        p.title as product_title,
                        p.ean as product_ean,
                        p.sku as product_sku,
                        p.is_set as product_is_set,
                        p.packaging as product_packaging,
                        oi.status,
                        oi.quantity_ordered,
                        oi.editable,
                        oi.vvb,
                        oi.store_costs,
                        oi.unit_store_costs,
                        oi.store_costs_converted,
                        oi.unit_store_costs_converted,
                        oi.total_price,
                        oi.total_price_converted,
                        oi.unit_price,
                        oi.unit_price_converted,
                        o.image_url as offer_image_url,
                        o.id as offer_id,
                        o.ean as offer_ean,
                        o.seller_sku as offer_seller_sku,
                        o.title as offer_title
                FROM uni_orderitem oi
                LEFT JOIN uni_product p ON oi.product_id = p.id
                LEFT JOIN product_with_image_url iuv ON p.id = iuv.product_id
                LEFT JOIN uni_offer o ON oi.offer_id = o.id
                WHERE oi.order_id = ANY($1::int[])
            """,
                order_ids,
            )

            order_items = [dict(item) for item in order_items]
            order_item_ids = [item["id"] for item in order_items]

            # Get supplies for order items
            supplies = await conn.fetch(
                """
                SELECT s.order_item_id,
                        l.id as location_id,
                        l.sublocations,
                        w.name as warehouse_name,
                        p.id as product_id,
                        p.sku as product_sku,
                        p.title as product_title,
                        p.ean as product_ean,
                        iuv.image_url as product_image_url,
                        SUM(s.amount) as total_amount
                FROM uni_supply s
                JOIN uni_location l ON s.location_id = l.id
                JOIN ware_warehouse w ON l.warehouse_id = w.id
                LEFT JOIN uni_product p ON s.product_id = p.id
                LEFT JOIN product_with_image_url iuv ON p.id = iuv.product_id
                WHERE s.order_item_id = ANY($1::int[])
                AND s.deleted_at IS NULL
                GROUP BY s.order_item_id, l.id, l.sublocations, w.name, p.id, p.sku, p.title, p.ean, iuv.image_url
            """,
                order_item_ids,
            )

            supplies = [dict(supply) for supply in supplies]

            if include_profit:
                profit_details = await conn.fetch(
                    """
                    SELECT order_item_id,
                            product_id,
                            quantity_sold,
                            purchase_costs,
                            selling_price,
                            shipping_costs,
                            vat_costs,
                            store_costs,
                            fulfillment_costs,
                            profit,
                            unit_purchase_costs,
                            unit_selling_price,
                            unit_shipping_costs,
                            unit_vat_costs,
                            unit_store_costs,
                            unit_fulfillment_costs,
                            unit_profit
                    FROM uni_productsale
                    WHERE order_item_id = ANY($1::int[])
                """,
                    order_item_ids,
                )

                profit_details = [dict(detail) for detail in profit_details]

                profit_details_dict = {}
                for detail in profit_details:
                    if detail["order_item_id"] not in profit_details_dict:
                        profit_details_dict[detail["order_item_id"]] = []
                    profit_details_dict[detail["order_item_id"]].append(detail)

            supplies_dict = {}
            for supply in supplies:
                if supply["order_item_id"] not in supplies_dict:
                    supplies_dict[supply["order_item_id"]] = {}
                if supply["product_id"] not in supplies_dict[supply["order_item_id"]]:
                    supplies_dict[supply["order_item_id"]][supply["product_id"]] = []
                supplies_dict[supply["order_item_id"]][supply["product_id"]].append(supply)

            for item in order_items:
                item["product_supplies"] = []
                for product_id, supplies in supplies_dict.get(item["id"], {}).items():
                    item["product_supplies"].append(
                        {
                            "product_id": product_id,
                            "product_title": supplies[0]["product_title"],
                            "product_image_url": supplies[0]["product_image_url"],
                            "product_ean": supplies[0]["product_ean"],
                            "product_sku": supplies[0]["product_sku"],
                            "supplies": [
                                {
                                    "warehouse_name": supply["warehouse_name"],
                                    "total_amount": supply["total_amount"],
                                    "sublocations": supply["sublocations"],
                                }
                                for supply in supplies
                            ],
                        }
                    )
                if include_profit:
                    item["profit_details"] = profit_details_dict.get(item["id"], [])

            order_items_dict = {}
            for item in order_items:
                if item["order_id"] not in order_items_dict:
                    order_items_dict[item["order_id"]] = []
                order_items_dict[item["order_id"]].append(item)

            for order in orders:
                order["order_items"] = order_items_dict.get(order["id"], [])

        return orders, total_count


async def get_single_order(order_id, seller_id=None, external=False):

    async with get_pg().acquire() as conn:
        # External users get limited fields
        if external:
            orders = await conn.fetch(
                """
                SELECT o.id,
                       o.created_at,
                       o.updated_at,
                       o.status,
                       o.order_date,
                       o.store_id,
                       o.visible_store_id
                FROM uni_order o
                JOIN order_seller os ON o.id = os.order_id
                WHERE o.id = $1
                AND ($2::int IS NULL OR os.seller_id = $2)
            """,
                order_id,
                seller_id,
            )

            if not orders:
                return None

            order = dict(orders[0])

            # Get carrier info for external users
            parcels = await conn.fetch(
                """
                SELECT p.carrier,
                       p.carrier_track,
                       p.carrier_url
                FROM uni_parcel p
                JOIN uni_parcel_orders po ON p.id = po.parcel_id
                WHERE po.order_id = $1
                AND p.is_valid IS TRUE
                ORDER BY p.created_at DESC
            """,
                order_id,
            )

            order["parcels"] = [dict(parcel) for parcel in parcels]
            return order

        # Internal users get full data
        orders = await conn.fetch(
            """
            SELECT o.id,
                   o.status,
                   o.order_date,
                   o.store_id,
                   o.visible_store_id,
                   o.package_type_programming,
                   o.pickup_id,
                   o.pickup_name,
                   o.pickup_street,
                   o.pickup_housenumber,
                   o.pickup_housenumber_extended,
                   o.pickup_postcode,
                   o.pickup_city,
                   o.pickup_country,
                   o.customer_firstname,
                   o.customer_lastname,
                   o.customer_company,
                   o.customer_street,
                   o.customer_housenumber,
                   o.customer_housenumber_extended,
                   o.customer_postcode,
                   o.customer_city,
                   o.customer_country,
                   o.customer_email,
                   o.customer_phone,
                   o.billing_firstname,
                   o.billing_lastname,
                   o.billing_company,
                   o.billing_street,
                   o.billing_housenumber,
                   o.billing_housenumber_extended,
                   o.billing_postcode,
                   o.billing_city,
                   o.billing_country,
                   o.billing_email,
                   o.billing_phone,
                   o.billing_kvk,
                   o.billing_vat,
                   sc.name as sales_channel_name,
                   scm.logo_path as sales_channel_logo_path
            FROM uni_order o
            JOIN order_seller os ON o.id = os.order_id
            LEFT JOIN uni_saleschannel sc ON o.sales_channel_id = sc.id
            LEFT JOIN uni_saleschannelmetadata scm ON sc.meta_data_id = scm.id
            WHERE o.id = $1
            AND ($2::int IS NULL OR os.seller_id = $2)
        """,
            order_id,
            seller_id,
        )

        if not orders:
            return None

        # Convert orders to list of dicts
        order = decrypt_order_dict(dict(orders[0]))

        order_items = await conn.fetch(
            """
            SELECT oi.order_id,
                    oi.id,
                    iuv.image_url as product_image_url,
                    p.id as product_id,
                    p.title as product_title,
                    p.ean as product_ean,
                    p.sku as product_sku,
                    p.is_set as product_is_set,
                    oi.status,
                    oi.quantity_ordered,
                    oi.unit_price,
                    oi.editable,
                    oi.vvb,
                    o.image_url as offer_image_url,
                    o.id as offer_id,
                    o.ean as offer_ean,
                    o.seller_sku as offer_seller_sku,
                    o.title as offer_title
            FROM uni_orderitem oi
            LEFT JOIN uni_product p ON oi.product_id = p.id
            LEFT JOIN product_with_image_url iuv ON p.id = iuv.product_id
            LEFT JOIN uni_offer o ON oi.offer_id = o.id
            WHERE oi.order_id = $1
        """,
            order_id,
        )

        # Get parcels for the order
        parcels = await conn.fetch(
            """
            SELECT p.id,
                   p.created_at,
                   p.carrier,
                   p.label_id,
                   p.package_type,
                   p.carrier_track,
                   p.carrier_url,
                   p.transporter_text,
                   p.printed_at,
                   p.is_valid,
                   p.options
            FROM uni_parcel p
            JOIN uni_parcel_orders po ON p.id = po.parcel_id
            WHERE po.order_id = $1
            AND p.is_valid IS TRUE
            ORDER BY p.created_at DESC
        """,
            order_id,
        )

        order_items = [dict(item) for item in order_items]
        order_item_ids = [item["id"] for item in order_items]
        parcels = [dict(parcel) for parcel in parcels]

        order["parcels"] = parcels
        order["order_items"] = order_items

        # Get supplies for order items
        supplies = await conn.fetch(
            """
            SELECT s.order_item_id,
                   l.id as location_id,
                   l.sublocations,
                   w.name as warehouse_name,
                   p.id as product_id,
                   p.sku as product_sku,
                   p.title as product_title,
                   p.ean as product_ean,
                   iuv.image_url as product_image_url,
                   SUM(s.amount) as total_amount
            FROM uni_supply s
            JOIN uni_location l ON s.location_id = l.id
            JOIN ware_warehouse w ON l.warehouse_id = w.id
            LEFT JOIN uni_product p ON s.product_id = p.id
            LEFT JOIN product_with_image_url iuv ON p.id = iuv.product_id
            WHERE s.order_item_id = ANY($1::int[])
            AND s.deleted_at IS NULL
            GROUP BY s.order_item_id, l.id, l.sublocations, w.name, p.id, p.sku, p.title, p.ean, iuv.image_url
        """,
            order_item_ids,
        )

        supplies = [dict(supply) for supply in supplies]

        supplies_dict = {}
        for supply in supplies:
            if supply["order_item_id"] not in supplies_dict:
                supplies_dict[supply["order_item_id"]] = {}
            if supply["product_id"] not in supplies_dict[supply["order_item_id"]]:
                supplies_dict[supply["order_item_id"]][supply["product_id"]] = []
            supplies_dict[supply["order_item_id"]][supply["product_id"]].append(supply)

        for item in order_items:
            item["product_supplies"] = []
            for product_id, supplies in supplies_dict.get(item["id"], {}).items():
                item["product_supplies"].append(
                    {
                        "product_id": product_id,
                        "product_title": supplies[0]["product_title"],
                        "product_image_url": supplies[0]["product_image_url"],
                        "product_ean": supplies[0]["product_ean"],
                        "product_sku": supplies[0]["product_sku"],
                        "supplies": [
                            {
                                "warehouse_name": supply["warehouse_name"],
                                "total_amount": supply["total_amount"],
                                "sublocations": supply["sublocations"],
                            }
                            for supply in supplies
                        ],
                    }
                )

        error_tags = await conn.fetch(
            """
            SELECT t.id, t.name
            FROM uni_tag t
            JOIN uni_order_tags ot ON t.id = ot.tag_id
            WHERE ot.order_id = $1 AND t.type = 'error'
        """,
            order["id"],
        )

        transporter_error_messages

        order["error_tags"] = [
            transporter_error_messages.get(
                tag["name"], "Er is een onbekende fout opgetreden. Probeer het later opnieuw of neem contact met ons op voor verdere hulp. Vaak gaat er iets mis in het adres van de klant, controleer het adres voordat je contact met ons opneemt."
            )
            for tag in error_tags
        ]

    return order


async def search_order_by_store_id(store_id, user_id=None):
    async with get_pg().acquire() as conn:
        return await conn.fetchval(
            """
            SELECT o.id
            FROM uni_order o
            JOIN order_seller os ON o.id = os.order_id
            JOIN accounts_user_sellers aus ON os.seller_id = aus.seller_id
            WHERE o.store_id = $1 or o.visible_store_id = $1
            AND aus.user_id = $2
            LIMIT 1
        """,
            store_id,
            user_id,
        )


async def create_new_order(user_id, channel='manual', seller_id=None, **data):
    async with get_pg().acquire() as conn:
        async with conn.transaction():
            # Auto-assign seller if None
            if seller_id is None:
                seller = await conn.fetchrow(
                    """
                    SELECT seller_id
                    FROM accounts_user_sellers
                    WHERE user_id = $1
                    LIMIT 1
                """,
                    user_id,
                )
                if not seller:
                    return None, "No seller found for user"
                seller_id = seller["seller_id"]

            # Create the order with a temporary store_id
            if data.get("store_id"):
                temp_store_id = data.get("store_id")
            else:
                temp_store_id = f"SIU-{token_urlsafe(10)}-temp"

            # Insert the order
            if data.get("status"):
                status = data.get("status")
            else:
                if await get_redis().get("siu:system:new_orders_as_open"):
                    status = "OPEN"
                else:
                    status = "DRAFT"
            order = await conn.fetchrow(
                """
                INSERT INTO uni_order
                (sales_channel_id, order_date, store_id, status, seller_id,
                 created_at, updated_at, channel, label_id)
                VALUES (0, NOW(), $1, $4, $2,
                        NOW(), NOW(), $3, '')
                RETURNING id
            """,
                temp_store_id,
                seller_id,
                channel,
                status,
            )

            order_id = order["id"]
            total_order_price = 0

            # Create order items if provided (for API orders)
            order_item_ids = []
            if order_items := data.get("order_items"):
                for item_data in order_items:
                    product_ean = item_data.get("product_ean")
                    quantity = item_data.get("quantity")
                    unit_price = item_data.get("unit_price")

                    if not product_ean:
                        return None, "Missing product_ean in order items"
                    if not isinstance(quantity, int):
                        return None, "Invalid quantity. Must be an integer"
                    if not isinstance(unit_price, (int, float)):
                        return None, "Invalid unit_price. Must be a number"

                    product = await conn.fetchrow(
                        "SELECT p.id, p.sku FROM uni_product p JOIN uni_offer o ON p.id = o.product_id JOIN uni_saleschannel sc ON o.sales_channel_id = sc.id WHERE p.ean = $1 AND sc.seller_id = $2",
                        product_ean, seller_id
                    )
                    if not product:
                        return None, f"Product with EAN {product_ean} not found for this client"

                    total_price = quantity * unit_price
                    total_order_price += total_price

                    order_item_id = await conn.fetchval(
                        """
                        INSERT INTO uni_orderitem
                        (order_id, product_id, sku, store_id, quantity_ordered, unit_price, total_price, status)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, 'OPEN')
                        RETURNING id
                        """,
                        order_id, product['id'], product['sku'], product['sku'], quantity, unit_price, total_price
                    )
                    order_item_ids.append(order_item_id)
            # Update store_id and conditionally update price
            if order_items:
                # Update both store_id and price when order_items are provided
                await conn.execute(
                    """
                    UPDATE uni_order
                    SET store_id = $1, price = $2
                    WHERE id = $3
                """,
                    f"SIU-{order_id}",
                    total_order_price,
                    order_id,
                )
            else:
                # Only update store_id when no order_items provided (manual orders)
                await conn.execute(
                    """
                    UPDATE uni_order
                    SET store_id = $1
                    WHERE id = $2
                """,
                    f"SIU-{order_id}",
                    order_id,
                )

            to_update_data = {}
            for key, value in data.items():
                if key in ["order_date", "visible_store_id", "is_appointment", "is_pickup_at_seller", "is_pickup", "pickup_id", "pickup_name", "pickup_street", "pickup_housenumber", "pickup_housenumber_extended", "pickup_postcode", "pickup_city", "pickup_country", "shipping_paid", "price", "discount", "chosen_carrier", "customer_firstname", "customer_lastname", "customer_street", "customer_housenumber", "customer_housenumber_extended", "customer_postcode", "customer_city", "customer_country", "customer_email", "customer_phone", "billing_firstname", "billing_lastname", "billing_street", "billing_housenumber", "billing_housenumber_extended", "billing_postcode", "billing_city", "billing_country", "billing_email", "billing_phone", "billing_kvk", "billing_vat", "is_company"]:
                    if key in ["pickup_name", "pickup_street", "pickup_housenumber", "pickup_housenumber_extended", "pickup_postcode", "pickup_city", "customer_firstname", "customer_lastname", "customer_street", "customer_housenumber", "customer_housenumber_extended", "customer_city", "customer_email", "customer_phone", "billing_firstname", "billing_lastname", "billing_street", "billing_housenumber", "billing_housenumber_extended", "billing_city", "billing_email", "billing_phone", "billing_kvk", "billing_vat"]:
                        value = encrypt(value)
                    to_update_data[key] = value
            if to_update_data:
                await conn.execute(f"""
                    UPDATE uni_order
                    SET {', '.join([f"{key} = ${i}" for i, key in enumerate(to_update_data.keys(), start=1)])}
                    WHERE id = ${len(to_update_data) + 1}
                """, *to_update_data.values(), order_id)
        # Log event
        description = "Via API aangemaakt" if channel == 'api' else "Handmatig aangemaakt"
        await alog_event(
            "Order Misc Log", description=description, instances=[("uni_order", order_id), ("accounts_user", user_id)]
        )

        for order_item in order_item_ids:
            if status in ["OPEN", "DRAFT"]:
                await decrement_product_stock_by_order_item(order_item, None, f"API order item {order_item}")

        return order_id, None


async def create_parcel_and_notify_channels(conn, order_id, order_record, transporter_code, track_and_trace, tracking_url):
    """
    Creates parcel record, links to order, updates order status, and queues channel notifications.
    This shared logic is used by both API tracking and fulfillment shipping.
    """
    # Create parcel
    parcel_id = await conn.fetchval("""
        INSERT INTO uni_parcel (carrier, carrier_track, carrier_url)
        VALUES ($1, $2, $3)
        RETURNING id
    """, transporter_code, track_and_trace, tracking_url)

    # Link parcel to order
    await conn.execute("""
        INSERT INTO uni_parcel_orders (parcel_id, order_id)
        VALUES ($1, $2)
    """, parcel_id, order_id)

    # Update order status and tracking info
    await conn.execute("""
        UPDATE uni_order
        SET carrier = $1, carrier_track = $2, carrier_url = $3, status = 'API_SHIPPING'
        WHERE id = $4
    """, transporter_code, track_and_trace, tracking_url, order_id)

    # Queue channel-specific tasks
    channel_name = order_record['channel_name']
    q = get_queue()
    if channel_name in order_ship_functions:
        q.enqueue(order_ship_functions[channel_name], order_id)
    elif channel_name in parcel_ship_functions:
        q.enqueue(parcel_ship_functions[channel_name], parcel_id)

    return parcel_id


async def add_tracking_to_order(order_id, transporter_code, track_and_trace, tracking_url, user_id=None, seller_id=None):
    async with get_pg().acquire() as conn:
        # Get order and verify seller ownership
        order_record = await conn.fetchrow(
            """SELECT o.id, o.status, o.sales_channel_id, sc.meta_data_id AS sales_channel_meta_id, sm.channel_name, sc.seller_id
               FROM uni_order o
               JOIN uni_saleschannel sc ON o.sales_channel_id = sc.id
               JOIN uni_saleschannelmetadata sm ON sc.meta_data_id = sm.id
               WHERE o.id = $1""",
            order_id
        )

        if not order_record:
            return None, f"Order {order_id} not found"

        # Auto-assign seller if None and verify access
        if seller_id is None:
            if user_id is None:
                return None, "Either user_id or seller_id must be provided"

            user_seller = await conn.fetchrow(
                """
                SELECT seller_id
                FROM accounts_user_sellers
                WHERE user_id = $1
                LIMIT 1
            """,
                user_id,
            )
            if not user_seller:
                return None, "No seller found for user"
            seller_id = user_seller["seller_id"]

        # Verify seller has access to this order
        if order_record['seller_id'] != seller_id:
            return None, f"Order {order_id} not found for seller {seller_id}"

        # Check if order can be shipped
        if order_record['status'] in ['API_SHIPPING', 'COMPLETE']:
            return None, f"Order cannot be shipped from its current status: {order_record['status']}"

        # Get webhook URLs for process status updates
        webhook_urls = []
        if user_id:
            webhook_urls_records = await conn.fetch(
                """
                SELECT aw.webhook_url
                FROM api_webhook_user AS awu
                JOIN api_webhook AS aw ON awu.api_webhook_id = aw.id
                WHERE awu.user_id = $1 AND 'PROCESS_STATUS_UPDATE' = ANY(aw.webhook_type)
                """,
                user_id,
            )
            webhook_urls = [r["webhook_url"] for r in webhook_urls_records]

        # Create process status
        process_id = await create_siu_process_status(
            seller_id, 'shipOrder', order_record['sales_channel_meta_id'], order_id, webhook_urls
        )

        # Use shared parcel creation and notification logic
        parcel_id = await create_parcel_and_notify_channels(
            conn, order_id, order_record, transporter_code, track_and_trace, tracking_url
        )

        return process_id, None


async def delete_order(order_id):
    async with get_pg().acquire() as conn:
        # First unpick and delete all order items
        order_items = await conn.fetch(
        """
        SELECT id
        FROM uni_orderitem
        WHERE order_id = $1
        """,
            order_id,
        )

        for order_item in order_items:
            await unpick_item(order_item["id"])

            await conn.execute(
                """
                DELETE FROM uni_orderitem_events
                WHERE orderitem_id = $1
            """,
                order_item["id"],
            )

            await conn.execute(
                """
                DELETE FROM uni_productsale
                WHERE order_item_id = $1
            """,
                order_item["id"],
            )

            await conn.execute(
                """
                DELETE FROM uni_orderitem
                WHERE id = $1
            """,
                order_item["id"],
            )
        # Delete order events
        await conn.execute(
            """
            DELETE FROM uni_order_parcel_events_new
            WHERE order_id = $1
        """,
            order_id,
        )

        # Then delete the order itself
        await conn.execute(
            """
            DELETE FROM uni_order WHERE id = $1
        """,
            order_id,
        )


async def edit_order_field(order_id, field, value):
    async with get_pg().acquire() as conn:
        if field in {
            'pickup_name',
            'pickup_street',
            'pickup_housenumber',
            'pickup_housenumber_extended',
            'pickup_city',
            'customer_firstname',
            'customer_lastname',
            'customer_company',
            'customer_street',
            'customer_housenumber',
            'customer_housenumber_extended',
            'customer_city',
            'customer_email',
            'customer_phone',
            'customer_delivery_instructions',
            'billing_firstname',
            'billing_lastname',
            'billing_company',
            'billing_kvk',
            'billing_vat',
            'billing_street',
            'billing_housenumber',
            'billing_housenumber_extended',
            'billing_city',
            'billing_email',
            'billing_phone',
            'raw'
            }:
            value = encrypt(value)

        await conn.execute(
            f"""
            UPDATE uni_order
            SET {field} = $1
            WHERE id = $2
        """,
            value,
            order_id,
        )

    if field in ["customer_country", "billing_country"]:
        await recompute_order_metadata(order_id)


async def add_product_to_order(order_id, product_id, quantity, user_id=None, run_recompute=True):
    async with get_pg().acquire() as conn:
        # Check if order item already exists
        order_id = int(order_id)
        product_id = int(product_id)
        quantity = int(quantity)

        existing_order_item = await conn.fetchrow(
            """
            SELECT id, quantity_ordered
            FROM uni_orderitem
            WHERE order_id = $1
            AND product_id = $2
            AND editable = true
        """,
            order_id,
            product_id,
        )

        if existing_order_item:
            orderitem_id = existing_order_item["id"]
            await unpick_item(existing_order_item["id"], cause="")
            # Update quantity of existing order item
            await conn.execute(
                """
                UPDATE uni_orderitem
                SET quantity_ordered = quantity_ordered + $1
                WHERE id = $2
            """,
                quantity,
                existing_order_item["id"],
            )

        else:

            # Insert the order item and get its id
            orderitem_id = await conn.fetchval(
                """
                INSERT INTO uni_orderitem (
                    order_id,
                    store_id,
                    product_id,
                    quantity_ordered,
                    unit_price,
                    total_price,
                    sku,
                    status,
                    editable,
                    managed_by_channel
                )
                VALUES (
                    $1,                    -- order_id
                    $2,                    -- store_id
                    $3,                    -- product_id
                    $4,                    -- quantity_ordered
                    $5,                    -- unit_price
                    $6,                    -- total_price
                    $7,                    -- sku
                    $8,                    -- status
                    $9,                    -- editable
                    $10                    -- managed_by_channel
                )
                RETURNING id
            """,
                order_id,
                f"SIU-{token_urlsafe(10)}-temp",
                product_id,
                quantity,
                0,  # unit_price
                0,  # total_price
                await conn.fetchval("SELECT sku FROM uni_product WHERE id = $1", product_id),
                "HANDMATIG",
                True,
                False,
            )

            # Update store_id with the order item id
            await conn.execute(
                """
                UPDATE uni_orderitem
                SET store_id = $1
                WHERE id = $1
            """,
                orderitem_id,
            )

        await decrement_product_stock_by_order_item(orderitem_id)

        if run_recompute:
            await recompute_order_metadata(order_id)

        product_sku = await conn.fetchval(
            """
            SELECT sku
            FROM uni_product
            WHERE id = $1
        """,
            product_id,
        )

        # This should be rewritten to not have the sku in the description, but be rendered from the instances
        instances = [("uni_order", order_id), ("uni_product", product_id)]
        if user_id:
            instances.append(("accounts_user", user_id))

        await alog_event("Order edit", f"Product {product_sku} toegevoegd met aantal {quantity}", instances=instances)


async def edit_item_amount(order_item_id, new_quantity, user_id=None):
    async with get_pg().acquire() as conn:
        # Get product sku, id and order_id from orderitem
        product_info = await conn.fetchrow(
            """
            SELECT p.sku, p.id as product_id, oi.order_id
            FROM uni_orderitem oi
            JOIN uni_product p ON p.id = oi.product_id
            WHERE oi.id = $1
        """,
            order_item_id,
        )

        product_sku = product_info["sku"]
        product_id = product_info["product_id"]
        order_id = product_info["order_id"]

        # This should be rewritten to not have the sku in the description, but be rendered from the instances
        instances = [("uni_product", product_id)]
        if user_id:
            instances.append(("accounts_user", user_id))

        await unpick_item(order_item_id)
        # Update quantity of existing order item

        if new_quantity == 0:

            await conn.execute(
                """
                DELETE FROM uni_orderitem_events
                WHERE orderitem_id = $1
            """,
                order_item_id,
            )

            await conn.execute(
                """
                DELETE FROM uni_productsale
                WHERE order_item_id = $1
            """,
                order_item_id,
            )

            await conn.execute(
                """
                DELETE FROM uni_orderitem
                WHERE id = $1
            """,
                order_item_id,
            )

            await alog_event("Order edit", f"Product {product_sku} verwijderd", instances=instances)

        else:

            instances.append(("uni_orderitem", order_item_id))

            await conn.execute(
                """
                UPDATE uni_orderitem
                SET quantity_ordered = $1
                WHERE id = $2
            """,
                new_quantity,
                order_item_id,
            )

            await decrement_product_stock_by_order_item(order_item_id, new_quantity)

            await alog_event(
                "Order edit", f"Product {product_sku} aantal aangepast naar {new_quantity}", instances=instances
            )

        await recompute_order_metadata(order_id)


async def decrement_product_stock_by_order_item(order_item_id, pick_quantity=None, cause="", locations=None):
    # Get order item details
    async with get_pg().acquire() as conn:
        order_item = await conn.fetchrow(
            """
            SELECT
                oi.id,
                oi.order_id,
                oi.product_id,
                oi.quantity_ordered,
                oi.status,
                o.order_date,
                o.store_id,
                sc.name as sales_channel_name,
                sc.id as sales_channel_id,
                p.id as product_id,
                p.title as product_title,
                p.created_at as product_created_at
            FROM uni_orderitem oi
            JOIN uni_order o ON o.id = oi.order_id
            JOIN uni_saleschannel sc ON o.sales_channel_id = sc.id
            JOIN uni_product p ON p.id = oi.product_id
            WHERE oi.id = $1
        """,
            order_item_id,
        )

        # Get seller from order_seller table
        seller_id = await conn.fetchval(
            """
            SELECT seller_id
            FROM order_seller
            WHERE order_id = $1
        """,
            order_item["order_id"],
        )

        if not seller_id:
            # Final fallback to first seller
            seller_id = await conn.fetchval("SELECT id FROM uni_seller LIMIT 1")

        if JAD_ID == 15:
            if order_item["product_id"] and await conn.fetchval(
                """
                SELECT packaging
                FROM uni_product
                WHERE id = $1
                """,
                order_item["product_id"],
            ):
                seller_id = 1

        if not pick_quantity:
            pick_quantity = order_item["quantity_ordered"]

        if order_item["status"] != "OPEN" and order_item["status"] != "HANDMATIG":
            await alog_event(f"order_item is not open", instances=[("uni_orderitem", order_item["id"])])
            return

        if not order_item["product_id"]:
            await alog_event(f"order_item has no product", instances=[("uni_orderitem", order_item["id"])])
            return

        if order_item["product_created_at"] > order_item["order_date"]:
            # Get location id for warehouse ???
            location_id = await conn.fetchval(
                """
                SELECT l.id
                FROM uni_location l
                JOIN ware_warehouse w ON l.warehouse_id = w.id
                WHERE w.name = '???'
                LIMIT 1
            """
            )

            price, supplier_id = await purchase_price_with_suppliers(order_item["product_id"])
            await conn.executemany(
                """
                INSERT INTO uni_supply
                (order_item_id, location_id, seller_id, product_id, reserved_at, price)
                VALUES ($1, $2, $3, $4, NOW(), $5)
                """,
                [
                    (order_item["id"], location_id, seller_id, order_item["product_id"], price) for _ in range(order_item["quantity_ordered"])
                ],  # TODO (Job): This should use amount, but I do not want to change this now as I am already changing a lot of things
            )
        else:
            await decrement_product_stock(
                order_item["product_id"],
                seller_id,
                pick_quantity,
                cause=cause or f"{order_item['sales_channel_name']} pick item {order_item['product_title'][:30]} ({order_item['id']}) for order {order_item['store_id']}",
                order_item=order_item,
                locations=locations,
            )


async def decrement_product_stock(
    product_id, seller_id, quantity, cause="", order_item=None, locations=None
):  # This is what decrement_product_stock_recursive_set was, that should always be used

    if settings.JAD_ID == 1853:
        sales_channel_id = order_item.get("sales_channel_id") if order_item else None
        if sales_channel_id != 0:
            EXCLUDED_EANS = {
                "8720892482402",
                "8720892482419",
                "8720892482495",
                "8721008212043",
                "8721008212050",
            }
            async with get_pg().acquire() as conn:
                product_ean = await conn.fetchval(
                    """
                    SELECT ean
                    FROM uni_product
                    WHERE id = $1
                    """,
                    product_id,
                )
            if product_ean in EXCLUDED_EANS:
                logger.info(
                    f"Stock decrement skipped for product {product_id} (EAN: {product_ean}) due to exclusion for JAD_ID 1853"
                )
                return

    async with get_pg().acquire() as conn:
        from server.inventory import alocal_stock_supply, aset_updated_stock_at, pick_item

        current_product_supply = await conn.fetchval(
            """
            SELECT COALESCE(SUM(s.amount), 0)
            FROM uni_supply s
            JOIN uni_location l ON s.location_id = l.id
            JOIN ware_warehouse w ON l.warehouse_id = w.id
            WHERE s.reserved_at IS NULL
            AND s.deleted_at IS NULL
            AND s.product_id = $1
            AND s.seller_id = $2
            AND w.pickable = true
        """,
            product_id,
            seller_id,
        )
        pick_amount = min(current_product_supply, quantity)
        quantity -= pick_amount
        if quantity > 0:
            # Get set products
            set_products = await conn.fetch(
                """
                SELECT sp.product_id, sp.quantity
                FROM uni_setproduct sp
                WHERE sp.parent_id = $1
                ORDER BY sp.product_id
            """,
                product_id,
            )

            if set_products:
                for set_product in set_products:
                    await decrement_product_stock(
                        set_product["product_id"],
                        seller_id,
                        quantity * set_product["quantity"],
                        cause=cause,
                        order_item=order_item,
                        locations=locations,
                    )
            else:
                location_id = await conn.fetchval(
                    """
                    SELECT l.id
                    FROM uni_location l
                    JOIN ware_warehouse w ON l.warehouse_id = w.id
                    WHERE w.name = '???'
                    LIMIT 1
                """
                )
                old_stock = await alocal_stock_supply(product_id)
                price, supplier_id = await purchase_price_with_suppliers(product_id)

                await conn.executemany(
                    """
                    INSERT INTO uni_supply
                    (order_item_id, location_id, product_id, seller_id, price, amount)
                    VALUES ($1, $2, $3, $4, $5, 1)
                    """,
                    [
                        (order_item["id"], location_id, product_id, seller_id, price) for _ in range(quantity)
                    ],  # TODO (Job): This should use amount, but I do not want to change this now as I am already changing a lot of things
                )

                await aset_updated_stock_at(product_id, old_stock)
                if await get_redis().get("system:auto-backorder") and order_item:
                    if not await conn.fetchval(
                        """
                        SELECT packaging
                        FROM uni_product
                        WHERE id = $1
                        """,
                        product_id,
                    ):
                        order_id = order_item["order_id"]
                        await aset_order_status(order_id, "BACKORDER")
        if pick_amount > 0:
            picked = 0
            while picked < pick_amount:
                picked += await pick_item(
                    product_id, seller_id, pick_amount - picked, cause=cause, order_item_id=order_item["id"], locations=locations
                )


async def aset_order_status(order_id, status, channel_sync=None, user=None, force=False):
    async with get_pg().acquire() as conn:
        from django_rq import get_queue
        from server.inventory import acache_stock_per_type

        # Get current order status, shipment_id, and sales channel info
        order_data = await conn.fetchrow(
            """
            SELECT o.status, o.shipment_id, sc.name as sales_channel_name, sc.id as sales_channel_id
            FROM uni_order o
            LEFT JOIN uni_saleschannel sc ON o.sales_channel_id = sc.id
            WHERE o.id = $1
        """,
            order_id,
        )
        current_status = order_data["status"]

        if current_status == "COMPLETE" and not force and channel_sync and settings.JAD_ID == 1943 and order_data["sales_channel_id"] == 1:
            return False

        default_q = get_queue("default")  # Should be async as well
        high_q = get_queue("high")
        low_q = get_queue("low")  # Should be async as well
        mails_q = get_queue("mails")  # Should be async as well

        allowed_transitions = {
            "CANCELED": ["ERROR", "OPEN", "WACHT OP BETALING", "AFHAALPUNT"],
            "LVB": ["CANCELED", "COMPLETE", "RETURNED", "ERROR"],
            "COMPLETE": [
                "BACKORDER",
                "OPEN",
                "RETURNED",
                "PICKUP",
                "APPOINTMENT",
                "ERROR",
                "WACHT OP BETALING",
                "AFHAALPUNT",
            ],
            "FBA": ["CANCELED", "COMPLETE", "RETURNED", "ERROR", "WACHT OP ADRES"],
            #'ALLEGRO': ['CANCELED', 'COMPLETE', 'RETURNED', 'ERROR', 'WACHT OP ADRES'], # TODO (Lars): Nog niet geimplementeerd, eerst controle op Marketplace/Eigen orders van Allegro.
            "BACKORDER": ["CANCELED", "COMPLETE", "ERROR", "WACHT OP ADRES"],
            "OPEN": [
                "CANCELED",
                "LVB",
                "ALLEGRO",
                "COMPLETE",
                "FBA",
                "BACKORDER",
                "RETURNED",
                "PICKUP",
                "APPOINTMENT",
                "ERROR",
                "WACHT OP ADRES",
                "WACHT OP BETALING",
                "AFHAALPUNT",
                "SENT TO PRINTER",
                "FRAUD",
                "ON-HOLD",
            ],
            "RETURNED": ["ERROR"],
            "PICKUP": ["CANCELED", "COMPLETE", "RETURNED", "ERROR"],  # Pickup at seller
            "APPOINTMENT": [
                "CANCELED",
                "COMPLETE",
                "RETURNED",
                "ERROR",
            ],  # Bezorgafspraak
            "ERROR": ["CANCELED", "COMPLETE", "RETURNED"],
            "BOL.COM LABEL ERROR": ["CANCELED", "COMPLETE", "RETURNED"],
            "SHIPPING ERROR": ["CANCELED", "COMPLETE", "RETURNED"],
            "WACHT OP BETALING": [
                "OPEN",
                "BACKORDER",
                "CANCELED",
                "COMPLETE",
                "RETURNED",
                "WACHT OP ADRES",
                "PICKUP",
                "AFHAALPUNT",
            ],
            "SHIPPING": [
                "ERROR",
                "COMPLETE",
                "CANCELED",
                "PICK ERROR",
            ],  # Maybe COMPLETE needs to go and we need to use force keyword in the finalize_order_item from bol
            "WACHT OP ADRES": [
                "OPEN",
                "COMPLETE",
                "CANCELED",
                "APPOINTMENT",
                "ERROR",
                "FBA",
                "BACKORDER",
            ],
            "AFHAALPUNT": [
                "OPEN",
                "COMPLETE",
                "CANCELED",
                "SHIPPING",
                "ERROR",
                "BACKORDER",
                "RETURNED",
            ],  # pickuppoint
            "SENT TO PRINTER": ["OPEN", "CANCELED", "COMPLETE", "RETURNED"],
            "FRAUD": ["OPEN", "CANCELED", "COMPLETE", "RETURNED"],
            "GML SHIPPING": ["CANCELED", "COMPLETE"],
            "QLS SHIPPING": ["CANCELED", "COMPLETE"],
            "HUBOO SHIPPING": ["CANCELED", "COMPLETE"],
            "MONTA SHIPPING": ["CANCELED", "COMPLETE"],
            "PICK ERROR": ["OPEN", "CANCELED", "COMPLETE", "RETURNED"],
            "OPZOEKEN": ["CANCELED", "COMPLETE", "RETURNED"],  # Custom for 394
            "ON-HOLD": ["OPEN", "CANCELED", "COMPLETE", "RETURNED"],
            "API_SHIPPING": ["COMPLETE", "CANCELED", "SHIPPING", "SHIPPING ERROR", "ERROR"]
        }

        # TODO(danilo): transitioning to OPEN or WACHT_OP_BETALING needs a stock check (so unpick everything and pick it again) BUT picking everything again won't work well until fulfilment items get a flag unpickable, so decrement_product_stock_by_order_item can check that, instead of the bol.tasks or amaz.tasks

        status = status.upper()


        if status == "CANCELLED":
            status = "CANCELED"


        if not force and status == "OPEN" and await get_redis().get("system:auto-backorder"):
            if not (await get_redis().get("system:enable-set-backorders-open") and user and current_status == "BACKORDER"):
                has_unknown = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM uni_supply s
                        JOIN uni_orderitem oi ON s.order_item_id = oi.id
                        JOIN uni_location l ON s.location_id = l.id
                        JOIN ware_warehouse w ON l.warehouse_id = w.id
                        WHERE oi.order_id = $1
                        AND s.deleted_at IS NULL
                        AND w.name = '???'
                    )
                    """,
                    order_id,
                )
                if has_unknown:
                    status = "BACKORDER"

        if channel_sync and not force:
            if status not in allowed_transitions.get(current_status, []):
                return False

        # Prevent order completion or status changes from COMPLETE if prevent_order_completion is enabled
        data = await conn.fetchrow(
            """
            SELECT sc.prevent_order_completion
            FROM uni_order o
            LEFT JOIN uni_saleschannel sc ON o.sales_channel_id = sc.id
            WHERE o.id = $1
            """,
            order_id,
        )
        if data:
            prevent_completion = data['prevent_order_completion']

        if (
            (current_status == "COMPLETE")
            and not force
            and (channel_sync and prevent_completion)
        ):
            return False

        fields_to_update = {}
        if current_status != status:
            if status == "BACKORDER":
                fields_to_update["backorder"] = True
            elif status == "OPEN":
                fields_to_update["backorder"] = False
                if current_status == "COMPLETE":
                    await conn.execute(
                        """
                        UPDATE uni_supply
                        SET deleted_at = NULL
                        WHERE order_item_id IN (
                            SELECT id
                            FROM uni_orderitem
                            WHERE order_id = $1
                        )
                    """,
                        order_id,
                    )
                elif current_status == "CANCELED" and channel_sync:
                    items = await conn.fetch(
                        """
                        SELECT id
                        FROM uni_orderitem
                        WHERE order_id = $1
                        AND status IN ('OPEN', 'HANDMATIG')
                    """,
                        order_id,
                    )
                    for item in items:
                        await decrement_product_stock_by_order_item(item["id"])

                if JAD_ID == 386:  # TODO(danilo): remove this whole call here after you confirm it works well via the ->OPEN set_order_status transition
                    default_q.enqueue_in(
                        timedelta(seconds=30),
                        "uni.tasks.distribute_order_check",
                        order_id,
                    )
            elif status == "COMPLETE" and current_status == "LVB":
                fields_to_update["fulfillment_costs_retrieved_at"] = datetime.now().astimezone()
            if channel_sync:
                await alog_event(
                    "Update Order Status",
                    description=f"{current_status} ➡️ {status}",
                    instances=[("uni_order", order_id), ("uni_saleschannel", channel_sync)],
                )
            elif user:
                await alog_event(
                    "Update Order Status",
                    description=f"{current_status} ➡️ {status}",
                    instances=[("uni_order", order_id), ("accounts_user", user)],
                )
            else:
                await alog_event(
                    "Update Order Status",
                    description=f"{current_status} ➡️ {status}",
                    instances=[("uni_order", order_id)],
                )
            recompute_stock_per_type = False
            if (current_status == "BACKORDER" or status == "BACKORDER") and JAD_ID == 279:
                recompute_stock_per_type = True

            fields_to_update["status"] = status
            recompute_order_profit = False
            if status == "COMPLETE":
                recompute_order_profit = True
                if (await get_redis().get("system:auto-ship") or await get_redis().get("system:auto-print-manual")) and order_data["shipment_id"]:
                    async_debounce(full_auto_print_helper, 3000)(order_data["shipment_id"])
                mails_q.enqueue_in(timedelta(seconds=5), "mailer.models.trigger_order_event", order_id, "order_shipped")
                items = await conn.fetch(
                    """
                    SELECT id
                    FROM uni_orderitem
                    WHERE order_id = $1
                """,
                    order_id,
                )
                for item in items:
                    await complete_order(item["id"])
                if await get_redis().get("ExactOnline:make_invoices"):
                    low_q.enqueue("exactonline.tasks.create_invoice_with_ratelimit", order_id)

                if JAD_ID == 334:
                    if order_data["sales_channel_name"] == "Propeller":
                        high_q.enqueue("server.custom.jad334.gridflow.send_order_to_dls", order_id)
                    high_q.enqueue("server.custom.jad334.gridflow.send_order_to_gridflow", order_id)
                    high_q.enqueue("server.custom.jad334.dutch_label_engine.send_order_to_dls", order_id)

                if JAD_ID == 1105:
                    high_q.enqueue("server.custom.jad1105.inflow_sync.complete_inflow_order", order_id)

                if current_status == "API_SHIPPING":
                    default_q.enqueue("server.siu_webhooks.update_siu_process_status", "shipOrder", "COMPLETE", order_id)

                if JAD_ID == 15:
                    fulfilled_at = await conn.fetchval(
                        """
                        SELECT fulfilled_at
                        FROM uni_order
                        WHERE id = $1
                    """,
                        order_id,
                    )
                    if not fulfilled_at:
                        await conn.execute(
                            """
                            UPDATE uni_order
                            SET fulfilled_at = NOW()
                            WHERE id = $1
                        """,
                        order_id,
                    )

            elif status == "CANCELED":
                recompute_order_profit = True
                mails_q.enqueue_in(timedelta(seconds=5), "mailer.models.trigger_order_event", order_id, "order_canceled")
                items = await conn.fetch(
                    """
                    SELECT id
                    FROM uni_orderitem
                    WHERE order_id = $1
                """,
                    order_id,
                )
                for item in items:
                    if JAD_ID != 279:
                        await unpick_item(item["id"])
                    else:
                        await complete_order(item["id"])
                if current_status == "API_SHIPPING":
                    default_q.enqueue("server.siu_webhooks.update_siu_process_status", order_id, "CANCELED")
            elif status == "RETURNED":
                recompute_order_profit = True
                mails_q.enqueue_in(timedelta(seconds=5), "mailer.models.trigger_order_event", order_id, "order_returned")

            # THIS NEEDS TO BE DONE WHEN THE NEW FRONTEND IS USED
            # if status not in [
            #     "OPEN",
            #     "LVB",
            #     "FBA",
            #     "BACKORDER",
            #     "WACHT OP BETALING",
            #     "WACHT OP ADRES",
            #     "AFHAALPUNT",
            # ]:
            #     await async_debounce(update_active_shipment_card, 500)()
            #     await async_debounce(update_order_items_nav, 500)()
            fields = []
            set_clauses = []

            for i, (field, value) in enumerate(fields_to_update.items(), start=1):
                fields.append(value)
                set_clauses.append(f"{field} = ${i}")
            await conn.execute(
                f"""
                UPDATE uni_order
                SET {', '.join(set_clauses)}
                WHERE id = ${len(fields) + 1}
            """,
                *fields,
                order_id,
            )
            if recompute_order_profit:
                await set_order_profit(order_id)

            default_q.enqueue("uni.tasks.set_status_in_channel", order_id, status)

            if recompute_stock_per_type:
                products = await conn.fetch(
                    """
                    SELECT DISTINCT s.product_id
                    FROM uni_supply s
                    JOIN uni_orderitem oi ON s.order_item_id = oi.id
                    WHERE oi.order_id = $1
                """,
                    order_id,
                )
                for product in products:
                    await acache_stock_per_type(product["product_id"])

            if channel_id := await conn.fetchval("SELECT id FROM optiply_optiply LIMIT 1"):
                default_q.enqueue("optiply.tasks.update_or_create_sellorder", channel_id, order_id)

            if status == "OPEN" and current_status == "DRAFT":
                await recompute_order_metadata(order_id)
            return True
        return False


async def unpick_item(order_item_id, cause=""):
    # Get distinct products for this order item's supplies
    async with get_pg().acquire() as conn:
        products = await conn.fetch(
            """
            SELECT DISTINCT s.product_id
            FROM uni_supply s
            WHERE s.order_item_id = $1
            ORDER BY s.product_id
        """,
            order_item_id,
        )

        # Unpick each product
        for product in products:
            await unpick_order_item(order_item_id, product["product_id"], cause=cause)


async def unpick_order_item(order_item_id, product_id, cause=""):
    async with get_pg().acquire() as conn:
        from server.inventory import alocal_stock_supply, aset_updated_stock_at

        # Get sales channel name for the order
        sales_channel_name = await conn.fetchval(
            """
            SELECT sc.name
            FROM uni_order uo
            JOIN uni_saleschannel sc ON uo.sales_channel_id = sc.id
            WHERE uo.id = (
                SELECT order_id
                FROM uni_orderitem
                WHERE id = $1
            )
        """,
            order_item_id,
        )

        old_stock = await alocal_stock_supply(product_id)

        # Get location id for warehouse ???
        location_id = await conn.fetchval(
            """
            SELECT l.id
            FROM uni_location l
            JOIN ware_warehouse w ON l.warehouse_id = w.id
            WHERE w.name = '???'
            LIMIT 1
        """
        )

        await conn.execute(
            """
            DELETE FROM uni_parcel_supplies
            WHERE supply_id IN (
                SELECT id
                FROM uni_supply
                WHERE order_item_id = $1
                AND product_id = $2
                AND location_id = $3
            )
        """,
            order_item_id,
            product_id,
            location_id,
        )

        await conn.execute(
            """
            DELETE FROM uni_supply
            WHERE order_item_id = $1
            AND product_id = $2
            AND location_id = $3
        """,
            order_item_id,
            product_id,
            location_id,
        )

        await aset_updated_stock_at(product_id, old_stock)

        locations = await conn.fetch(
            """
            SELECT location_id as location, SUM(amount) as amount
            FROM uni_supply
            WHERE order_item_id = $1 AND product_id = $2
            GROUP BY location_id
        """,
            order_item_id,
            product_id,
        )

        await conn.execute(
            """
            UPDATE uni_supply
            SET reserved_at = NULL, order_item_id = NULL
            WHERE order_item_id = $1
            AND product_id = $2
        """,
            order_item_id,
            product_id,
        )

        for locationdict in locations:
            location_id = locationdict.get("location")
            amount = locationdict.get("amount")

            quantities = await conn.fetchrow(
                """
                SELECT
                    COALESCE(SUM(amount) FILTER (WHERE location_id = $1), 0) as amount_location,
                    COALESCE(SUM(amount), 0) as amount_total
                FROM uni_supply
                WHERE product_id = $2
                AND deleted_at IS NULL
                AND reserved_at IS NULL
            """,
                location_id,
                product_id,
            )
            current_quantity = quantities["amount_location"]
            all_location_total = quantities.get("amount_total") or 0

            await conn.execute(
                """
                INSERT INTO uni_inventorymutationbutsane
                (product_id, location_id, prev_total, new_total, all_location_total, cause, inserted_at)
                VALUES ($1, $2, $3, $4, $5, $6, NOW())
            """,
                product_id,
                location_id,
                current_quantity - amount,
                current_quantity,
                all_location_total,
                cause or f"{sales_channel_name} annulering item {order_item_id}",
            )


async def complete_order(order_item_id):
    async with get_pg().acquire() as conn:
        from server.inventory import alocal_stock_supply, aset_updated_stock_at
        has_parcels = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM uni_parcel_orders po
                WHERE po.order_id = (
                    SELECT order_id
                    FROM uni_orderitem
                    WHERE id = $1
                )
            )
        """,
            order_item_id,
        )

        if JAD_ID == 197 and not has_parcels:
            await unpick_item(order_item_id, "Extern verzonden")
            return []
        else:
            supplies = await conn.fetch(
                """
                SELECT id
                FROM uni_supply
                WHERE order_item_id = $1
                AND deleted_at IS NULL
            """,
                order_item_id,
            )
            old_stocks = {}
            products = await conn.fetch(
                """
                SELECT DISTINCT product_id
                FROM uni_supply
                WHERE order_item_id = $1
            """,
                order_item_id,
            )
            for p in [p["product_id"] for p in products]:
                old_stocks[p] = await alocal_stock_supply(p)
            await conn.execute(
                """
                UPDATE uni_supply
                SET deleted_at = NOW()
                WHERE order_item_id = $1
            """,
                order_item_id,
            )
            for p in [p["product_id"] for p in products]:
                await aset_updated_stock_at(p, old_stocks[p])
            return supplies

async def custom_recompute_order_metadata_314(picked_data):
    async with get_pg().acquire() as conn:
        package_details = {  # space_used, qty, sum
            "letterbox_s": [0, 0, 0],
            "letterbox_m": [0, 0, 0],
            "letterbox_l": [0, 0, 0],
            "package_s": [0, 0, 0],
            "package_m": [0, 0, 0],
            "package_l": [0, 0, 0],
        }
        for product_id, count in picked_data.items():
            product_data = await conn.fetchrow(
                """
                SELECT data
                FROM uni_product
                WHERE id = $1
            """,
                product_id,
            )
            for key, value in package_details.items():
                if not product_data.get(key):
                    package_details[key][0] += 2
                else:
                    package_details[key][0] += count / product_data.get(key)
                if product_data.get(key) != None:
                    package_details[key][1] += 1
                    package_details[key][2] += count
        return package_details


async def advanced_packaging_recompute_order_item(order_id):
    async with get_pg().acquire() as conn:
        import itertools
        from copy import deepcopy

        packaging_products = await conn.fetch(
            """
            SELECT id, packaging_priority, letter, mailbox, package
            FROM uni_product
            WHERE packaging = true
        """
        )
        packaging_products_dict = {}
        for packaging_product in packaging_products:
            packaging_products_dict[str(packaging_product["id"])] = {
                "packaging_priority": packaging_product["packaging_priority"],
                "letter": packaging_product["letter"],
                "mailbox": packaging_product["mailbox"],
                "package": packaging_product["package"],
            }

        percentage_dict = {}
        percentages_list = []
        products_count = {}
        order_items = await conn.fetch(
            """
            SELECT oi.quantity_ordered, oi.product_id
            FROM uni_orderitem oi
            JOIN uni_product p ON p.id = oi.product_id
            WHERE oi.order_id = $1
            AND p.packaging = false
        """,
            order_id,
        )
        for order_item in order_items:
            product_id = order_item["product_id"]
            if product_id not in products_count:
                products_count[product_id] = order_item["quantity_ordered"]
            else:
                products_count[product_id] += order_item["quantity_ordered"]
        products_count = [(product_id, count) for product_id, count in products_count.items()]

        for product_id, count in products_count:
            percentage_dict[str(product_id)] = {}
            product_percentage_list = []
            for key in packaging_products_dict.keys():
                product_data = await conn.fetchrow(
                    """
                    SELECT count
                    FROM uni_packaging
                    WHERE product_id = $1 and container_id = $2
                """,
                    int(product_id),
                    int(key),
                )
                available_space = product_data["count"] if product_data else 0
                if available_space:
                    usage = count / available_space
                    percentage_dict[str(product_id)][key] = usage
                    product_percentage_list.append((key, usage))
            percentages_list.append(product_percentage_list)

        base_combination = {}
        best_combination = {}

        for i in range(
            int(len(percentages_list) / 3) + 1
        ):  # We calculate in groups of 3 to keep the amount of possibilities down (6 package types with 3 products would mean 216 possibilites, 4 would be 1296, 6 would be 46656. If we split this up into two groups we lose some precision, but it would be 216+216 combinations)
            best_combination_sum = 0
            best_combination_count = 0
            sub_percentages_list = percentages_list[i * 3 : i * 3 + 3]  # [[(1,2), (2,3)], [(1,2)]]
            max_counters = [(len(values)) for values in sub_percentages_list]  # [2, 1]
            max_ranges = [list(range(length)) for length in max_counters]  # [[0, 1], [0]]
            for possibility_indexes in itertools.product(*max_ranges):  # [(0, 0), (1, 0)]
                possibility = deepcopy(base_combination)
                for index, possibility_index in enumerate(possibility_indexes):
                    product, percentage = sub_percentages_list[index][possibility_index]
                    if product not in possibility:
                        possibility[product] = percentage
                    else:
                        possibility[product] += percentage
                current_sum = 0
                current_count = 0
                for packaging_product, amount in possibility.items():
                    current_sum += packaging_products_dict[packaging_product]["packaging_priority"] * math.ceil(amount)
                    current_count += math.ceil(amount)
                if (
                    not best_combination_sum
                    or current_count < best_combination_count
                    or (current_count == best_combination_count and current_sum < best_combination_sum)
                ):
                    best_combination = possibility
                    best_combination_sum = current_sum
                    best_combination_count = current_count
            base_combination = best_combination
        return {
            key: (
                math.ceil(value),
                packaging_products_dict[key]["letter"],
                packaging_products_dict[key]["mailbox"],
                packaging_products_dict[key]["package"],
            )
            for key, value in best_combination.items()
        }


async def advanced_packaging_recompute_supply(picked_data):
    async with get_pg().acquire() as conn:
        import itertools
        from copy import deepcopy

        packaging_products = await conn.fetch(
            """
            SELECT id, packaging_priority, letter, mailbox, package
            FROM uni_product
            WHERE packaging = true
        """
        )
        packaging_products_dict = {}
        for packaging_product in packaging_products:
            packaging_products_dict[str(packaging_product["id"])] = {
                "packaging_priority": packaging_product["packaging_priority"],
                "letter": packaging_product["letter"],
                "mailbox": packaging_product["mailbox"],
                "package": packaging_product["package"],
            }

        percentage_dict = {}
        percentages_list = []
        products_count = [(product_id, count) for product_id, count in picked_data.items()]
        for product_id, count in products_count:
            percentage_dict[str(product_id)] = {}
            product_percentage_list = []
            for key in packaging_products_dict.keys():
                product_data = await conn.fetchrow(
                    """
                    SELECT count
                    FROM uni_packaging
                    WHERE product_id = $1 and container_id = $2
                """,
                    int(product_id),
                    int(key),
                )
                available_space = product_data["count"] if product_data else 0
                if available_space:
                    usage = count / available_space
                    percentage_dict[str(product_id)][key] = usage
                    product_percentage_list.append((key, usage))
            percentages_list.append(product_percentage_list)

        base_combination = {}
        best_combination = {}

        for i in range(
            int(len(percentages_list) / 3) + 1
        ):  # We calculate in groups of 3 to keep the amount of possibilities down (6 package types with 3 products would mean 216 possibilites, 4 would be 1296, 6 would be 46656. If we split this up into two groups we lose some precision, but it would be 216+216 combinations)
            best_combination_sum = 0
            best_combination_count = 0
            sub_percentages_list = percentages_list[i * 3 : i * 3 + 3]
            max_counters = [(len(values)) for values in sub_percentages_list]
            max_ranges = [list(range(length)) for length in max_counters]
            for possibility_indexes in itertools.product(*max_ranges):
                possibility = deepcopy(base_combination)
                for index, possibility_index in enumerate(possibility_indexes):
                    product, percentage = sub_percentages_list[index][possibility_index]
                    if product not in possibility:
                        possibility[product] = percentage
                    else:
                        possibility[product] += percentage
                current_sum = 0
                current_count = 0
                for packaging_product, amount in possibility.items():
                    current_sum += packaging_products_dict[packaging_product]["packaging_priority"] * math.ceil(amount)
                    current_count += math.ceil(amount)
                if (
                    not best_combination_sum
                    or current_count < best_combination_count
                    or (current_count == best_combination_count and current_sum < best_combination_sum)
                ):
                    best_combination = possibility
                    best_combination_sum = current_sum
                    best_combination_count = current_count
            base_combination = best_combination
        return {
            key: (
                math.ceil(value),
                packaging_products_dict[key]["letter"],
                packaging_products_dict[key]["mailbox"],
                packaging_products_dict[key]["package"],
            )
            for key, value in best_combination.items()
        }


async def arecompute_shipmentconfig(order_id):
    async with get_pg().acquire() as conn:
        if JAD_ID not in [
            43,
            100,
        ]:
            chosen_shipmentconfig = None
            for shipmentconfig in await conn.fetch(
                """
                SELECT id
                FROM uni_shipmentconfig
                WHERE active = true
                ORDER BY priority
            """
            ):
                shipmentconfig_id = shipmentconfig["id"]
                logger.debug(f"🔍 {order_id} considering {shipmentconfig_id}")
                if await contains_object(shipmentconfig_id, "uni_shipmentconfig", order_id, "uni_order"):
                    logger.debug(f"🆗 {order_id} picked {shipmentconfig_id}")
                    chosen_shipmentconfig = shipmentconfig_id
                    break
            await conn.execute(
                """
                UPDATE uni_order
                SET shipmentconfig_id = $1
                WHERE id = $2
            """,
                chosen_shipmentconfig,
                order_id,
            )


async def arecompute_shipmentconfigs():
    if JAD_ID in [
        43,
        100,
    ]:
        return
    async with get_pg().acquire() as conn:
        order_ids = await conn.fetch(
            """
            SELECT id
            FROM uni_order
            WHERE status IN ('OPEN', 'BACKORDER')
        """
    )
    order_ids = [order_id["id"] for order_id in order_ids]
    for order_id in order_ids:
        await arecompute_shipmentconfig(order_id)


# TODO(danilo): manage cancel/shipped/returned count in order items, subtract those from the items_count and items_quantity_ordered_sum here (these two should be renamed to OPEN-count/-quantity_ordered_sum)
async def recompute_order_metadata(order_id):
    async with get_pg().acquire() as conn:
        order_id = int(order_id)
        advanced_packaging = await get_redis().get("siu:system:advanced_packaging")
        packaging_determines_package_type = await get_redis().get("siu:system:packaging_determines_package_type")

        picking_data, has_mispicks = await picking_data_simplified(order_id)
        fields_to_update = {}
        if has_mispicks:
            fields_to_update["has_mispicks"] = True

        different_items_count = len(picking_data)
        fields_to_update["different_items_count"] = different_items_count
        order_raw_data = await conn.fetch(
            """
            SELECT uni_order.raw, uni_order.lock_labels_needed, uni_order.status, uni_order.customer_country,
                    uni_saleschannel.meta_data_id as sales_channel_meta_data_id, uni_order.checked_address,
                    uni_order.sales_channel_id as sales_channel_id
            FROM uni_order
            LEFT JOIN uni_saleschannel ON uni_order.sales_channel_id = uni_saleschannel.id
            WHERE uni_order.id = $1
        """,
            order_id,
        )
        # Convert the Record to a dict, decrypt it, and store in a new variable
        decrypted_order_raw_data = decrypt_order_dict(dict(order_raw_data[0]))

        # Use the new variable for accessing decrypted data
        order_raw = decrypted_order_raw_data["raw"]
        lock_labels_needed = decrypted_order_raw_data["lock_labels_needed"]
        status = decrypted_order_raw_data["status"]
        customer_country = decrypted_order_raw_data["customer_country"]
        sales_channel_meta_data_id = decrypted_order_raw_data["sales_channel_meta_data_id"]
        checked_address = decrypted_order_raw_data["checked_address"]
        sales_channel_id = decrypted_order_raw_data["sales_channel_id"]
        # Get product data and calculate sums
        product_data = await conn.fetch(
            """
            WITH product_counts AS (
                SELECT p.id, p.letter, p.mailbox, p.package, p.weight, p.length, p.width, p.height, p.data, pd.count as quantity
                FROM uni_product p
                JOIN (SELECT unnest($1::int[]) as id, unnest($2::int[]) as count) pd ON p.id = pd.id
            )
            SELECT
                SUM(quantity) as items_sum,
                SUM(CASE WHEN letter IS NULL THEN quantity * 2
                            WHEN letter = 0 THEN quantity * 2
                            ELSE quantity::float / letter END) as letter_space_used,
                SUM(CASE WHEN letter IS NOT NULL THEN quantity ELSE 0 END) as letter_sum,
                COUNT(CASE WHEN letter IS NOT NULL THEN 1 END) as letter_qty,
                SUM(CASE WHEN mailbox IS NULL THEN quantity * 2
                            WHEN mailbox = 0 THEN quantity * 2
                            ELSE quantity::float / mailbox END) as mailbox_space_used,
                SUM(CASE WHEN mailbox IS NOT NULL THEN quantity ELSE 0 END) as mailbox_sum,
                COUNT(CASE WHEN mailbox IS NOT NULL THEN 1 END) as mailbox_qty,
                SUM(CASE WHEN package IS NULL THEN 0
                            WHEN package = 0 THEN 0
                            ELSE quantity::float / package END) as package_space_used,
                SUM(CASE WHEN package IS NOT NULL THEN quantity ELSE 0 END) as package_sum,
                COUNT(CASE WHEN package IS NOT NULL THEN 1 END) as package_qty,
                SUM(CASE WHEN weight IS NOT NULL THEN weight::bigint * quantity ELSE 0 END) as total_weight,
                bool_or(weight IS NULL) as none_weight,
                MAX(GREATEST(
                    COALESCE(width, 0),
                    COALESCE(height, 0),
                    COALESCE(length, 0)
                )) as longest_side,
                SUM(
                    COALESCE(width, 0)::bigint *
                    COALESCE(height, 0) *
                    COALESCE(length, 0) *
                    quantity
                ) as volume,
                bool_or((data->>'courier')::bool) as courier,
                bool_or((data->>'logique')::bool) as logique,
                bool_or((data->>'signature')::bool) as signature,
                SUM(
                    COALESCE((data->>'insurance')::float, 0) *
                    quantity::float
                ) as insurance
            FROM product_counts
        """,
            list(picking_data.keys()),
            list(picking_data.values()),
        )

        row = product_data[0]
        items_sum = row["items_sum"]
        letter_space_used = row["letter_space_used"]
        letter_qty = row["letter_qty"]
        mailbox_space_used = row["mailbox_space_used"]
        mailbox_qty = row["mailbox_qty"]
        package_space_used = row["package_space_used"]
        package_qty = row["package_qty"]
        weight = row["total_weight"]
        none_weight = row["none_weight"]
        longest_side = row["longest_side"] or 0
        volume = row["volume"]
        courier = row["courier"]
        logique = row["logique"]
        signature = row["signature"]
        insurance = int(row["insurance"]) if row["insurance"] else 0

        fields_to_update["logique_custom"] = logique
        fields_to_update["signature_needed"] = signature
        fields_to_update["volume"] = volume
        fields_to_update["longest_side"] = longest_side
        fields_to_update["courier_custom"] = courier
        fields_to_update["insurance_value"] = insurance


        fields_to_update["items_sum"] = items_sum

        if not none_weight:
            if await get_redis().get("siu:system:letter-weight"):
                letter_weight = int((await get_redis().get("siu:system:letter-weight")).decode())
                weight = (weight or 0) + letter_weight
            if fixed_extra_weight := await get_redis().get("siu:system:fixed_extra_weight"):
                fixed_extra_weight = fixed_extra_weight.decode()
                weight += int(fixed_extra_weight)
            fields_to_update["weight"] = weight

        if JAD_ID in [102, 0] and different_items_count == 1:
            if order_raw.get("myparcelletter") == list(picking_data.values())[0]:
                fields_to_update["myparcel_letter"] = True
            else:
                fields_to_update["myparcel_letter"] = False
        else:
            fields_to_update["myparcel_letter"] = False

        letters_have_weights = [12, 15, 102, 199, 231]

        if not advanced_packaging or not packaging_determines_package_type:
            if JAD_ID not in [314]:
                if (
                    JAD_ID in letters_have_weights and letter_qty == different_items_count and letter_space_used != None and letter_space_used <= 1.0001
                ):  # Allow for floating point errors, and products that dont matter can be set to product.letter = 100000 or something
                    if weight <= 20:
                        weight_str = "<20"
                    elif weight <= 50:
                        weight_str = "<50"
                    elif weight <= 100:
                        weight_str = "<100"
                    elif weight <= 350:
                        weight_str = "<350"
                    else:
                        weight_str = "350+"
                    fields_to_update["package_type_programming"] = f"Brief {weight_str}"
                elif (
                    JAD_ID not in letters_have_weights
                    and letter_qty == different_items_count
                    and letter_space_used != None
                    and letter_space_used <= 1.0001
                ):
                    fields_to_update["package_type_programming"] = "Brief"
                elif (
                    (await get_redis().get("siu:system:disabled_package_mailbox") or JAD_ID > 306)
                    and mailbox_qty == different_items_count
                    and mailbox_space_used != None
                    and mailbox_space_used <= 1.0001
                ):  # Maybe this should be default for all
                    fields_to_update["package_type_programming"] = "Brievenbus"
                elif mailbox_qty == different_items_count and different_items_count == 1 and mailbox_space_used != None and mailbox_space_used <= 1.0001:
                    fields_to_update["package_type_programming"] = "Brievenbus"
                elif mailbox_qty == different_items_count and mailbox_space_used != None and mailbox_space_used <= 1.0001:
                    fields_to_update["package_type_programming"] = "Pakket/Brievenbus"
                elif mailbox_qty == different_items_count and mailbox_space_used != None:
                    fields_to_update["package_type_programming"] = "Pakket"
                    if await get_redis().get("siu:system:multi_collo") and not lock_labels_needed:
                        labels_needed = int(package_space_used)
                        if package_space_used % 1 > 0.004:  # This number can maybe be lower (0.001 for example) | Used to be 0.04
                            labels_needed += 1
                        fields_to_update["labels_needed"] = max(labels_needed, 1)
                else:
                    fields_to_update["package_type_programming"] = "?"
                if not picking_data:
                    fields_to_update["package_type_programming"] = "?"
            elif JAD_ID == 314:
                results = await custom_recompute_order_metadata_314(picking_data)
                for key, values in results.items():  # space used, qty, sum
                    if values[1] == different_items_count and values[0] <= 1.0001:
                        fields_to_update["package_type_programming"] = key
                        break
                if not picking_data:
                    fields_to_update["package_type_programming"] = "?"

        if advanced_packaging:
            package_item_ids = await conn.fetch(
                """
                SELECT id
                FROM uni_orderitem
                WHERE order_id = $1
                AND product_id IN (
                    SELECT id
                    FROM uni_product
                    WHERE packaging = true
                )
            """,
                order_id,
            )
            package_item_ids = [package_item_id["id"] for package_item_id in package_item_ids]
            for package_item_id in package_item_ids:
                await unpick_item(package_item_id)

                await conn.execute(
                    """
                    DELETE FROM uni_orderitem_events
                    WHERE orderitem_id = $1
                """,
                    package_item_id,
                )

                await conn.execute(
                    """
                    DELETE FROM uni_productsale
                    WHERE order_item_id = $1
                """,
                    package_item_id,
                )

                await conn.execute(
                    """
                    DELETE FROM uni_orderitem
                    WHERE id = $1
                """,
                    package_item_id,
                )
            if await get_redis().get("siu:system:recompute_on_items"):
                packaging = await advanced_packaging_recompute_order_item(order_id)
            else:
                packaging = await advanced_packaging_recompute_supply(picking_data)
            letter_none = False
            mailbox_none = False
            package_none = False
            letter_total = 0
            mailbox_total = 0
            package_total = 0
            for index, (product_id, (count, letter, mailbox, package)) in enumerate(packaging.items()):
                if letter == None:
                    letter_none = True
                else:
                    if letter == 0:
                        letter_total += 2
                    else:
                        letter_total += count / letter
                if mailbox == None:
                    mailbox_none = True
                else:
                    if mailbox == 0:
                        mailbox_total += 2
                    else:
                        mailbox_total += count / mailbox
                if package == None or package == 0:
                    package_none = True
                else:
                    package_total += count / package
                await add_product_to_order(order_id, product_id, count, run_recompute=False)
            if packaging_determines_package_type:
                if not packaging:
                    fields_to_update["package_type_programming"] = "Pakket"
                elif not mailbox_none:
                    if not letter_none and letter_total <= 1:
                        fields_to_update["package_type_programming"] = "Brief"
                    elif not mailbox_none and mailbox_total <= 1:
                        fields_to_update["package_type_programming"] = "Brievenbus"
                    else:
                        fields_to_update["package_type_programming"] = "Pakket"
                else:
                    fields_to_update["package_type_programming"] = "?"
                if await get_redis().get("siu:system:multi_collo") and not lock_labels_needed and not package_none:
                    labels_needed = math.ceil(package_total)
                    fields_to_update["labels_needed"] = max(labels_needed, 1)

        if (
            not none_weight
        ):  # Remove letter weight if it was not a letter, we have to add the weight beforehand to make sure the weight is correct for the letter_have_weights
            if await get_redis().get("siu:system:letter-weight") and "Brief" not in fields_to_update.get("package_type_programming", ""):
                letter_weight = int((await get_redis().get("siu:system:letter-weight")).decode())
                weight -= letter_weight
                fields_to_update["weight"] = weight

        await conn.execute(
            """
            UPDATE uni_order
            SET raw = $1,
                weight = $2,
                package_type_programming = $3,
                labels_needed = $4,
                logique_custom = $6,
                signature_needed = $7,
                volume = $8,
                longest_side = $9,
                courier_custom = $10,
                insurance_value = $11,
                myparcel_letter = $12,
                items_sum = $13,
                has_mispicks = $14,
                different_items_count = $15
            WHERE id = $5
        """,
            encrypt(json.dumps(order_raw)),
            fields_to_update.get("weight", weight),  # Use dict value if available, else local var
            fields_to_update.get("package_type_programming", "?"), # Match DB default
            fields_to_update.get("labels_needed", 1),
            order_id,
            fields_to_update.get("logique_custom", False),
            fields_to_update.get("signature_needed", False),
            fields_to_update.get("volume"), # Defaults to None if not present
            fields_to_update.get("longest_side"), # Defaults to None if not present
            fields_to_update.get("courier_custom", False),
            fields_to_update.get("insurance_value"), # Defaults to None if not present
            fields_to_update.get("myparcel_letter", False),
            fields_to_update.get("items_sum") or 0,  # Use `or 0` to handle None
            fields_to_update.get("has_mispicks", False),
            fields_to_update.get("different_items_count", 0),
        )

        await arecompute_shipmentconfig(order_id)

        if JAD_ID == 314 and status == "OPEN":
            product_id = {
                "letterbox_s": 57,
                "letterbox_m": 58,
                "letterbox_l": 59,
                "package_s": 60,
                "package_m": 61,
                "package_l": 62,
            }.get(fields_to_update.get("package_type_programming"))
            if product_id:
                if not await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM uni_orderitem
                        WHERE order_id = $1 AND product_id = $2
                    )
                """,
                    order_id,
                    product_id,
                ):
                    if order_item := await conn.fetchrow(
                        """
                        SELECT id, product_id
                        FROM uni_orderitem
                        WHERE order_id = $1
                        AND EXISTS (
                            SELECT 1 FROM uni_product p
                            WHERE p.id = uni_orderitem.product_id
                            AND p.packaging = true
                        )
                        LIMIT 1
                    """,
                        order_id,
                    ):
                        await unpick_order_item(order_item["id"])
                        await conn.execute(
                            """
                            UPDATE uni_orderitem
                            SET product_id = $1
                            WHERE id = $2
                        """,
                            product_id,
                            order_item["id"],
                        )
                    else:
                        await add_product_to_order(order_id, product_id, 1, run_recompute=False)
                    await decrement_product_stock_by_order_item(order_item["id"])

        default_q = get_queue("default")
        if await get_redis().get("postcode_API"):
            if not checked_address and not sales_channel_meta_data_id == 6:
                default_q.enqueue("uni.tasks.check_postcode_apis", order_id)
        elif await get_redis().get("kadaster_API"):
            if customer_country == "NL" and not checked_address and not sales_channel_meta_data_id == 6:
                default_q.enqueue("uni.tasks.check_postcode_apis", order_id)
        elif await get_redis().get("check_google_maps"):
            if not checked_address and not sales_channel_meta_data_id == 6:
                default_q.enqueue("uni.tasks.check_postcode_apis", order_id)

        if JAD_ID != 386:  # TODO(danilo): remove this whole call here after you confirm it works well via the ->OPEN set_order_status transition
            default_q.enqueue("uni.tasks.distribute_order_check", order_id)

        if await get_redis().get("ExactOnline:make_orders") and sales_channel_id == 20 and not await get_redis().get(f"ExactOnline:order_processed:{order_id}"):
            default_q.enqueue("exactonline.tasks.create_exact_sales_order_with_ratelimit", order_id)

        await set_order_profit(order_id)

# This function needs to be deprecated
def make_order_dictionaries(orders_paginated):
    from django.db.models import Count, Exists, OuterRef, Sum

    from events.models import Event
    from uni.models import Order, OrderItem, Supply
    from uni.utils import sublocation_string

    paginated_order_ids = [order.id for order in orders_paginated]

    orders = (
        Order.objects.filter(id__in=paginated_order_ids)
        .values(
            "id",
            "visible_store_id",
            "store_id",
            "order_date",
            "customer_country",
            "customer_city",
            "customer_firstname",
            "customer_lastname",
            "sales_channel__name",
            "sales_channel__meta_data_id",
            "sales_channel__meta_data__logo_path",
            "price",
            "currency",
            "latest_handover_at",
            "latest_delivery",
            "exact_delivery",
            # "has_messages",
            "raw",
            "shipmentconfig__name",
            "shipmentconfig_id",
            "package_type_programming",
            "bolorder__bol_has_mailbox_option",
            "checked_custom",
        )
        .annotate(has_messages=Exists(Event.objects.filter(temporary_parcels_new=OuterRef("pk"), meta_data__type="message")))
    )
    order_items = (
        OrderItem.objects.filter(order_id__in=paginated_order_ids)
        .select_related("product", "offer")
        .values(
            "order_id",
            "id",
            "product__image_url_view__image_url",
            "product__id",
            "product__title",
            "product__ean",
            "product__sku",
            "product__is_set",
            "status",
            "vvb",
            "raw__notes",
            "quantity_ordered",
            "unit_price",
            "editable",
            "offer__image_url",
            "offer__id",
            "offer__ean",
            "offer__seller_sku",
            "offer__title",
            "bolorderitem__vvb",
        )
    )

    order_items_dict = defaultdict(list)
    order_item_ids = []
    for item in order_items:
        order_items_dict[item["order_id"]].append(item)
        order_item_ids.append(item["id"])

    supplies = Supply.objects.filter(order_item__in=order_item_ids).select_related("location__warehouse")
    supplies_product_sets = (
        supplies.filter()
        .values(
            "order_item_id",
            "product_id",
            "product__sku",
            "product__title",
            "product__ean",
            "product__image_url_view__image_url",
            "location__warehouse__name",
            "location__sublocations",
            "location_id",
        )
        .annotate(sum_amount=Sum("amount"))
    )
    supplies_non_product_sets = (
        supplies.filter(product__is_set=False)
        .values("order_item_id", "location__warehouse__name", "location__sublocations", "location_id")
        .annotate(amount=Count("location_id"))
    )

    supplies_dict_sets = {}
    for supply in supplies_product_sets:
        order_item_id = supply["order_item_id"]
        product_info = {
            "id": supply["product_id"],
            "sku": supply["product__sku"],
            "title": supply["product__title"],
            "ean": supply["product__ean"],
            "image_url_view__image_url": supply["product__image_url_view__image_url"],
        }
        location_info = {
            "location__warehouse__name": supply["location__warehouse__name"],
            "location__sublocations": sublocation_string(supply["location__sublocations"]),
            "location_id": supply["location_id"],
            "amount": supply["sum_amount"],
        }
        if order_item_id not in supplies_dict_sets:
            supplies_dict_sets[order_item_id] = []
        product_tuple = next((t for t in supplies_dict_sets[order_item_id] if t[0]["id"] == product_info["id"]), None)
        if not product_tuple:
            product_tuple = (product_info, [])
            supplies_dict_sets[order_item_id].append(product_tuple)
        product_tuple[1].append(location_info)
    supplies_dict = {}
    for supply in supplies_non_product_sets:
        if supply["order_item_id"] not in supplies_dict:
            supplies_dict[supply["order_item_id"]] = []
        supplies_dict[supply["order_item_id"]].append(supply)

    for items in order_items_dict.values():
        for item in items:
            item["item_supplies_set"] = supplies_dict_sets.get(item["id"], [])
            item["item_supplies"] = supplies_dict.get(item["id"], [])
    for order in orders:
        decrypt_order_dict(order)
        order["items"] = order_items_dict[order["id"]]

    # Sort orders by their index in paginated_order_ids if provided
    if paginated_order_ids:
        orders = sorted(orders, key=lambda x: paginated_order_ids.index(x["id"]))

    return orders


transporter_error_messages = {
    # General errors
    "unauthorized": "Je bent niet geautoriseerd. Gelieve de inloggegevens te controleren of contact op te nemen met de vervoerder.",
    "maintenance_error": "De vervoerder voert momenteel onderhoud uit aan hun API. Gelieve later opnieuw te proberen.",
    "internal_error": "Er is een interne fout opgetreden bij de vervoerder. Gelieve later opnieuw te proberen of contact op te nemen met de vervoerder.",
    "api_error": "De API geeft een error. Probeer het later opnieuw of neem contact met ons op voor verdere hulp.",
    "overdue_invoices": "De vervoerder heeft een foutmelding gekregen omdat er openstaande facturen zijn. Gelieve deze te betalen en opnieuw te proberen.",
    "invalid_credentials": "De vervoerder heeft ongeldige inloggegevens. Gelieve de inloggegevens te controleren en opnieuw te proberen.",
    "invalid_character": "Er is een ongeldig karakter gevonden in de gegevens die naar de vervoerder zijn gestuurd. Gelieve de gegevens te controleren en opnieuw te proberen.",
    "unserviceable_area": "Het adres is niet beschikbaar voor deze verzendmethode of vervoerder.",
    "service_point_required": "De vervoerder vereist een servicepunt voor deze verzendmethode.",
    "shipping_method_unavailable": "De geselecteerde verzendmethode is niet beschikbaar voor deze order / producten.",
    "invalid_order_or_canceled": "Deze bestelling is niet geldig of is geannuleerd. Controleer de bestelling in het verkoopkanaal.",
    # Contact transporter
    "contact_stockitup": "Onbekende fout opgetreden, neem contact op met Stockitup.",
    "contact_stockitup_carriercode": "De vervoerderscode mist in de configuratie van de vervoerder, neem contact op met Stockitup.",
    "contact_bol": "Onbekende fout opgetreden, neem contact op met bol.",
    "contact_amazon": "Onbekende fout opgetreden, neem contact op met Amazon.",
    "contact_shopify": "Onbekende fout opgetreden, neem contact op met Shopify.",
    "contact_woocommerce": "Onbekende fout opgetreden, neem contact op met WooCommerce.",
    # Customs declaration errors
    "invalid_customs_declaration": "De douaneverklaring bevat ongeldige gegevens. Controleer de classificatiecodes van de producten (moeten 6, 8 of 10 cijfers zijn).",
    "contact_innosend": "Onbekende fout opgetreden, neem contact op met Innosend.",
    # Transport errors
    "invalid_billing_number": "De opgegeven factuurnummer is ongeldig.",
    "ampere_nog_niet_actief": "Je kan nog geen labels uitprinten, omdat Ampere nog niet geactiveerd is of je startperiode nog niet begonnen is.",
    "multiple_active_contracts": "Je hebt meerdere actieve contracten voor deze vervoerder. Je moet een contract specificeren.",
    "service_point_carrier_mismatch": "De vervoerder heeft een mismatch tussen de verzendmethode en het servicepunt.",
    "invalid_service_point": "Het opgegeven servicepunt is ongeldig.",
    "packstation_not_supported": "Deze verzendmethode ondersteunt geen Packstation adressen. Vul een ander adres in en probeer het opnieuw.",
    "invalid_order_items": "Deze bestelling bevat producten die niet tot dezelfde bestelling behoren.",
    "canceled_order_items": "Deze bestelling bevat producten die al geannuleerd zijn.",
    "postnl_unauthorized_operation": "De vervoerder heeft een foutmelding gekregen omdat de gebruiker niet geautoriseerd is om deze operatie uit te voeren.",
    # Missing fields
    "missing_delivery_option": "De vervoerder heeft een foutmelding gekregen omdat er geen verzendoptie is geselecteerd.",
    "missing_fulfiller": "Om met deze vervoerder te verzenden, moet je een fulfiller hebben aangemaakt die gekoppeld staat aan het magazijn van de bestelling. Ga naar instellingen en voeg een fulfiller toe.",
    "missing_fulfiller_contact": "De vervoerder heeft een foutmelding gekregen omdat er geen contactgegevens zijn ingevuld van de fulfiller. Ga naar Instellingen > Fulfillers en vul deze in.",
    "missing_housenumber": "Het huisnummer ontbreekt in het verzendadres.",
    "missing_street": "De straat ontbreekt in het verzendadres.",
    "missing_city": "De stad ontbreekt in het verzendadres.",
    "missing_country": "Het land ontbreekt in het verzendadres.",
    "missing_name": "De klantnaam ontbreekt in het adres.",
    "missing_first_name": "De voornaam ontbreekt in het verzendadres.",
    "missing_last_name": "De achternaam ontbreekt in het verzendadres.",
    "missing_first_name_billing": "De voornaam ontbreekt in het factuuradres.",
    "missing_last_name_billing": "De achternaam ontbreekt in het factuuradres.",
    "missing_companyname": "De bedrijfsnaam ontbreekt in het verzendadres.",
    "missing_email_address": "Het e-mailadres ontbreekt in het verzendadres.",
    "missing_phonenumber": "Het telefoonnummer ontbreekt in het verzendadres",
    "missing_transporter": "Vervoerder is verplicht, selecteer een vervoerder om verder te gaan.",
    "missing_postalcode": "De postcode ontbreekt in het verzendadres",
    "missing_weight_per_unit": "Gewicht per eenheid (product) mag niet leeg zijn, vul dit in om verder te gaan.",
    "missing_qls_vat_eori_number": "Van de gebruikte handelsnaam is geen BTW en / of EORI nummer bekend. Ga naar je QLS account en vul deze in bij Instellingen -> Handelsnamen -> [handelsnaam] -> Douane",
    "missing_products": "De order bevat geen producten, voeg een product toe om te verschepen.",
    "missing_customs_segment": "Het veld 'Customs segment' is verplicht, vul dit in om verder te gaan.",
    "missing_customs_shipment_type": "Het veld 'Customs shipment type' is verplicht, vul dit in om verder te gaan.",
    "missing_customs_invoice_nr": "Het veld 'Customs invoice number' is verplicht, vul dit in om verder te gaan.",
    "missing_billing_number": "Het veld 'Billing number' is verplicht, vul dit in om verder te gaan.",
    # Seller fields
    "seller_missing_country": "Het land van de vervoerder ontbreekt bij het verkopers adres, ga naar instellingen > addressen en vul dit in.",
    # Invalid fields
    "invalid_ordernumber": "Het ordernummer is ongeldig.",
    "invalid_name": "De voor/achternnaam in het verzendadres is ongeldig.",
    "invalid_housenumber": "Het huisnummer in het verzendadres is geen geldig huisnummer.",
    "invalid_housenumber_start_with_digit": "Het huisnummer in het verzendadres moet beginnen met een cijfer.",
    "invalid_combination_postcode_and_housenumber": "De combinatie van de postcode en het huisnummer komt niet voor in Nederland. Controleer deze op www.postcode.nl.",
    "invalid_street": "De opgegeven straat lijkt ongeldig te zijn. Controleer de spelling en probeer het opnieuw.",
    "invalid_phone_number": "Dit is een ongeldig telefoonnummer, pas dit aan om verder te gaan.",
    "invalid_country": "De opgegeven landcode lijkt ongeldig te zijn. Controleer deze en probeer het opnieuw.",
    "invalid_city": "De opgegeven stad/woonplaats lijkt ongeldig te zijn. Controleer deze en probeer het opnieuw.",
    "invalid_postcode": "De ingevoerde postcode lijkt ongeldig te zijn. Zorg ervoor dat deze correct is ingevuld.",
    "invalid_address": "Het adres in het verzendadres is ongeldig.",
    "invalid_customer_name": "Er is een probleem opgetreden met de klantnaam in het verzendadres.",
    "invalid_email_address": "Het opgegeven e-mailadres is niet geldig. Controleer de spelling en probeer het opnieuw.",
    "invalid_shipment": "Er is een probleem met deze verzending.",
    "invalid_companyname": "Deze verzendmethode is alleen mogelijk voor een zakelijk adres. Vul a.u.b. een bedrijfsnaam in",
    "invalid_tradename": "U heeft geen geldige handelsnaam ingevuld in QLS, corrigeer dit of neem contact met ze op.",
    "invalid_vat_number": "Ongeldig of missend BTW nummer, graag invullen.",
    "invalid_vat_number_or_qls_error": "Controleer het BTW nummer, deze is mogelijk niet correct. Lukt het nog steeds niet? Neem contact op met QLS.",
    "invalid_shipping_method": "De geselecteerde verzendmethode is niet geschikt voor dit adres of voor een product in deze bestelling. Selecteer een andere verzendmethode en probeer het opnieuw.",
    "invalid_country_combination": "De combinatie van verzendland en bestemmingsland is niet geldig voor deze verzendmethode. Controleer de landen en probeer het opnieuw.",
    "receiver_country_must_be_other": "De vervoerder ondersteunt dit land niet voor het verzendadres.",
    "sender_country_must_be_be": "De vervoerder ondersteunt alleen België voor het verzendadres.",
    "invalid_country_must_be_ic": "De vervoerder ondersteunt alleen de Canarische eilanden voor het verzendadres.",
    "receiver_country_must_be_nl": "De vervoerder ondersteunt alleen Nederland voor het verzendadres.",
    "invalid_product_description": "Een van je producten mist een productomschrijving (douane-gegevens). Controleer of de douane-gegevens voor alle producten zijn ingevuld.",
    # Too long fields
    "max_weight": "Het gewicht van het pakket is te zwaar voor de geselecteerde verzendmethode. Probeer een andere verzendmethode of vraag ons om het gewicht van de order te wijzigen.",
    "too_long_name": "De voor/achternnaam in het verzendadres is te lang.",
    "too_long_address_line_1": "Het verzendadres is te lang (maximaal 30 tekens). Controleer de lengte van het adres en probeer het opnieuw.",
    "too_long_housenumber": "Het huisnummer is te lang. Controleer de lengte van het huisnummer en probeer het opnieuw.",
    "too_long_housenumber_extension": "Het huisnummer toevoeging is te lang. Controleer de lengte van de toevoeging en probeer het opnieuw.",
    "too_long_street": "De straatnaam is te lang. Controleer de lengte van de straatnaam en probeer het opnieuw.",
    "too_long_city": "De stad is te lang. Controleer de lengte van de stad en probeer het opnieuw.",
    "too_long_company": "De bedrijfsnaam is te lang. Controleer de lengte van de bedrijfsnaam en probeer het opnieuw.",
    "too_long_reference": "De verzendingsreferentie is te lang. Controleer de lengte van de verzendingsreferentie en probeer het opnieuw.",
    # Customs errors
    "product_requires_vat_or_eori_number": "Verzendmethode is alleen mogelijk als het VAT en het EORI-nummer opgegeven zijn.",
    "missing_hs_code": 'Het veld "HS-code" is leeg op een van de producten in deze order.',
    "invalid_hs_code": 'Het veld "HS-code" heeft een ongeldige waarde op een van de producten in deze order.',
    "forbidden_hs_code": 'Een van de producten in deze order heeft een HS-code die uitgesloten is voor export uit Nederland.',
    "missing_isic_code": 'Het veld "ISIC-code" is leeg op een van de producten in deze order.',
    "missing_country_code_of_origin": 'Het veld "Land van herkomst" is leeg op een van de producten in deze order.',
    "invalid_country_code_of_origin": 'Het veld "Land van herkomst" heeft een ongeldige waarde op een van de producten in deze order.',
    "missing_douane_information": "Je mist douane-gegevens in je producten van deze Stockitup bestelling, of op je vervoerdersomgeving. Voeg dit toe om verder te gaan.",
    # Weight errors
    "minimum_weight_501_grams": "Het minimale gewioht van dit pakket moet hoger zijn dan 500 gram.",
    "minimum_weight_2_kg": "Het minimale gewicht van dit pakket moet hoger zijn dan 2 kg.",
    "minimum_weight_5_kg": "Het minimale gewicht van dit pakket moet hoger zijn dan 5 kg.",
    "minimum_weight_10_kg": "Het minimale gewicht van dit pakket moet hoger zijn dan 10 kg.",
    "minimum_weight_23_kg": "Het minimale gewicht van dit pakket moet hoger zijn dan 23 kg.",
    "weight_not_possible_with_chosen_product": "Het gewicht is niet mogelijk met de gekozen verzendmethode.",
    # Channel specific orders
    "contact_hst_date_calculation": "Informatie niet correct: Datum berekening is niet goed gegaan. Neem contact op met de klantenservice van HST.",
    "not_easy_ship_order": "Deze bestelling is hoogstwaarschijnlijk niet een Easy Ship order, gelieve deze te controleren in het verkoopkanaal.",
    "dhl_service_unavailable": "De vervoerder DHL is momenteel niet beschikbaar, gelieve later opnieuw te proberen.",
    "dpd_service_unavailable": "De vervoerder DPD is momenteel niet beschikbaar, gelieve later opnieuw te proberen.",
    "monta_service_unavailable": "Monta is momenteel niet beschikbaar of heeft een storing, probeer het later opnieuw.",
    "ups_weight_limit_exceeded": "Het pakket is te zwaar voor de gekozen UPS service. Het maximale gewicht per pakket is 70 kg. Verdeel het pakket in kleinere delen of kies een andere verzendmethode.",
    "bol_vvb_invalid_shipping_option": "Tijdens het opvragen van de verzendopties voor deze bestelling gaf bol geen opties met het gekozen pakket type.",
    "magento_check_logs": "Er is iets fout gegaan bij het afronden van deze bestelling in Magento. Bekijk de foutlog in Magento voor meer informatie.",
    "magento_shipping_not_allowed": "Magento: De bestelling staat niet toe dat er een verzending wordt aangemaakt.",
    "magento_shipping_no_products": "Magento: U kunt geen verzending aanmaken zonder producten.",
    "no_matching_order_items": "Een of meerdere order items in de order komen niet overeen met de order items op Amazon. Rond de order handmatig af in Amazon, na enkele minuten wordt het binnen StockItUp ook afgerond.",
    "contact_bpost": "Er is een onbekende fout opgetreden, neem contact op met bPost en stuur een screenshot van het verzendadres. Controleer eerst of alle velden zijn ingevuld bij het verzendadres!"
}
