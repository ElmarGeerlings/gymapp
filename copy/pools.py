redis = None
pg    = None
http  = None

pool_configs = {
    "postgres": {"min_size": 10, "max_size": 1000},
    "redis": {},
    "http": {}
}

def init(redis_pool=None, pg_pool=None, http_pool=None):
    global redis, pg, http
    if redis_pool is not None:
        redis = redis_pool
    if pg_pool is not None:
        pg = pg_pool
        # Track actual pool configuration
        if hasattr(pg_pool, 'get_min_size') and hasattr(pg_pool, 'get_max_size'):
            pool_configs["postgres"]["min_size"] = pg_pool.get_min_size()
            pool_configs["postgres"]["max_size"] = pg_pool.get_max_size()
    if http_pool is not None:
        http = http_pool

async def create_and_init_pools():
    import aiohttp
    import urllib.parse
    import os
    import logging
    from redis import asyncio as aioredis
    from siu_base.postgres.pool import get_async_pool, get_async_pool_with_config

    logger = logging.getLogger(__name__)

    try:
        from jad.settings import REDIS_URL, LOCAL_SERVER_INSTANCE_ID
    except ImportError:
        REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        LOCAL_SERVER_INSTANCE_ID = None

    redis_db = 1 if LOCAL_SERVER_INSTANCE_ID is None else (LOCAL_SERVER_INSTANCE_ID * 2) + 1

    parsed_redis = urllib.parse.urlparse(REDIS_URL)
    redis_host = parsed_redis.hostname or 'localhost'
    redis_port = parsed_redis.port or 6379
    redis_password = parsed_redis.password

    if redis_password:
        redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
    else:
        redis_url = f"redis://{redis_host}:{redis_port}/{redis_db}"

    redis_pool = await aioredis.from_url(
        redis_url,
        decode_responses=False
    )

    pg_pool = await get_async_pool_with_config(min_size=10, max_size=1000)

    http_session = aiohttp.ClientSession()

    init(
        redis_pool=redis_pool,
        pg_pool=pg_pool,
        http_pool=http_session
    )

    return redis_pool, pg_pool, http_session

async def close_pools():
    global redis, pg, http

    try:
        if redis:
            await redis.close()
    except:
        pass

    try:
        if pg:
            await pg.close()
    except:
        pass

    try:
        if http:
            await http.close()
    except:
        pass

def get_redis():
    if redis is None:
        raise RuntimeError("Redis pool has not been initialised yet")
    return redis

def get_pg():
    if pg is None:
        raise RuntimeError("Postgres pool has not been initialised yet")
    return pg

def get_http_session():
    if http is None:
        raise RuntimeError("HTTP pool has not been initialised yet")
    return http

def get_pool_configs():
    """Get current pool configuration tracking data."""
    return pool_configs.copy()

async def update_pool_config(pool_type, config):
    """Update pool configuration tracking."""
    if pool_type in pool_configs:
        pool_configs[pool_type].update(config)