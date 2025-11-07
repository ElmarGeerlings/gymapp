from server.pools import get_redis
from jad import settings

async def cron_job_tester():
    return "test"

async def cron_job_tester1():
    return "test1"

cron_jobs = None

async def init_cron_jobs():
    global cron_jobs
    cron_jobs = {
        "server.integrations.bol.repricer.check_bol_competing_products": {
            "cron_schedule": None,
            "interval_value": 1,
            "interval_unit": "hours",
            "queue": "default",
            "enabled": True,
            "args": [],
            "kwargs": {},
        },
        "server.integrations.bol.repricer.check_non_buybox_products": {
            "cron_schedule": None,
            "interval_value": 20,
            "interval_unit": "minutes",
            "queue": "default",
            "enabled": True,
            "args": [],
            "kwargs": {},
        },
        "server.integrations.bol.repricer.check_buybox_products": {
            "cron_schedule": "0 2 * * *",
            "interval_value": None,
            "interval_unit": None,
            "queue": "default",
            "enabled": True,
            "args": [],
            "kwargs": {},
        },
        "server.integrations.oscar.check_open_orders_status": {
            "cron_schedule": None,
            "interval_value": 30,
            "interval_unit": "seconds",
            "queue": "default",
            "enabled": False,
            "args": [],
            "kwargs": {},
        },
        "server.integrations.import4you.sync.sync_import4you_stock": {
            "cron_schedule": None,
            "interval_value": 15,
            "interval_unit": "minutes",
            "queue": "default",
            "enabled": True,
            "args": [],
            "kwargs": {},
        },
        "server.integrations.bol.webhooks.check_pending_process_statuses": {
            "cron_schedule": None,
            "interval_value": 5,
            "interval_unit": "seconds",
            "queue": "default",
            "enabled": True,
            "args": [],
            "kwargs": {},
        },
        "server.integrations.bol.webhooks.delete_old_process_statuses": {
            "cron_schedule": None,
            "interval_value": 24,
            "interval_unit": "hours",
            "queue": "default",
            "enabled": True,
            "args": [],
            "kwargs": {},
        },
        "cb.tasks.ado_stock_sync": {
            "cron_schedule": "0 4 * * *",  # Daily at 4:00 AM
            "interval_value": None,
            "interval_unit": None,
            "queue": "default",
            "enabled": True,
            "args": [],
            "kwargs": {},
        },
        "server.sellfiller.bol.replenishments.do_sync_replenishments": {
            "cron_schedule": None,
            "interval_value": 10,
            "interval_unit": "minutes",
            "queue": "default",
            "enabled": True,
            "args": [],
            "kwargs": {},
        },
        "server.integrations.import4you.shipments.automatic_generate_replenishment_suggestions": {
            "cron_schedule": "0 6 * * *",  # Daily 6:00 AM
            "interval_value": None,
            "interval_unit": None,
            "queue": "default",
            "enabled": True,
            "args": [],
            "kwargs": {},
        },
        "server.integrations.import4you.shipments.cleanup_old_replenishment_suggestions": {
            "cron_schedule": "0 5 * * *",  # Daily 5:00 AM
            "interval_value": None,
            "interval_unit": None,
            "queue": "default",
            "enabled": True,
            "args": [],
            "kwargs": {},
        },
        "server.integrations.booksinbelgium.stock.do_bib_stock_sync": {
            "cron_schedule": None,
            "interval_value": 15,
            "interval_unit": "minutes",
            "queue": "default",
            "enabled": False,  # Inactive until ready
            "args": [],
            "kwargs": {},
        },
        "server.integrations.booksinbelgium.offers.do_offer_sync": {
            "cron_schedule": None,
            "interval_value": 5,
            "interval_unit": "minutes",
            "queue": "default",
            "enabled": False,  # Inactive until ready
            "args": [],
            "kwargs": {},
        },
        "server.integrations.booksinbelgium.orders.do_order_sync": {
            "cron_schedule": None,
            "interval_value": 10,
            "interval_unit": "minutes",
            "queue": "default",
            "enabled": False,  # Inactive until ready
            "args": [],
            "kwargs": {},
        },
        "server.integrations.booksinbelgium.offers.do_nightly_reconciliation": {
            "cron_schedule": "0 3 * * *",  # Daily at 3:00 AM
            "interval_value": None,
            "interval_unit": None,
            "queue": "default",
            "enabled": False,  # Inactive until ready
            "args": [],
            "kwargs": {},
        },
        "server.integrations.bol.destinations.sync_all_bol_destinations": {
            "cron_schedule": None,
            "interval_value": 30,
            "interval_unit": "minutes",
            "queue": "default",
            "enabled": True,
            "args": [],
            "kwargs": {},
        },
        "server.integrations.kaufland.offers.delivery_promise.do_delivery_promise_sync": {
            "cron_schedule": None,
            "interval_value": 30,
            "interval_unit": "minutes",
            "queue": "default",
            "enabled": settings.JAD_ID == 370,
            "args": [],
            "kwargs": {},
        },
        "server.integrations.bol.offers.delivery_promise.do_delivery_promise_sync": {
            "cron_schedule": None,
            "interval_value": 30,
            "interval_unit": "minutes",
            "queue": "default",
            "enabled": settings.JAD_ID == 370,
            "args": [],
            "kwargs": {},
        },
        "server.integrations.amazon.delivery_promise.do_delivery_promise_sync": {
            "cron_schedule": None,
            "interval_value": 30,
            "interval_unit": "minutes",
            "queue": "default",
            "enabled": settings.JAD_ID == 370,
            "args": [],
            "kwargs": {},
        },
        "server.custom.jad365.warehouses.change_priorities": {
            "cron_schedule": "0 0,21 * * *",
            "interval_value": None,
            "interval_unit": None,
            "queue": "default",
            "enabled": settings.JAD_ID == 365,
            "args": [],
            "kwargs": {},
        },
        # "server.task_registry.cron_job_tester": {
        #     "cron_schedule": "* * * * *", #minute, hour, day of month (1-31), month (1=january), day of week (0=sunday)
        #     "interval_value": None,
        #     "interval_unit": None,
        #     "queue": "default",
        #     "enabled": True,
        #     "args": [],
        #     "kwargs": {},
        # },
        # "server.task_registry.cron_job_tester1": {
        #     "cron_schedule": None,
        #     "interval_value": 1,
        #     "interval_unit": "seconds", #seconds, minutes, hours, days, weeks
        #     "queue": "default",
        #     "enabled": True,
        #     "args": [],
        #     "kwargs": {},
        # }
    }

async def get_cron_jobs():
    if cron_jobs is None:
        await init_cron_jobs()
    return cron_jobs