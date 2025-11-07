"""
This module defines the URL routing for the JAD application.

URL and Naming Conventions:
---------------------------
To maintain consistency and clarity across the codebase, we follow these conventions:

1.  **Server-side Code (Python):**
    -   All Python code, including handler function names (e.g., `bol.repricer.handle`), module names, and variable names, MUST be in **English**.

2.  **Customer-Facing Browser URLs (HTML):**
    -   URLs that serve HTML pages to end-users (our customers) should be in **Dutch**.
    -   This provides a more intuitive experience for our Dutch-speaking user base.
    -   Example: `/bestellingen/` maps to the `orders.handle` handler.
    -   These routes are typically defined in `sellfiller_routes`.

3.  **Internal Developer URLs (HTML):**
    -   URLs for internal tools and dashboards intended for developers MUST be in **English**.
    -   This keeps the development environment consistent for our international team.
    -   Example: `/dev/postgres/`
    -   These routes are defined in `dev_routes`.

4.  **API Endpoints (JSON):**
    -   URLs that serve JSON data for external or internal APIs MUST be in **English**.
    -   This follows global standards for API design.
    -   Example: `/import4you/stock/`
    -   These routes are typically defined in `external_routes` and `thirdparty_routes`.
"""
import logging
import re

from jad import settings


logger = logging.getLogger(__name__)

# Role priorities (highest to lowest)
ROLE_PRIORITIES = [
    "external",
    "buttler",
    "sellfiller",
    "seller",
    "fulfiller",
    "dev",
    "authenticated",
    "thirdparty",
    "public",
]

# Define route handlers for different roles
# Each path can have multiple handlers for different roles
# The handler of the highest priority role will be used

# --- Developer Routes ---
# Convention: English URLs for internal developer tools.
# Handlers are always in English.

dev_routes = [
    ("/", "home.handle", "NO_RIGHTS_REQUIRED"),
    ("/logout/", "auth.logout", "NO_RIGHTS_REQUIRED"),
    ("/uitloggen/", "auth.logout", "NO_RIGHTS_REQUIRED"),

    ("/terminal/ws/", "terminal.websocket_handler", "NO_RIGHTS_REQUIRED"),

    ("/redis/", "redis.handle", "NO_RIGHTS_REQUIRED"),
    ("/redis/execute/", "redis.execute", "NO_RIGHTS_REQUIRED"),
    ("/redis/keys/", "redis.keys", "NO_RIGHTS_REQUIRED"),
    ("/redis/key/meta/", "redis.key_meta", "NO_RIGHTS_REQUIRED"),
    ("/redis/key/value/", "redis.key_value", "NO_RIGHTS_REQUIRED"),

    ("/cache/", "cache.handle", "NO_RIGHTS_REQUIRED"),
    ("/cache/list/", "cache.list_files", "NO_RIGHTS_REQUIRED"),
    ("/cache/file/meta/", "cache.file_meta", "NO_RIGHTS_REQUIRED"),
    ("/cache/file/ast/", "cache.file_ast", "NO_RIGHTS_REQUIRED"),
    ("/cache/symbols/search/", "cache.symbols_search", "NO_RIGHTS_REQUIRED"),
    ("/cache/changed/", "cache.changed_since", "NO_RIGHTS_REQUIRED"),
    ("/cache/events/start/", "cache.events_start", "NO_RIGHTS_REQUIRED"),
    ("/cache/events/stop/", "cache.events_stop", "NO_RIGHTS_REQUIRED"),
    ("/cache/pg/schemas/", "cache.pg_schemas", "NO_RIGHTS_REQUIRED"),
    ("/cache/pg/tables/", "cache.pg_tables", "NO_RIGHTS_REQUIRED"),
    ("/cache/pg/table/meta/", "cache.pg_table_meta", "NO_RIGHTS_REQUIRED"),

    ("/time/", "time.handle", "NO_RIGHTS_REQUIRED"),
    ("/danilo/", "danilo.handle", "NO_RIGHTS_REQUIRED"),



    ("/postgres/schemas/", "postgres.list_schemas", "NO_RIGHTS_REQUIRED"),
    ("/postgres/tables/", "postgres.list_tables", "NO_RIGHTS_REQUIRED"),
    ("/postgres/table/meta/", "postgres.get_table_meta", "NO_RIGHTS_REQUIRED"),
    ("/postgres/table/query/", "postgres.query_table", "NO_RIGHTS_REQUIRED"),
    ("/postgres/query/", "postgres.execute_query", "NO_RIGHTS_REQUIRED"),

    ("/bol/webhooks/", "bol.bol_webhooks_view", "NO_RIGHTS_REQUIRED"),
    ("/bol/webhooks/create/<int>/", "bol.create_bol_webhook", "NO_RIGHTS_REQUIRED", ["sales_channel_id"]),
    ("/bol/webhooks/delete/<int>/", "bol.delete_bol_webhook", "NO_RIGHTS_REQUIRED", ["sales_channel_id"]),

    ("/mcp/", "mcp.handle", "NO_RIGHTS_REQUIRED"),
    ("/mcp/stream/", "mcp.stream", "NO_RIGHTS_REQUIRED"),

    ("/mailer/", "mailer.dev_handle", "NO_RIGHTS_REQUIRED"),
    ("/mailer/signature/<int>/approve/", "mailer.approve_signature", "NO_RIGHTS_REQUIRED", ["signature_id"]),
    ("/mailer/domain/<int>/approve/", "mailer.approve_domain", "NO_RIGHTS_REQUIRED", ["domain_id"]),
    ("/mailer/bulk-sync/", "mailer.bulk_sync_postmark", "NO_RIGHTS_REQUIRED"),
    ("/mailer/export/", "mailer.export_signatures_domains", "NO_RIGHTS_REQUIRED"),

    ("/jobs/", "jobs.handle", "NO_RIGHTS_REQUIRED"),
    ("/frontend/build/", "frontend.build", "NO_RIGHTS_REQUIRED"),
    ("/local/", "local.handle", "NO_RIGHTS_REQUIRED"),
    ("/shutdown/", "shutdown.handle", "NO_RIGHTS_REQUIRED"),

    ("/logs/list/", "logs.list_logs", "NO_RIGHTS_REQUIRED"),
    ("/logs/stream/start/", "logs.stream_start", "NO_RIGHTS_REQUIRED"),
    ("/logs/stream/stop/", "logs.stream_stop", "NO_RIGHTS_REQUIRED"),

    ("/bash/execute/", "bash.execute", "NO_RIGHTS_REQUIRED"),
    ("/rg/execute/", "rg.execute", "NO_RIGHTS_REQUIRED"),
    ("/git/execute/", "git.execute", "NO_RIGHTS_REQUIRED"),
    ("/gh/execute/", "gh.execute", "NO_RIGHTS_REQUIRED"),
    ("/server/exec/", "python.exec_handle", "NO_RIGHTS_REQUIRED"),
    ("/clients/exec/", "js.exec_broadcast", "NO_RIGHTS_REQUIRED"),
    ("/clients/exec/response/", "js.submit_exec_result", "NO_RIGHTS_REQUIRED"),

    ("/dump/list/", "dump.list_items", "NO_RIGHTS_REQUIRED"),
    ("/dump/upload/", "dump.upload", "NO_RIGHTS_REQUIRED"),
    ("/dump/file/", "dump.file_get", "NO_RIGHTS_REQUIRED"),

    ("/ws/connections/", "ws.connections_summary", "NO_RIGHTS_REQUIRED"),

    ("/reload/", "reload.handle", "NO_RIGHTS_REQUIRED"),

    ("/bol/advertiser/v11/campaigns/", "advertiser_v11.campaigns", "NO_RIGHTS_REQUIRED"),
    ("/bol/advertiser/v11/campaigns/get/", "advertiser_v11.campaign", "NO_RIGHTS_REQUIRED"),
    ("/bol/advertiser/v11/ad-groups/", "advertiser_v11.ad_groups", "NO_RIGHTS_REQUIRED"),
    ("/bol/advertiser/v11/ad-groups/get/", "advertiser_v11.ad_group", "NO_RIGHTS_REQUIRED"),
    ("/bol/advertiser/v11/ads/", "advertiser_v11.ads", "NO_RIGHTS_REQUIRED"),
    ("/bol/advertiser/v11/ads/get/", "advertiser_v11.ad", "NO_RIGHTS_REQUIRED"),
    ("/bol/advertiser/v11/budgets/campaign/", "advertiser_v11.budgets_campaign", "NO_RIGHTS_REQUIRED"),
    ("/bol/advertiser/v11/budgets/account/", "advertiser_v11.budgets_account", "NO_RIGHTS_REQUIRED"),
    ("/bol/advertiser/v11/budgets/settings/", "advertiser_v11.budgets_settings", "NO_RIGHTS_REQUIRED"),
    ("/bol/advertiser/v11/budgets/free-credits/", "advertiser_v11.budgets_free_credits", "NO_RIGHTS_REQUIRED"),
    ("/bol/advertiser/v11/budgets/billing-advertisers/", "advertiser_v11.budgets_billing_advertisers", "NO_RIGHTS_REQUIRED"),
    ("/bol/advertiser/v11/insights/search-terms/", "advertiser_v11.insights_search_terms", "NO_RIGHTS_REQUIRED"),
    ("/bol/advertiser/v11/insights/categories/", "advertiser_v11.insights_categories", "NO_RIGHTS_REQUIRED"),
    ("/bol/advertiser/v11/insights/pdp/", "advertiser_v11.insights_pdp", "NO_RIGHTS_REQUIRED"),
    ("/bol/advertiser/v11/reporting/performance/", "advertiser_v11.reporting_performance", "NO_RIGHTS_REQUIRED"),
    ("/bol/advertiser/v11/reporting/target-page/", "advertiser_v11.reporting_target_page", "NO_RIGHTS_REQUIRED"),
    ("/bol/advertiser/v11/reporting/advertiser/", "advertiser_v11.reporting_advertiser", "NO_RIGHTS_REQUIRED"),
    ("/bol/advertiser/v11/reporting/search-terms/", "advertiser_v11.reporting_search_terms", "NO_RIGHTS_REQUIRED"),
    ("/bol/advertiser/v11/reporting/categories/", "advertiser_v11.reporting_categories", "NO_RIGHTS_REQUIRED"),
    ("/bol/advertiser/v11/bulk-report/", "advertiser_v11.bulk_report", "NO_RIGHTS_REQUIRED"),

    ("/bol/retailer/v10/offers/create/", "retailer_v10.offer_create", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/offers/get/", "retailer_v10.offer_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/offers/update/", "retailer_v10.offer_update", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/offers/delete/", "retailer_v10.offer_delete", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/offers/price/update/", "retailer_v10.offer_price_update", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/offers/stock/update/", "retailer_v10.offer_stock_update", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/offers/export/create/", "retailer_v10.offer_export_create", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/offers/export/get/", "retailer_v10.offer_export_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/offers/unpublished-report/create/", "retailer_v10.unpublished_offer_report_create", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/offers/unpublished-report/get/", "retailer_v10.unpublished_offer_report_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/orders/", "retailer_v10.orders_list", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/orders/get/", "retailer_v10.order_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/orders/cancel-item/", "retailer_v10.order_item_cancel", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/shipments/", "retailer_v10.shipments_list", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/shipments/get/", "retailer_v10.shipment_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/shipments/create/", "retailer_v10.shipment_create", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/shipments/invoice-requests/", "retailer_v10.invoice_requests_list", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/shipments/invoice/upload/", "retailer_v10.invoice_upload", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/shipments/delivery-options/", "retailer_v10.delivery_options_list", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/shipments/shipping-label/create/", "retailer_v10.shipping_label_create", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/shipments/shipping-label/get/", "retailer_v10.shipping_label_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/shipments/transport/add/", "retailer_v10.transport_add", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/returns/", "retailer_v10.returns_list", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/returns/get/", "retailer_v10.return_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/returns/create/", "retailer_v10.return_create", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/returns/handle-item/", "retailer_v10.return_item_handle", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/inventory/", "retailer_v10.inventory_list", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/replenishments/", "retailer_v10.replenishments_list", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/replenishments/get/", "retailer_v10.replenishment_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/replenishments/create/", "retailer_v10.replenishment_create", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/replenishments/update/", "retailer_v10.replenishment_update", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/replenishments/load-carrier-labels/", "retailer_v10.replenishment_load_carrier_labels", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/replenishments/pick-list/", "retailer_v10.replenishment_pick_list", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/replenishments/product-destinations/get/", "retailer_v10.product_destinations_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/replenishments/product-destinations/request/", "retailer_v10.product_destinations_request", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/products/catalog/get/", "retailer_v10.catalog_product_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/products/chunk-recommendations/", "retailer_v10.product_chunk_recommendations", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/products/content/create/", "retailer_v10.product_content_create", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/products/upload-report/get/", "retailer_v10.product_upload_report_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/products/categories/", "retailer_v10.product_categories_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/products/list/", "retailer_v10.product_list_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/products/list-filters/", "retailer_v10.product_list_filters_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/products/assets/get/", "retailer_v10.product_assets_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/products/competing-offers/get/", "retailer_v10.product_competing_offers_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/products/placement/get/", "retailer_v10.product_placement_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/products/price-star-boundaries/get/", "retailer_v10.product_price_star_boundaries_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/products/ids/get/", "retailer_v10.product_ids_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/products/ratings/get/", "retailer_v10.product_ratings_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/promotions/", "retailer_v10.promotions_list", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/promotions/get/", "retailer_v10.promotion_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/promotions/products/", "retailer_v10.promotion_products_list", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/commissions/get/", "retailer_v10.commission_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/commissions/bulk/", "retailer_v10.commissions_bulk_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/commissions/rates/", "retailer_v10.commission_rates_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/invoices/", "retailer_v10.invoices_list", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/invoices/get/", "retailer_v10.invoice_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/invoices/specification/", "retailer_v10.invoice_specification_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/insights/offer/", "retailer_v10.insights_offer_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/insights/performance/", "retailer_v10.insights_performance_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/insights/product-ranks/", "retailer_v10.insights_product_ranks_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/insights/sales-forecast/", "retailer_v10.insights_sales_forecast_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/insights/search-terms/", "retailer_v10.insights_search_terms_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/subscriptions/", "retailer_v10.subscriptions_list", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/subscriptions/get/", "retailer_v10.subscription_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/subscriptions/create/", "retailer_v10.subscription_create", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/subscriptions/update/", "retailer_v10.subscription_update", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/subscriptions/delete/", "retailer_v10.subscription_delete", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/subscriptions/keys/", "retailer_v10.subscription_keys_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/subscriptions/test/", "retailer_v10.subscription_test_send", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/retailer/info/", "retailer_v10.retailer_info_get", "NO_RIGHTS_REQUIRED"),
    ("/bol/retailer/v10/refurbished-offers/create/", "retailer_v10.refurbished_offer_create", "NO_RIGHTS_REQUIRED"),

    # RQ JSON endpoints for devs
    ("/rq/system/", "rq.system", "NO_RIGHTS_REQUIRED"),
    ("/rq/queues/", "rq.queues", "NO_RIGHTS_REQUIRED"),
    ("/rq/workers/", "rq.workers", "NO_RIGHTS_REQUIRED"),
    ("/rq/failed/aggregated/", "rq.failed_aggregated", "NO_RIGHTS_REQUIRED"),
    ("/rq/latency/", "rq.queue_latency", "NO_RIGHTS_REQUIRED"),
    ("/rq/scheduler/", "rq.scheduler", "NO_RIGHTS_REQUIRED"),

    ("/prompts/", "ai.prompts", "NO_RIGHTS_REQUIRED"),
    ("/prompts/create/", "ai.create_prompt", "NO_RIGHTS_REQUIRED"),
    ("/prompts/data/", "ai.prompts", "NO_RIGHTS_REQUIRED"),
    ("/prompts/<int>/", "ai.get_prompt", "NO_RIGHTS_REQUIRED", ["prompt_id"]),
    ("/prompts/<int>/cancel/", "ai.prompt_cancel", "NO_RIGHTS_REQUIRED", ["prompt_id"]),

    ("/grok/models/", "grok.list_models", "NO_RIGHTS_REQUIRED"),
    ("/grok/responses/", "grok.list_responses", "NO_RIGHTS_REQUIRED"),
    ("/grok/responses/create/", "grok.create_response", "NO_RIGHTS_REQUIRED"),
    ("/grok/responses/create_stream/", "grok.create_response_stream", "NO_RIGHTS_REQUIRED"),
    ("/grok/traces/", "grok.list_traces", "NO_RIGHTS_REQUIRED"),
    ("/grok/traces/<int>/", "grok.list_user_traces", "NO_RIGHTS_REQUIRED", ["user_id"]),

    ("/pools/", "pools.handle", "NO_RIGHTS_REQUIRED"),
    ("/pools/status/", "pools.get_status", "NO_RIGHTS_REQUIRED"),
    ("/pools/resize/", "pools.resize_pool", "NO_RIGHTS_REQUIRED"),

    ("/ai/nl-to-jsx/", "prompt_graph.nl_to_jsx", "NO_RIGHTS_REQUIRED"),
    ("/ai/parse-jsx/", "prompt_graph.parse_jsx", "NO_RIGHTS_REQUIRED"),
    ("/ai/run-graph/", "prompt_graph.run_graph", "NO_RIGHTS_REQUIRED"),

    ("/files/list/", "files.list_dir", "NO_RIGHTS_REQUIRED"),
    ("/files/meta/", "files.file_meta", "NO_RIGHTS_REQUIRED"),
    ("/files/content/", "files.file_content", "NO_RIGHTS_REQUIRED"),
    ("/files/tree/", "files.list_tree", "NO_RIGHTS_REQUIRED"),

    ("/api/v11/api-keys/", "api.create_api_key", "NO_RIGHTS_REQUIRED"),

    ("/sellers/", "sellers.list_sellers", "NO_RIGHTS_REQUIRED"),
    ("/sellers/<int>/", "sellers.get_seller", "NO_RIGHTS_REQUIRED", ["seller_id"]),

    ("/oauth-callback", "buttler_oauth.oauth_callback", "NO_RIGHTS_REQUIRED"),
]

dev_routes_regex = [
    (r"/AI/conversations/(?P<conversation_id>[^/]+)/messages/(?P<message_id>[^/]+)/edit/?", "ai.edit_conversation_message", "NO_RIGHTS_REQUIRED", ["conversation_id", "message_id"]),
    (r"/AI/conversations/(?P<conversation_id>[^/]+)/?", "ai.get_conversation_details_handler", "NO_RIGHTS_REQUIRED", ["conversation_id"]),
    (r"/postgres/(?P<schema>[a-zA-Z0-9_]+)/(?P<table>[a-zA-Z0-9_]+)/?", "postgres.table_contents", "NO_RIGHTS_REQUIRED", ["schema", "table"]),
    (r"/jobs/success/(?P<page>\d+)/?", "jobs.list", "NO_RIGHTS_REQUIRED", ["page"]),
    (r"/jobs/failed/(?P<page>\d+)/?", "jobs.list", "NO_RIGHTS_REQUIRED", ["page"]),
    (r"/jobs/details/(?P<job_id>[^/]+)/?", "jobs.details", "NO_RIGHTS_REQUIRED", ["job_id"]),
    (r"/jobs/restart/(?P<job_id>[^/]+)/?", "jobs.restart", "NO_RIGHTS_REQUIRED", ["job_id"]),
    (r"/jobs/clear-failed/?", "jobs.clear_failed", "NO_RIGHTS_REQUIRED"),

    # Grok API endpoints
    (r"/grok/models/(?P<model_id>[^/]+)/?", "grok.get_model", "NO_RIGHTS_REQUIRED", ["model_id"]),
    (r"/grok/responses/(?P<response_id>[^/]+)/?", "grok.get_response", "NO_RIGHTS_REQUIRED", ["response_id"]),
    (r"/grok/traces/(?P<user_id>[^/]+)/(?P<request_id>[^/]+)/?", "grok.get_trace", "NO_RIGHTS_REQUIRED", ["user_id", "request_id"]),

    # OpenAI models can have string IDs; support via regex route
    (r"/openai/models/(?P<model_id>[^/]+)/?", "openai.get_model", "NO_RIGHTS_REQUIRED", ["model_id"]),

    # RQ JSON regex endpoints for devs
    (r"/rq/queues/(?P<queue>[^/]+)/?", "rq.queue_details", "NO_RIGHTS_REQUIRED", ["queue"]),
    (r"/rq/workers/(?P<worker>[^/]+)/?", "rq.worker_details", "NO_RIGHTS_REQUIRED", ["worker"]),
    (r"/rq/jobs/(?P<status>queued|started|finished|failed|scheduled|all)/?", "rq.jobs_by_status", "NO_RIGHTS_REQUIRED", ["status"]),
    (r"/rq/jobs/details/(?P<job_id>[^/]+)/?", "rq.job_details", "NO_RIGHTS_REQUIRED", ["job_id"]),
    (r"/rq/jobs/result/(?P<job_id>[^/]+)/?", "rq.job_result", "NO_RIGHTS_REQUIRED", ["job_id"]),
    (r"/rq/jobs/results/(?P<job_id>[^/]+)/?", "rq.job_results", "NO_RIGHTS_REQUIRED", ["job_id"]),
    (r"/exec/(?P<request_id>[^/]+)/?", "exec.get_result_handler", "NO_RIGHTS_REQUIRED", ["request_id"]),
]

# --- Customer-Facing (Sellfiller) Routes ---
# Convention: Dutch URLs for customer-facing HTML pages.
# Handlers are always in English.
sellfiller_routes = [
    ("/", "home.handle", "NO_RIGHTS_REQUIRED"),
    ("/uitloggen/", "auth.logout", "NO_RIGHTS_REQUIRED"),
    ("/logout/", "auth.logout", "NO_RIGHTS_REQUIRED"),

    ("/home/", "home.handle", "NO_RIGHTS_REQUIRED"),
    ("/home/notifications/", "home.show_notifications", "NO_RIGHTS_REQUIRED"),
    ("/home/notifications/delete/", "home.delete_all_notifications", "NO_RIGHTS_REQUIRED"),
    ("/home/notifications/delete/<int>/", "home.delete_notifications", "NO_RIGHTS_REQUIRED", ["event_id"]),

    ("/voorraad/", "inventory.inventory.handle", "NO_RIGHTS_REQUIRED"),
    ("/welkom/", "welkom.handle", "NO_RIGHTS_REQUIRED"), #These should not be allowed for everyone, but we need more advanced initial redirecting for that
    ("/welkom/adressen/", "welkom.handle_adressen", "NO_RIGHTS_REQUIRED"),
    ("/welkom/adressen/delete/", "welkom.handle_address_delete", "NO_RIGHTS_REQUIRED"),
    ("/welkom/verkopers/", "welkom.handle_verkopers", "NO_RIGHTS_REQUIRED"),
    ("/welkom/verkopers/delete/", "welkom.handle_seller_delete", "NO_RIGHTS_REQUIRED"),
    ("/welkom/fulfillers/", "welkom.handle_fulfillers", "NO_RIGHTS_REQUIRED"),
    ("/welkom/fulfillers/delete/", "welkom.handle_fulfiller_delete", "NO_RIGHTS_REQUIRED"),
    ("/welkom/magazijnen/", "welkom.handle_magazijnen", "NO_RIGHTS_REQUIRED"),
    ("/welkom/magazijnen/delete/", "welkom.handle_warehouse_delete", "NO_RIGHTS_REQUIRED"),

    ("/help/", "help.handle", "NO_RIGHTS_REQUIRED"),

    ("/tickets/", "tickets.list_open", "NO_RIGHTS_REQUIRED"),
    ("/tickets/open/", "tickets.list_open", "NO_RIGHTS_REQUIRED"),
    ("/tickets/new/", "tickets.create", "NO_RIGHTS_REQUIRED"),
    ("/whatsapp/", "whatsapp.dashboard", "NO_RIGHTS_REQUIRED"),
    ("/whatsapp/conversations/", "whatsapp.conversations", "NO_RIGHTS_REQUIRED"),
    ("/whatsapp/messages/", "whatsapp.messages", "NO_RIGHTS_REQUIRED"),

    ("/inventory/", "inventory.inventory.handle", "NO_RIGHTS_REQUIRED"), # backwards compatibility

    ("/zoeken/", "home.global_search", "supply_rights"),
    ("/zoeken/producten/", "products.search", "supply_rights"),

    ("/bestellingen/", "orders.handle", "orders_rights"),
    ("/bestellingen/reserveringen/", "orders.get_picks", "orders_rights"),
    ("/bestellingen/reserveringen/gemist/", "orders.get_missed_picks", "orders_rights"),

    ("/backorders/", "fulfilment.backorders", "orders_rights"),
    ("/backorders/repicken/", "fulfilment.backorders_repick", "orders_rights"),

    ("/import4you/accounts/", "import4you.get_account_data", "supply_rights"),
    ("/import4you/accounts/nieuw/", "import4you.create_new_account", "supply_rights"),
    ("/import4you/", "import4you.get_stock_and_shipments", "supply_rights"),
    ("/import4you/voorraad/", "import4you.get_stock_data", "supply_rights"),
    ("/import4you/verzendingen/", "import4you.get_shipments_data", "supply_rights"),
    # ("/import4you/verzendingen/nieuw/", "import4you.create_i4y_replenishment", "supply_rights"),

    # ("/bol/verzendingen/", "bol.get_bol_shipments"),
    ("/bol/verzendingen/", "bol.get_bol_replenishments", "supply_rights"),
    ("/bol/verzendingen/sync/", "bol.replenishments.deletethisaftertesting", "supply_rights"),
    ("/bol/test/", "bol.add_test_bol_replenishment", "integration_rights"),
    ("/bol/verzendingen/nieuw/", "bol.create_bol_replenishment", "integration_rights"),
    ("/bol/kanalen/", "bol.get_channels", "integration_rights"),
    ("/bol/lvb-switch/offer/<int>/", "bol.switch_fulfilment_for_offer", "integration_rights", ["pk"]),
    ("/bol/lvb-switch/saleschannel/<int>/", "bol.switch_fulfilment_for_saleschannel", "integration_rights", ["pk"]),
    ("/bol/lvb-settings/offer/<int>/", "bol.change_lvb_settings_for_offer", "integration_rights", ["pk"]),
    ("/bol/fulfilment-type/offer/<int>/", "bol.change_fulfilment_type_for_offer", "integration_rights", ["pk"]),
    ("/bol/repricer/v2/", "bol.repricer.bol_repricer_v2_sellfiller", "integration_rights"),
    ("/bol/repricer/v2/products/", "bol.repricer.bol_repricer_v2_products", "integration_rights"),
    ("/bol/repricer/v2/session_content/", "bol.repricer.get_session_content", "integration_rights"),
    ("/bol/repricer/v2/create/", "bol.repricer.create_new_repricer_group", "integration_rights"),
    ("/bol/repricer/v2/page/", "bol.repricer.paginate_repricer_groups", "integration_rights"),
    ("/bol/repricer/v2/check_group/", "bol.repricer.toggle_repricergroup_selection", "integration_rights"),
    ("/bol/repricer/v2/remove/", "bol.repricer.remove_repricer_groups", "integration_rights"),
    ("/bol/repricer/v2/sort/", "bol.repricer.sort_repricer_groups", "integration_rights"),
    ("/bol/repricer/v2/<int>/", "bol.repricer.bol_repricer_v2_detail", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/products/page/", "bol.repricer.paginate_repricer_products", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/edit/", "bol.repricer.edit_repricer_group_value", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/toggle_lvb_pricing/", "bol.repricer.toggle_repricer_group_lvb_pricing", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/add_price_row/", "bol.repricer.add_price_row", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/remove_price_row/", "bol.repricer.remove_price_row", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/edit_price_type/", "bol.repricer.edit_price_type", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/edit_price_value/", "bol.repricer.edit_price_value", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/check/", "bol.repricer.toggle_repricer_selection", "integration_rights", ["repricer_group_id"]),
    # ("/bol/repricer/v2/<int>/toggle/", "bol.repricer.toggle_repricer_group_checked_value", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/toggle_active/", "bol.repricer.toggle_repricer_group_active", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/product_modal_initial/", "bol.repricer.get_initial_product_modal_content", "integration_rights", ["repricer_group_id"]),
    # ("/bol/repricer/v2/channel_priorities/move/", "bol.repricer.move_repricer_priority_channel"),
    # ("/bol/repricer/v2/channel_priorities/add/", "bol.repricer.add_repricer_priority_channel"),
    # ("/bol/repricer/v2/channel_priorities/remove/", "bol.repricer.remove_repricer_priority_channel"),
    ("/bol/repricer/v2/<int>/bulk_modal_initial/", "bol.repricer.get_initial_bulk_modal_content", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/modal_product_search/", "bol.repricer.modal_product_search", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/reprice/<int>/", "bol.repricer.reprice_product", "integration_rights", ["repricer_id"]),
    ("/bol/repricer/v2/<int>/products/check/", "bol.repricer.toggle_product_selection", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/products/add/", "bol.repricer.add_selected_products_to_repricer_group", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/products/remove/", "bol.repricer.remove_repricer_product", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/products/sort/", "bol.repricer.sort_repricer_products", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/products/search/", "bol.repricer.product_search", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/modal/", "bol.repricer.get_repricer_modal", "integration_rights", ["repricer_id"]),
    ("/bol/repricer/v2/<int>/edit_modal/", "bol.repricer.get_repricer_edit_modal", "integration_rights", ["repricer_id"]),
    ("/bol/repricer/v2/<int>/save_rules/", "bol.repricer.save_repricer_rules", "integration_rights", ["repricer_id"]),
    ("/bol/repricer/v2/<int>/reset/", "bol.repricer.reset_repricer_product_overrides", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/modal/update_rules/", "bol.repricer.handle_repricer_modal_rule_change", "integration_rights", ["repricer_id"]),
    ("/bol/repricer/v2/price/<int>/edit/", "bol.repricer.edit_repricer_value", "integration_rights", ["repricer_id"]),
    ("/bol/repricer/v2/price/<int>/toggle/", "bol.repricer.toggle_repricer_value", "integration_rights", ["repricer_id"]),
    ("/bol/repricer/v2/<int>/import_offers/", "bol.repricer.import_offers", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/export_offers/", "bol.repricer.export_offers", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/add_condition_row/", "bol.repricer.add_condition_row", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/remove_condition_row/", "bol.repricer.remove_condition_row", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/edit_condition_type/", "bol.repricer.edit_condition_type", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/edit_condition_value/", "bol.repricer.edit_condition_value", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/save_settings/", "bol.repricer.save_repricer_group_settings", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/cancel_settings/", "bol.repricer.cancel_repricer_group_settings", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/conflict_modal_page/", "bol.repricer.paginate_conflict_modal_rows", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/conflict_choice/", "bol.repricer.handle_conflict_choice", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/conflict_global_choice/", "bol.repricer.handle_global_conflict_choice", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/<int>/process_conflicts/", "bol.repricer.process_resolved_conflicts", "integration_rights", ["repricer_group_id"]),
    ("/bol/repricer/v2/history/", "bol.repricer.repricer_history", "integration_rights"),
    ("/bol/repricer/v2/history_search/", "bol.repricer.repricer_history_search", "integration_rights"),
    ("/bol/repricer/v2/history_filter/", "bol.repricer.repricer_history_filter", "integration_rights"),
    ("/bol/repricer/v2/history_page_size/", "bol.repricer.repricer_history_page_size", "integration_rights"),
    ("/bol/repricer/v2/history/page/", "bol.repricer.paginate_repricer_history", "integration_rights"),  # Main page pagination
    ("/bol/repricer/v2/detail/<int>/", "bol.repricer.bol_repricer_v2_detail_sellfiller", "integration_rights", ["repricer_id"]),
    ("/bol/repricer/v2/<int>/history/page/", "bol.repricer.paginate_repricer_history", "integration_rights", ["repricer_id"]),
    ("/bol/repricer/v2/<int>/event_logs/page/", "bol.repricer.paginate_repricer_event_logs", "integration_rights", ["repricer_id"]),
    ("/bol/repricer/v2/<int>/redis/set/", "bol.repricer.set_redis_key", "integration_rights", ["repricer_id"]),

    ("/nieuws/bol-storing-2025-01-15/", "bol.news.bol_storing_2025_01_15", "NO_RIGHTS_REQUIRED"),
    ("/oscar/<int>/docs/", "oscar.docs", "integration_rights", ["pk"]),

    ("/voorraad/levertijden/", "inventory.delivery_dates.handle", "integration_rights"),
    ("/voorraad/levertijden/<int>/formulier/", "inventory.delivery_dates.handle_add_delivery_time_formulier", "integration_rights", ["channel_id"]),
    ("/voorraad/levertijden/toevoegen/", "inventory.delivery_dates.handle_add_delivery_time", "integration_rights"),
    ("/voorraad/levertijden/<int>/verwijderen/", "inventory.delivery_dates.handle_delete_delivery_time", "integration_rights", ["delivery_time_id"]),
    ("/voorraad/levertijden/<int>/wijzigen/", "inventory.delivery_dates.handle_move_delivery_time", "integration_rights", ["delivery_time_id"]),
    ("/voorraad/levertijden/amazon-verversen/", "inventory.delivery_dates.handle_refresh_amazon_delivery_options", "integration_rights"),
    ("/voorraad/levertijden/amazon-voor-land/", "inventory.delivery_dates.handle_get_amazon_delivery_options_for_country", "integration_rights"),
    ("/voorraad/levertijden/kaufland-verversen/", "inventory.delivery_dates.handle_refresh_kaufland_delivery_options", "integration_rights"),


    ("/producten/consolidatie/", "products.consolidation", "NO_RIGHTS_REQUIRED"),
    ("/producten/consolidatie/bijwerken/", "products.update_consolidation", "NO_RIGHTS_REQUIRED"),

    ("/distributie/", "distribution.distribution", "supply_rights"),
    ("/distributie/search-products/", "distribution.bol.search_products", "supply_rights"),
    ("/distributie/create/", "distribution.distribution_create", "supply_rights"),
    ("/distributie/create-bol/", "distribution.distribution_create_bol", "supply_rights"),
    ("/distributie/create-bol/save-draft/", "distribution.bol.save_bol_draft_replenishment", "supply_rights"),
    ("/distributie/create-bol/split-select/", "distribution.distribution_create_bol_split_select", "supply_rights"),
    ("/distributie/create-bol/save-splits/", "distribution.bol.save_split_selections", "supply_rights"),
    ("/distributie/zendingen/", "distribution.distribution", "supply_rights"),
    ("/distributie/zendingen/<int>/", "distribution.distributie_single", "supply_rights", ["replenishment_id"]),
    ("/distributie/zendingen/<int>/voormelden/", "distribution.bol.distribution_pre_notify_bol", "supply_rights", ["replenishment_id"]),
    ("/distributie/zendingen/<int>/voormelden/save/", "distribution.bol.save_bol_pre_notification", "supply_rights", ["replenishment_id"]),
    ("/distributie/zendingen/<int>/voormelden/afleverdatum/", "distribution.bol.distribution_pre_notify_bol_delivery_date", "supply_rights", ["replenishment_id"]),
    ("/distributie/zendingen/<int>/voormelden/save2/", "distribution.bol.save_bol_pre_notification2", "supply_rights", ["replenishment_id"]),
    ("/distributie/zendingen/update-name/", "distribution.bol.handle_update_replenishment_name", "supply_rights"),
    ("/distributie/zendingen/<int>/bewerken/", "distribution.distribution_edit_bol", "supply_rights", ["replenishment_id"]),
    ("/distributie/zendingen/<int>/bewerken/save/", "distribution.save_bol_edit", "supply_rights", ["replenishment_id"]),
    ("/distributie/zendingen/<int>/annuleren/", "distribution.bol.cancel_bol_replenishment", "supply_rights", ["replenishment_id"]),
    ("/distributie/zendingen/<int>/verwijderen/", "distribution.delete_replenishment", "supply_rights", ["replenishment_id"]),
    ("/distributie/zendingen/<int>/retry-i4y/", "distribution.bol.retry_i4y_send_endpoint", "supply_rights", ["replenishment_id"]),
    ("/distributie/zendingen/<int>/picklist/", "distribution.replenishment_picklist", "supply_rights", ["replenishment_id"]),
    ("/distributie/zendingen/<int>/picklist/download/", "distribution.download_picklist.download_bol_picklist", "supply_rights", ["replenishment_id"]),
    ("/distributie/dashboard/", "distribution.distribution", "supply_rights"),
    ("/distributie/instellingen/", "distribution.distribution", "supply_rights"),
    ("/distributie/logs/", "distribution.distribution", "supply_rights"),
    ("/distributie/update-replenishment/", "distribution.bol.update_replenishment_status", "supply_rights"),
    ("/distributie/zendingen/check-replenishment-suggestions/", "distribution.manual_check_replenishment_suggestions", "supply_rights"),
    ("/distributie/destinaties/sync/", "distribution.manual_sync_destinations", "supply_rights"),

    # Mailer routes (Dutch URLs)
    ("/mailer/", "mailer.handle", "marketing_rights"),
    ("/marketing/", "mailer.handle", "marketing_rights"),  # Marketing alias for mailer
    ("/mailer/template/nieuw/", "mailer.template_new", "marketing_rights"),
    ("/mailer/template/aanmaken/", "mailer.template_create", "marketing_rights"),
    ("/mailer/template/<int>/opslaan/", "mailer.template_save", "marketing_rights", ["pk"]),
    ("/mailer/template/<int>/naam-wijzigen/", "mailer.template_change_name", "marketing_rights", ["pk"]),
    ("/mailer/template/<int>/titel-wijzigen/", "mailer.template_change_title", "marketing_rights", ["pk"]),
    ("/mailer/template/<int>/testmail/", "mailer.template_test_mail", "marketing_rights", ["pk"]),
    ("/mailer/regel/aanmaken/", "mailer.rule_create", "marketing_rights"),
    ("/mailer/regel/<int>/", "mailer.rule_detail", "marketing_rights", ["pk"]),
    ("/mailer/regel/<int>/wijzigen/", "mailer.rule_update", "marketing_rights", ["pk"]),
    ("/mailer/regel/<int>/herordenen/", "mailer.rule_reorder", "marketing_rights", ["pk"]),
    ("/mailer/regel/<int>/verwijderen/", "mailer.rule_delete", "marketing_rights", ["pk"]),
    ("/mailer/regel/<int>/kanalen/", "mailer.rule_channels_selection", "marketing_rights", ["pk"]),
    ("/mailer/regel/<int>/kanaal-toggle/", "mailer.rule_toggle_channel", "marketing_rights", ["pk"]),
    ("/mailer/regel/<int>/kanaal-exclude-toggle/", "mailer.rule_toggle_channel_exclude", "marketing_rights", ["pk"]),
    ("/mailer/regel/<int>/producten/", "mailer.rule_products_selection", "marketing_rights", ["pk"]),
    ("/mailer/regel/<int>/product-toggle/", "mailer.rule_toggle_product", "marketing_rights", ["pk"]),
    ("/mailer/regel/<int>/product-exclude-toggle/", "mailer.rule_toggle_product_exclude", "marketing_rights", ["pk"]),
    ("/mailer/regel/<int>/bijlagen/", "mailer.rule_attachments_selection", "marketing_rights", ["pk"]),
    ("/mailer/regel/<int>/bijlage-toggle/", "mailer.rule_toggle_attachment", "marketing_rights", ["pk"]),
    ("/mailer/regel/<int>/factuur-toggle/", "mailer.rule_toggle_attach_invoice", "marketing_rights", ["pk"]),
    ("/mailer/regel/<int>/landen/", "mailer.rule_countries_selection", "marketing_rights", ["pk"]),
    ("/mailer/regel/<int>/land-toggle/", "mailer.rule_toggle_country", "marketing_rights", ["pk"]),
    ("/mailer/regel/<int>/bijlage-upload/", "mailer.rule_attachment_upload", "marketing_rights", ["pk"]),
    ("/mailer/regel/<int>/bijlagen-count/", "mailer.rule_attachments_count", "marketing_rights", ["pk"]),
    ("/mailer/regel/<int>/kanalen-count/", "mailer.rule_channels_count", "marketing_rights", ["pk"]),
    ("/mailer/regel/<int>/producten-count/", "mailer.rule_products_count", "marketing_rights", ["pk"]),
    ("/mailer/regel/<int>/landen-count/", "mailer.rule_countries_count", "marketing_rights", ["pk"]),
    ("/mailer/template/<int>/", "mailer.template_detail", "marketing_rights", ["pk"]),
    ("/mailer/template/<int>/bestelling-html/", "mailer.template_order_html", "marketing_rights", ["pk"]),
    ("/mailer/template/<int>/retour-html/", "mailer.template_return_html", "marketing_rights", ["pk"]),
    ("/mailer/template/<int>/media/upload/", "mailer.template_media_upload", "marketing_rights", ["pk"]),
    ("/mailer/template/<int>/media/list/", "mailer.template_media_list", "marketing_rights", ["pk"]),
    ("/mailer/template/<int>/media/delete/", "mailer.template_media_delete", "marketing_rights", ["pk"]),
    ("/mailer/template/<int>/media/cleanup/", "mailer.template_media_cleanup", "marketing_rights", ["pk"]),
    ("/mailer/template/<int>/save/", "mailer.template_save", "marketing_rights", ["pk"]),
    ("/mailer/template/<int>/raw-content/", "mailer.template_raw_content", "marketing_rights", ["pk"]),
    ("/mailer/template/<int>/rendered-content/", "mailer.template_rendered_content", "marketing_rights", ["pk"]),
    ("/mailer/template/<int>/delete/", "mailer.template_delete", "marketing_rights", ["pk"]),
    ("/mailer/template/<int>/wijzigen/", "mailer.template_update", "marketing_rights", ["pk"]),
    ("/mailer/template/<int>/AI/", "mailer.template_update_ai", "marketing_rights", ["pk"]),
    ("/mailer/automatisch-mailen/", "mailer.toggle_auto_mail", "marketing_rights"),
    ("/mailer/regel/product-search/", "mailer.rule_product_search", "marketing_rights"),
    ("/mailer/regel/country-search/", "mailer.rule_country_search", "marketing_rights"),
    ("/mailer/regel/<int>/landen-bulk-toggle/", "mailer.rule_bulk_toggle_countries", "marketing_rights", ["pk"]),
    ("/mailer/add-email/", "mailer.add_email", "marketing_rights"),
    ("/mailer/handtekeningen/controleren/", "mailer.signatures_check", "marketing_rights"),

    ("/mcp/", "mcp.handle", "NO_RIGHTS_REQUIRED"),
    ("/installeren/", "installeren.handle", "NO_RIGHTS_REQUIRED"),

    # API Simulation Routes
    ("/api/v1/amazon/connect/", "api_sim.amazon_connect_page", "NO_RIGHTS_REQUIRED"),
    ("/api/v1/amazon/initiate/", "api_sim.initiate_amazon_flow", "NO_RIGHTS_REQUIRED"),
    ("/api/v1/amazon/callback/", "api_sim.amazon_oauth_callback", "NO_RIGHTS_REQUIRED"),

    # Return/Retour system routes
    ("/retouren/", "returns.handle", "orders_rights"),
    ("/retouren/instellingen/", "returns.settings", "orders_rights"),

    # Buy/Inkoop system routes
    ("/inkoop/", "buy.products.handle_products_page", "suggestions_rights"),
    ("/inkoop/products/", "buy.products.handle_products_page", "suggestions_rights"),
    ("/inkoop/snoozed/", "buy.products.handle_snoozed", "suggestions_rights"),
    ("/inkoop/snoozed/search/", "buy.products.handle_snoozed_search", "suggestions_rights"),
    ("/inkoop/suggestions/", "buy.suggestions.handle_active_suggestions", "suggestions_rights"),
    ("/inkoop/suggestions/add-product/", "buy.suggestions.add_product", "suggestions_rights"),
    ("/inkoop/ordered/", "buy.orders.handle_ordered", "suggestions_rights"),
    ("/inkoop/ordered/<int>/", "buy.orders.handle_ordered_detail", "suggestions_rights", ["pk"]),
    ("/inkoop/ordered/search/", "buy.orders.search_orders", "suggestions_rights"),
    ("/inkoop/ordered/export/xlsx/", "buy.orders.export_orders", "suggestions_rights"),
    ("/inkoop/ordered/save-name/", "buy.orders.save_order_name", "suggestions_rights"),
    ("/inkoop/ordered/complete/", "buy.orders.complete_order", "suggestions_rights"),
    ("/inkoop/ordered/update-arrived-quantity/", "buy.orders.update_arrived_quantity", "suggestions_rights"),
    ("/inkoop/ordered/update-ordered-date/", "buy.orders.update_ordered_date", "suggestions_rights"),
    ("/inkoop/ordered/delete-item/", "buy.orders.delete_order_item", "suggestions_rights"),
    ("/inkoop/ordered/create-advanced-supply/", "buy.orders.create_advanced_supply", "suggestions_rights"),
    ("/inkoop/ordered/update-unit-price/", "buy.orders.update_unit_price", "suggestions_rights"),
    ("/inkoop/ordered/item/<int>/update-expected/", "buy.orders.update_expected_quantity", "suggestions_rights", ["item_id"]),
    ("/inkoop/ordered/select-warehouse/", "buy.orders.select_warehouse_soi", "suggestions_rights"),
    ("/inkoop/ordered/select-seller/", "buy.orders.select_seller_soi", "suggestions_rights"),
    ("/inkoop/ordered/get-updated-supply/", "buy.orders.get_updated_supply_html", "suggestions_rights"),
    ("/inkoop/ordered/search-items/", "buy.orders.search_items", "suggestions_rights"),
    ("/inkoop/suppliers/", "buy.suppliers.handle", "suggestions_rights"),
    ("/inkoop/suppliers/add/", "buy.suppliers.add_supplier", "suggestions_rights"),
    ("/inkoop/suppliers/edit-time/", "buy.suppliers.edit_supplier_time", "suggestions_rights"),
    ("/inkoop/suppliers/delete/", "buy.suppliers.delete_supplier", "suggestions_rights"),
    ("/inkoop/completed/", "buy.orders.handle_completed", "suggestions_rights"),
    ("/inkoop/completed/set-order-back/", "buy.orders.set_order_back", "suggestions_rights"),
    ("/inkoop/manual/", "buy.manual.handle", "suggestions_rights"),
    ("/inkoop/manual/suppliers/", "buy.manual.handle_suppliers", "suggestions_rights"),
    ("/inkoop/manual/add-supplier-offer/", "buy.manual.handle_add_supplier_offer", "suggestions_rights"),
    ("/inkoop/manual/delete-supplier-offer/", "buy.manual.handle_delete_supplier_offer", "suggestions_rights"),
    ("/inkoop/manual/edit-amount/", "buy.manual.edit_amount", "suggestions_rights"),
    ("/inkoop/manual/suggest/", "buy.manual.manual_suggest", "suggestions_rights"),
    ("/inkoop/manual/reset-values/", "buy.manual.reset_values", "suggestions_rights"),
    ("/inkoop/manual/search/", "buy.manual.handle_search", "suggestions_rights"),
    ("/inkoop/products/search/", "buy.products.handle_search", "suggestions_rights"),
    ("/inkoop/products/manual-search/", "buy.products.handle_manual_search", "suggestions_rights"),
    ("/inkoop/products/set-sales-period/", "buy.products.set_sales_period", "suggestions_rights"),
    ("/inkoop/products/suppliers/", "buy.products.handle_suppliers", "suggestions_rights"),
    ("/inkoop/products/select/", "buy.products.select_product", "suggestions_rights"),
    ("/inkoop/products/select-all/", "buy.products.select_all", "suggestions_rights"),
    ("/inkoop/products/snooze/", "buy.products.snooze_product", "suggestions_rights"),
    ("/inkoop/products/unfit/", "buy.products.handle_unfit_search", "suggestions_rights"),
    ("/inkoop/settings/", "buy.suggestions.handle_settings", "suggestions_rights"),
    ("/inkoop/suppliers/select/", "buy.suppliers.select_supplier", "suggestions_rights"),
    ("/inkoop/products/set-snooze/", "buy.products.set_snooze", "suggestions_rights"),
    ("/inkoop/products/stop-snooze/", "buy.products.stop_snooze", "suggestions_rights"),
    ("/inkoop/products/set-moq-or-max/", "buy.products.set_moq_or_max", "suggestions_rights"),
    ("/inkoop/products/edit-supplier-price/", "buy.products.edit_supplier_price", "suggestions_rights"),
    ("/inkoop/suggestions/generate/", "buy.suggestions.generate_suggestions", "suggestions_rights"),
    ("/inkoop/suggestions/buy-all/", "buy.suggestions.buy_all_suggestions", "suggestions_rights"),
    ("/inkoop/suggestions/delete-all/", "buy.suggestions.delete_all_suggestions", "suggestions_rights"),
    ("/inkoop/suggestions/update-quantity/", "buy.suggestions.update_quantity", "suggestions_rights"),
    ("/inkoop/suggestions/update-delivery-date/", "buy.suggestions.update_delivery_date", "suggestions_rights"),
    ("/inkoop/suggestions/update-delivery-date-all/", "buy.suggestions.update_delivery_date_all", "suggestions_rights"),
    ("/inkoop/suggestions/update-supplier/", "buy.suggestions.update_supplier", "suggestions_rights"),
    ("/inkoop/suggestions/delete-item/", "buy.suggestions.delete_suggestion_item", "suggestions_rights"),
    ("/inkoop/suggestions/export/csv/", "buy.suggestions.export_suggestions", "suggestions_rights"),

    # Return Portal routes (Dutch URLs for customer-facing return portal)
    ("/instellingen/integraties/", "settings.integrations.handle", "NO_RIGHTS_REQUIRED"),
    ("/instellingen/set-printnode-printers/", "settings.integrations.set_printnode_printers", "NO_RIGHTS_REQUIRED"),
    ("/instellingen/abonnement/", "settings.subscription.handle", "NO_RIGHTS_REQUIRED"),
    ("/instellingen/algemeen/", "settings.general.vat_handle", "NO_RIGHTS_REQUIRED"),
    ("/instellingen/algemeen/BTW/", "settings.general.vat_handle", "change_roles"),
    ("/instellingen/algemeen/btw-groepen/", "settings.general.vat_groups_handle", "change_roles"),
    ("/instellingen/algemeen/btw-groepen/<int>/", "settings.general.vat_groups_detail", "change_roles", ["id"]),
    ("/instellingen/algemeen/maatwerk/", "settings.custom.handle", "change_roles"),
    ("/settings/subscription/setup-mollie/", "settings.subscription.handle_setup_mollie", "change_roles"),
    ("/settings/subscription/update-in-buttler/", "settings.subscription.handle_update_in_buttler", "change_roles"),
    ("/settings/set-redis-option/", "settings.common.set_redis_option", "change_roles"),
    ("/settings/integrations/get-printers-page/", "settings.integrations.get_printers_page", "change_roles"),
    ("/settings/general/set-country-vat/", "settings.general.set_country_vat", "change_roles"),
    ("/settings/general/set-country-vat-reverse/", "settings.general.set_country_vat_reverse", "change_roles"),

    # VAT Groups action endpoints (English)
    ("/settings/general/vat-groups/new/", "settings.general.create_vat_group", "NO_RIGHTS_REQUIRED"),
    ("/settings/general/vat-groups/<int>/delete/", "settings.general.delete_vat_group", "NO_RIGHTS_REQUIRED", ["id"]),
    ("/settings/general/vat-groups/<int>/rename/", "settings.general.edit_vat_group_name", "NO_RIGHTS_REQUIRED", ["id"]),
    ("/settings/general/vat-groups/<int>/rules/new/", "settings.general.new_vat_rule", "NO_RIGHTS_REQUIRED", ["id"]),
    ("/settings/general/vat-groups/<int>/rules/<int>/delete/", "settings.general.delete_vat_rule", "NO_RIGHTS_REQUIRED", ["id", "rule_id"]),
    ("/settings/general/vat-groups/<int>/rules/<int>/country/", "settings.general.edit_vatrule_country", "NO_RIGHTS_REQUIRED", ["id", "rule_id"]),
    ("/settings/general/vat-groups/<int>/rules/<int>/percentage/", "settings.general.edit_vatrule_percentage", "NO_RIGHTS_REQUIRED", ["id", "rule_id"]),
    ("/settings/custom/magento/add/", "settings.custom.magento_add", "NO_RIGHTS_REQUIRED"),
    ("/settings/custom/magento/remove/", "settings.custom.magento_remove", "NO_RIGHTS_REQUIRED"),
    ("/settings/custom/product-search/", "settings.custom.product_search", "NO_RIGHTS_REQUIRED"),
    ("/settings/custom/email-daily-parcels/", "settings.custom.email_daily_parcels", "NO_RIGHTS_REQUIRED"),
    ("/settings/custom/repick-all-open-orders/", "settings.custom.repick_all_open_orders", "NO_RIGHTS_REQUIRED"),

]

sellfiller_routes_regex = [
    (r"/bol/api/(.*)", "bol.api_pipe", "integration_rights"),
    # (r"/bol/repricer/v2/create/(?P<country>[a-z]{2})/", "bol.repricer.create_new_repricer_group", ["country"]),
    (r"/bol/repricer/v2/export_offers_template/(?P<file_type>[a-z]{3,4})/", "bol.repricer.export_offers_template", "integration_rights", ["file_type"]),


    # WhatsApp and Tickets regex routes
    (r"/whatsapp/conversation/(?P<conversation_id>[^/]+)/?$", "whatsapp.conversation_detail", "NO_RIGHTS_REQUIRED", ["conversation_id"]),
    (r"/whatsapp/media/(?P<file_path>.+)", "whatsapp.media_proxy", "NO_RIGHTS_REQUIRED", ["file_path"]),
    (r"/tickets/(?P<ticket_id>\d+)/?$", "tickets.detail", "NO_RIGHTS_REQUIRED", ["ticket_id"]),
    (r"/tickets/(?P<ticket_id>\d+)/messages/new/?$", "tickets.new_message", "NO_RIGHTS_REQUIRED", ["ticket_id"]),
    (r"/tickets/(?P<ticket_id>\d+)/close/?$", "tickets.close", "NO_RIGHTS_REQUIRED", ["ticket_id"]),
    (r"/tickets/(?P<ticket_id>\d+)/reopen/?$", "tickets.reopen", "NO_RIGHTS_REQUIRED", ["ticket_id"]),
]

authenticated_routes = [
    # SIU External API Routes
    ("/api/v1/sellers/", "api_handlers.sellers.handle_sellers", "NO_RIGHTS_REQUIRED"),
    ("/api/v1/sellers/<int>/", "api_handlers.sellers.handle_seller", "NO_RIGHTS_REQUIRED", ["seller_id"]),
    ("/api/v1/sellers/<int>/sales-channels/", "api_handlers.sales_channel_management.client_sales_channels", "NO_RIGHTS_REQUIRED", ["seller_id"]),
    ("/api/v1/sellers/<int>/redirect-urls/", "api_handlers.sales_channel_management.manage_user_redirect_urls", "NO_RIGHTS_REQUIRED", ["seller_id"]),
    ("/api/v1/sales-channel-meta/", "api_handlers.sales_channel_management.get_all_sales_channel_meta", "NO_RIGHTS_REQUIRED"),
    ("/api/v1/sales-channel-meta/<int>/", "api_handlers.sales_channel_management.get_sales_channel_meta_details", "NO_RIGHTS_REQUIRED", ["sales_channel_meta_id"]),
    ("/api/v1/sellers/<int>/orders/", "api_handlers.order_management.get_orders", "NO_RIGHTS_REQUIRED", ["seller_id"]),
    ("/api/v1/sellers/<int>/orders/new/", "api_handlers.order_management.create_order", "NO_RIGHTS_REQUIRED", ["seller_id"]),
    ("/api/v1/sellers/<int>/orders/<int>/", "api_handlers.order_management.get_order_by_id", "NO_RIGHTS_REQUIRED", ["seller_id", "order_id"]),
    ("/api/v1/sellers/<int>/orders/<int>/ship/", "api_handlers.order_management.ship_order", "NO_RIGHTS_REQUIRED", ["seller_id", "order_id"]),
    ("/api/v1/transporters/", "api_handlers.transporter_management.get_transporters", "NO_RIGHTS_REQUIRED"),
    ("/api/v1/pickuppoints/", "api_handlers.pickuppoints.get_pickup_points", "NO_RIGHTS_REQUIRED"),
    ("/api/v1/redirect-tester/", "api_handlers.sales_channel_management.redirect_tester", "NO_RIGHTS_REQUIRED"),
    ("/api/v1/api-keys/", "api_handlers.sellers.handle_create_api_key", "NO_RIGHTS_REQUIRED"),
    ("/api/v1/webhooks/", "api_handlers.siu_webhooks.manage_webhooks", "NO_RIGHTS_REQUIRED"),
    ("/api/v1/webhooks/<int>/", "api_handlers.siu_webhooks.delete_webhook", "NO_RIGHTS_REQUIRED", ["webhook_id"]),
    ("/api/v1/process-statuses/", "api_handlers.siu_webhooks.get_process_statuses_handler", "NO_RIGHTS_REQUIRED"),
    ("/api/v1/parcels/<uuid>/", "api_handlers.parcels.handle", "NO_RIGHTS_REQUIRED", ["uuid"]),

    # OAuth and settings routes
    ("/api/v1/sellers/<int>/sales-channels/<int>/oauth/initiate/", "api_handlers.sales_channel_management.initiate_oauth_connection", "integration_rights", ["seller_id", "sales_channel_meta_id"]),
    ("/api/v1/sellers/<int>/sales-channels/<int>/retest/", "api_handlers.sales_channel_management.retest_channel_connection", "integration_rights", ["seller_id", "channel_id"]),
    ("/api/v1/sellers/<int>/sales-channels/<int>/settings/", "api_handlers.sales_channel_management.update_channel_settings", "integration_rights", ["seller_id", "channel_id"]),
    ("/instellingen/api-sleutels/", "api_keys.handle", "NO_RIGHTS_REQUIRED"),
    ("/api/v1/api-keys/", "api_keys.handle_api_keys", "NO_RIGHTS_REQUIRED"),
    ("/user/", "user.info", "NO_RIGHTS_REQUIRED"),

    ("/kanalen/", "channels.handle", "integration_rights"),
    ("/kanalen/nieuw/", "channels_new.step_1", "integration_rights"),
    ("/kanalen/nieuw/<int>/", "channels_new.step_2", "integration_rights", ["seller_id"]),
    ("/kanalen/nieuw/<int>/sales-channels/<int>/", "channels_new.step_3", "integration_rights", ["seller_id", "sales_channel_meta_id"]),
    ("/kanalen/nieuw/<int>/sales-channels/<int>/save/", "channels_new.step_4", "integration_rights", ["seller_id", "sales_channel_meta_id"]),
]

authenticated_routes_regex = [
]


buttler_routes = [
    ("/usage/", "usage.handle", "NO_RIGHTS_REQUIRED"),
    ("/amperelabels/", "labelstats.handle_ampere_labels", "NO_RIGHTS_REQUIRED"),
    ("/intrapostlabels/", "labelstats.handle_intrapost_labels", "NO_RIGHTS_REQUIRED"),
    ("/montalabels/", "labelstats.handle_monta_labels", "NO_RIGHTS_REQUIRED"),
    ("/verzendsimpellabels/", "labelstats.handle_verzendsimpel_labels", "NO_RIGHTS_REQUIRED"),
    ("/update-client/", "update.handle", "NO_RIGHTS_REQUIRED"),
    ("/subscription/costs/", "subscription.get_costs", "NO_RIGHTS_REQUIRED"),
]

buttler_routes_regex = [
]

external_routes = [
    ("/", "home.handle", "NO_RIGHTS_REQUIRED"),
    ("/logout/", "auth.logout", "NO_RIGHTS_REQUIRED"),
    ("/uitloggen/", "auth.logout", "NO_RIGHTS_REQUIRED"),
    ("/bestellingen/", "orders.handle", "NO_RIGHTS_REQUIRED"),
    ("/bestellingen/<int>/", "orders.handle_single", "NO_RIGHTS_REQUIRED", ["pk"]),
    ("/bestellingen/nieuw/", "orders.handle_new", "NO_RIGHTS_REQUIRED"),
    ("/bestellingen/zoeken/", "orders.handle_search", "NO_RIGHTS_REQUIRED"),
    ("/bestellingen/<int>/verwijder/", "orders.handle_delete", "NO_RIGHTS_REQUIRED", ["pk"]),
    ("/bestellingen/<int>/producten/zoeken/", "orders.handle_search_products", "NO_RIGHTS_REQUIRED", ["pk"]),
    ("/bestellingen/<int>/producten/toevoegen/", "orders.handle_add_product", "NO_RIGHTS_REQUIRED", ["pk"]),
    ("/bestellingen/<int>/status/wijzigen/", "orders.handle_change_status", "NO_RIGHTS_REQUIRED", ["pk"]),
    ("/bestellingen/items/<int>/aantal/wijzigen/", "orders.handle_change_item_amount", "NO_RIGHTS_REQUIRED", ["pk"]),
    ("/bestellingen/<int>/wijzigen/", "orders.handle_edit", "NO_RIGHTS_REQUIRED", ["pk"]),

    # v0.0.1 tumfur api routes
    ("/products/", "products.handle", "NO_RIGHTS_REQUIRED"),
    ("/products/new/", "products.handle_new", "NO_RIGHTS_REQUIRED"),
    ("/orders/", "orders.get_orders_legacy_jad15", "NO_RIGHTS_REQUIRED"),
    ("/orders/new/", "orders.handle_new", "NO_RIGHTS_REQUIRED"),
    ("/postmark-webhook/", "postmark.webhook", "NO_RIGHTS_REQUIRED"),
    ("/report-results/", "reports.report_results", "NO_RIGHTS_REQUIRED"),
]

# --- Third-Party API Routes ---
# Convention: English URLs for third-party API integrations (JSON-based).
# Handlers are always in English.
thirdparty_routes = [
    ("/logout/", "auth.logout", "NO_RIGHTS_REQUIRED"),
    ("/uitloggen/", "auth.logout", "NO_RIGHTS_REQUIRED"),
    ("/import4you/stock/", "import4you.get_stock_data", "NO_RIGHTS_REQUIRED"),
]

# --- Public Routes ---
# Convention: Mixed. Dutch for user-facing pages (login, password reset),
# English for webhooks and machine-to-machine endpoints.
# Handlers are always in English.
public_routes = [
    # Core website pages
    ("/", "home.handle", "NO_RIGHTS_REQUIRED"),
    ("/inkomsten/", "website.prestaties", "NO_RIGHTS_REQUIRED"),
    ("/btwfacturen/", "website.facturen", "NO_RIGHTS_REQUIRED"),
    ("/email/", "website.email", "NO_RIGHTS_REQUIRED"),
    ("/voorraadbeheer/", "website.voorraadbeheer", "NO_RIGHTS_REQUIRED"),
    ("/orderverwerking/", "website.orderverwerking", "NO_RIGHTS_REQUIRED"),
    ("/inkopen/", "website.inkopen", "NO_RIGHTS_REQUIRED"),
    ("/inkoop/", "website.inkopen", "NO_RIGHTS_REQUIRED"),
    ("/prestaties/", "website.prestaties", "NO_RIGHTS_REQUIRED"),
    ("/functionaliteiten/", "website.functionaliteiten", "NO_RIGHTS_REQUIRED"),

    # What we do section
    ("/wat-doen-we/", "modules.wat_doen_we", "NO_RIGHTS_REQUIRED"),
    ("/wat-doen-we/voorraadbeheer-software/", "website.voorraadbeheer", "NO_RIGHTS_REQUIRED"),
    ("/wat-doen-we/orderverwerking-software/", "website.orderverwerking", "NO_RIGHTS_REQUIRED"),
    ("/wat-doen-we/prestaties-software/", "website.prestaties", "NO_RIGHTS_REQUIRED"),
    ("/wat-doen-we/inkoop-software/", "website.inkopen", "NO_RIGHTS_REQUIRED"),
    ("/wat-doen-we/factuurverwerking-software/", "website.facturen", "NO_RIGHTS_REQUIRED"),
    ("/wat-doen-we/email-marketing-software/", "website.email", "NO_RIGHTS_REQUIRED"),

    # Integration overview pages
    ("/partners/", "integrations.partners", "NO_RIGHTS_REQUIRED"),
    ("/marketplaces/", "integrations.marketplaces", "NO_RIGHTS_REQUIRED"),
    ("/webshops/", "integrations.webshops", "NO_RIGHTS_REQUIRED"),
    ("/vervoerders/", "integrations.vervoerders", "NO_RIGHTS_REQUIRED"),
    ("/koppelingen/", "integrations.koppelingen", "NO_RIGHTS_REQUIRED"), #This page isnt linked?
    ("/koppelingen/boekhoud/", "integrations.boekhoud", "NO_RIGHTS_REQUIRED"),
    ("/koppelingen/webshop/", "integrations.webshops", "NO_RIGHTS_REQUIRED"),
    ("/koppelingen/vervoerder/", "integrations.vervoerders", "NO_RIGHTS_REQUIRED"),
    ("/koppelingen/marketplace/", "integrations.marketplaces", "NO_RIGHTS_REQUIRED"),

    # Company pages
    ("/wie-zijn-we/", "company.wie_zijn_we", "NO_RIGHTS_REQUIRED"),
    ("/wie-zijn-we/missie-kernwaarden-visie/", "company.missie_kernwaarden_visie", "NO_RIGHTS_REQUIRED"),
    ("/wie-zijn-we/ons-team/", "company.ons_team", "NO_RIGHTS_REQUIRED"),
    ("/wie-zijn-we/onze-vacatures/", "company.onze_vacatures", "NO_RIGHTS_REQUIRED"),
    ("/wie-zijn-we/onze-vacatures/junior-medior-developer/", "company.vacature_junior_medior_developer", "NO_RIGHTS_REQUIRED"),

    # Sales and marketing pages
    ("/prijzen/", "sales.prijzen", "NO_RIGHTS_REQUIRED"),
    ("/prijzen-new/", "sales.prijzen", "NO_RIGHTS_REQUIRED"),
    ("/contact/", "sales.contact", "NO_RIGHTS_REQUIRED"),
    ("/roadmap/", "sales.roadmap", "NO_RIGHTS_REQUIRED"),
    ("/demo/", "sales.demo", "NO_RIGHTS_REQUIRED"),
    ("/about/", "modules.wat_doen_we", "NO_RIGHTS_REQUIRED"),
    ("/pushups/", "sales.pushups", "NO_RIGHTS_REQUIRED"),
    ("/banen/", "company.onze_vacatures", "NO_RIGHTS_REQUIRED"),

    # Technical/SEO routes
    ("/robots.txt", "special.robots_txt", "NO_RIGHTS_REQUIRED"),
    ("/sitemap.xml", "special.sitemap_xml", "NO_RIGHTS_REQUIRED"),

    # Authentication routes
    ("/login/", "auth.login", "NO_RIGHTS_REQUIRED"),
    ("/inloggen/", "auth.login", "NO_RIGHTS_REQUIRED"),
    ("/tweestapsverificatie/", "auth.two_factor_auth", "NO_RIGHTS_REQUIRED"),
    ("/wachtwoord-vergeten/", "auth.forgot_password", "NO_RIGHTS_REQUIRED"),
    ("/logout/", "auth.logout", "NO_RIGHTS_REQUIRED"),
    ("/uitloggen/", "auth.logout", "NO_RIGHTS_REQUIRED"),

    # API and webhook routes
    ("/goedgepickt/customprovider/", "goedgepickt.customprovider", "NO_RIGHTS_REQUIRED"),
    ("/picqer/customprovider/", "picqer.customprovider", "NO_RIGHTS_REQUIRED"),
    ("/picqer/customprovider/config-options/", "picqer.customprovider_config_options", "NO_RIGHTS_REQUIRED"),
    ("/import4you/test-sync/", "import4you.sync_stock", "NO_RIGHTS_REQUIRED"),
    ("/bol/webhook/<int>/", "bol.webhook", "NO_RIGHTS_REQUIRED", ["sales_channel_id"]),
    ("/import4you/shipment/update/", "import4you.test_validate_update_request", "NO_RIGHTS_REQUIRED"),

    # API Documentation routes
    ("/docs/", "docs.handle", "NO_RIGHTS_REQUIRED"),
    ("/docs/flow/", "docs.handle_flow", "NO_RIGHTS_REQUIRED"),
    ("/docs/llm/", "docs.llm_handle", "NO_RIGHTS_REQUIRED"),

    ("/mcp/", "mcp.handle", "NO_RIGHTS_REQUIRED"),
    ("/oauth/token/", "auth.oauth_token", "NO_RIGHTS_REQUIRED"),
    ("/oauth/authorize/", "auth.oauth_authorize", "NO_RIGHTS_REQUIRED"),

    ("/register/", "auth.register", "NO_RIGHTS_REQUIRED"),
    ("/.well-known/oauth-authorization-server", "auth.oauth_authorization_server", "NO_RIGHTS_REQUIRED"),
    ("/.well-known/oauth-protected-resource", "auth.oauth_protected_resource", "NO_RIGHTS_REQUIRED"),
    ("/api/v1/oauth/callback/", "oauth.oauth_callback", "NO_RIGHTS_REQUIRED"),
    ("/lightspeed/shipment_methods", "lightspeed.pickuppoints", "NO_RIGHTS_REQUIRED"),

    # Return Portal routes (public access)
]

if settings.JAD_ID == 2116:
    public_routes += [
        ("/retourportaal/", "retourportal.handle_home", "NO_RIGHTS_REQUIRED"),
        ("/retourportaal/producten/", "retourportal.handle_products", "NO_RIGHTS_REQUIRED"),
        ("/retourportaal/adres/", "retourportal.handle_address", "NO_RIGHTS_REQUIRED"),
        ("/retourportaal/verzending/", "retourportal.handle_shipping", "NO_RIGHTS_REQUIRED"),
        ("/retourportaal/succes/", "retourportal.handle_success", "NO_RIGHTS_REQUIRED"),
        ("/retourportaal/label/<int>/", "retourportal.handle_return_label_download", "NO_RIGHTS_REQUIRED", ["return_id"])
    ]

public_routes_regex = [
    (r"/wachtwoord-reset/(?P<uid>[^/]+)/(?P<token>[^/]+)/?$", "auth.password_reset", "NO_RIGHTS_REQUIRED", ["uid", "token"]),
    (r"/doorgelezen/v1/product/(?P<isbn>\d{10}|\d{13})/?$", "doorgelezen.product", "NO_RIGHTS_REQUIRED", ["isbn"]),
    (r"/doorgelezen/v1/stock/(?P<isbn>\d{10}|\d{13})/?$", "doorgelezen.stock", "NO_RIGHTS_REQUIRED", ["isbn"]),
    (r"/doorgelezen/v1/products/?$", "doorgelezen.products", "NO_RIGHTS_REQUIRED"),
    (r"/koppelingen/marketplaces/(?P<url_name>[a-zA-Z0-9_-]+)/?$", "integrations.marketplace_detail", "NO_RIGHTS_REQUIRED", ["url_name"]),
    (r"/koppelingen/webshops/(?P<url_name>[a-zA-Z0-9_-]+)/?$", "integrations.webshop_detail", "NO_RIGHTS_REQUIRED", ["url_name"]),
    (r"/koppelingen/vervoerders/(?P<url_name>[a-zA-Z0-9_-]+)/?$", "integrations.vervoerder_detail", "NO_RIGHTS_REQUIRED", ["url_name"]),

]

if settings.JAD_ID == 2116:
    public_routes_regex += [
        (r"/retourportaal/bestelling/(?P<order_id>[^/]+)/?", "retourportal.handle_order_lookup", "NO_RIGHTS_REQUIRED", ["order_id"]),
        (r"/retourportaal/retour/(?P<return_id>[^/]+)/?", "retourportal.handle_return_detail", "NO_RIGHTS_REQUIRED", ["return_id"]),
        (r"/retourportaal/retour/(?P<return_id>[^/]+)/bevestigen/?", "retourportal.handle_return_confirm", "NO_RIGHTS_REQUIRED", ["return_id"]),
    ]

ROUTE_HANDLERS = {}
REGEX_ROUTE_HANDLERS = {}

for path, handler, rights_required, *args in sellfiller_routes:
    if path not in ROUTE_HANDLERS:
        ROUTE_HANDLERS[path] = {}
    arg_names = args[0] if args else []
    ROUTE_HANDLERS[path]["sellfiller"] = (handler, arg_names, rights_required)

for path, handler, rights_required, *args in sellfiller_routes_regex:
    if path not in REGEX_ROUTE_HANDLERS:
        REGEX_ROUTE_HANDLERS[path] = {}
    arg_names = args[0] if args else []
    REGEX_ROUTE_HANDLERS[path]["sellfiller"] = (handler, arg_names, rights_required)

for path, handler, rights_required, *args in authenticated_routes:
    if path not in ROUTE_HANDLERS:
        ROUTE_HANDLERS[path] = {}
    arg_names = args[0] if args else []
    ROUTE_HANDLERS[path]["authenticated"] = (handler, arg_names, rights_required)

for path, handler, rights_required, *args in authenticated_routes_regex:
    if path not in REGEX_ROUTE_HANDLERS:
        REGEX_ROUTE_HANDLERS[path] = {}
    arg_names = args[0] if args else []
    REGEX_ROUTE_HANDLERS[path]["authenticated"] = (handler, arg_names, rights_required)

for path, handler, rights_required, *args in buttler_routes:
    if path not in ROUTE_HANDLERS:
        ROUTE_HANDLERS[path] = {}
    arg_names = args[0] if args else []
    ROUTE_HANDLERS[path]["buttler"] = (handler, arg_names, rights_required)

for path, handler, rights_required, *args in buttler_routes_regex:
    if path not in REGEX_ROUTE_HANDLERS:
        REGEX_ROUTE_HANDLERS[path] = {}
    arg_names = args[0] if args else []
    REGEX_ROUTE_HANDLERS[path]["buttler"] = (handler, arg_names, rights_required)

for path, handler, rights_required, *args in dev_routes:
    if path not in ROUTE_HANDLERS:
        ROUTE_HANDLERS[path] = {}
    arg_names = args[0] if args else []
    ROUTE_HANDLERS[path]["dev"] = (handler, arg_names, rights_required)

for path, handler, rights_required, *args in dev_routes_regex:
    if path not in REGEX_ROUTE_HANDLERS:
        REGEX_ROUTE_HANDLERS[path] = {}
    arg_names = args[0] if args else []
    REGEX_ROUTE_HANDLERS[path]["dev"] = (handler, arg_names, rights_required)

for path, handler, rights_required, *args in external_routes:
    if path not in ROUTE_HANDLERS:
        ROUTE_HANDLERS[path] = {}
    arg_names = args[0] if args else []
    ROUTE_HANDLERS[path]["external"] = (handler, arg_names, rights_required)

for path, handler, rights_required, *args in thirdparty_routes:
    if path not in ROUTE_HANDLERS:
        ROUTE_HANDLERS[path] = {}
    arg_names = args[0] if args else []
    ROUTE_HANDLERS[path]["thirdparty"] = (handler, arg_names, rights_required)

for path, handler, rights_required, *args in public_routes:
    if path not in ROUTE_HANDLERS:
        ROUTE_HANDLERS[path] = {}
    arg_names = args[0] if args else []
    ROUTE_HANDLERS[path]["public"] = (handler, arg_names, rights_required)


for path, handler, rights_required, *args in public_routes_regex:
    if path not in REGEX_ROUTE_HANDLERS:
        REGEX_ROUTE_HANDLERS[path] = {}
    arg_names = args[0] if args else []
    REGEX_ROUTE_HANDLERS[path]["public"] = (handler, arg_names, rights_required)


def get_handler_for_path(path: str, roles: set, subdomain: str | None = None, subdomain_role: str | None = None):
    """Get the appropriate handler for a path based on user roles.
    Returns the handler name for the highest priority role that has access.
    """

    original_path = path
    forced_role = None

    path_parts = path.strip("/").split("/")
    if len(path_parts) > 0 and path_parts[0] in ROLE_PRIORITIES:
        forced_role = path_parts[0]
        path = "/" + "/".join(path_parts[1:])
        logger.info(f"routing forced role {forced_role} from {original_path} to {path}")

    roles_to_match = ROLE_PRIORITIES
    if forced_role:
        roles_to_match = [forced_role]
    elif subdomain_role:
        roles_to_match = [subdomain_role] + [r for r in ROLE_PRIORITIES if r != subdomain_role]

    # --- Part 1: Try ROUTE_HANDLERS (exact match, <int> normalized) ---

    path_as_is = path
    if path == '/':
        path_alternative = path  # No alternative for root that's different
    elif path.endswith('/'):
        path_alternative = path.rstrip('/')
    else:
        path_alternative = path + '/'

    # Normalize these path variations for <int> and <uuid> placeholders
    norm_path_as_is = re.sub(r"/\d+/", "/<int>/", path_as_is)
    # UUID: 8-4-4-4-12 hex chars
    norm_path_as_is = re.sub(
        r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/",
        "/<uuid>/",
        norm_path_as_is,
    )
    norm_path_alternative = (
        re.sub(r"/\d+/", "/<int>/", path_alternative) if path_as_is != path_alternative else norm_path_as_is
    )
    norm_path_alternative = re.sub(
        r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/",
        "/<uuid>/",
        norm_path_alternative,
    )


    handlers_dict_for_key = None
    matched_route_key_for_digits = None

    if norm_path_as_is in ROUTE_HANDLERS:
        handlers_dict_for_key = ROUTE_HANDLERS[norm_path_as_is]
        matched_route_key_for_digits = norm_path_as_is
    elif path_as_is != path_alternative and norm_path_alternative in ROUTE_HANDLERS:
        handlers_dict_for_key = ROUTE_HANDLERS[norm_path_alternative]
        matched_route_key_for_digits = norm_path_alternative

    if handlers_dict_for_key:
        path_args = {}
        digits_for_args = []

        if matched_route_key_for_digits and "<int>" in matched_route_key_for_digits:
            digits_for_args = [int(d) for d in re.findall(r"/(\d+)(?=/|$)", path)]

        if forced_role or subdomain_role:
            if 'dev' in roles:
                roles = roles | {forced_role or subdomain_role}

        for role in roles_to_match:
            if role in roles and role in handlers_dict_for_key:
                handler_tuple = handlers_dict_for_key[role]
                handler, arg_names_from_def, rights_required = handler_tuple

                if arg_names_from_def and digits_for_args:
                    path_args = dict(zip(arg_names_from_def, digits_for_args))

                return role, handler, path_args, rights_required

        if 'public' in handlers_dict_for_key:
            handler_tuple = handlers_dict_for_key['public']
            handler, arg_names_from_def, rights_required = handler_tuple
            if arg_names_from_def and digits_for_args:
                path_args = dict(zip(arg_names_from_def, digits_for_args))
            return 'public', handler, path_args, rights_required

        return "ROLE_MISMATCH"


    # --- Part 2: Try REGEX_ROUTE_HANDLERS ---
    for regex_pattern, handlers_for_roles_in_regex in REGEX_ROUTE_HANDLERS.items():
        match_obj = re.match(regex_pattern, path_as_is)

        if not match_obj and path_as_is != path_alternative:
            match_obj = re.match(regex_pattern, path_alternative)

        if match_obj:
            path_args_from_regex = match_obj.groupdict()

            for role in roles_to_match:
                if role in roles and role in handlers_for_roles_in_regex:
                    handler_tuple = handlers_for_roles_in_regex[role]
                    handler, arg_names_from_def, rights_required = handler_tuple
                    return role, handler, path_args_from_regex, rights_required

            if 'public' in handlers_for_roles_in_regex:
                handler_tuple = handlers_for_roles_in_regex['public']
                handler, arg_names_from_def, rights_required = handler_tuple
                return 'public', handler, path_args_from_regex, rights_required

            return "ROLE_MISMATCH"

    return None
