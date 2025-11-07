import asyncio
import logging
import time
import os
import json
import importlib
from datetime import datetime, timedelta, timezone as dt_timezone
import uuid
from server.pools import get_redis
from server.misc import get_next_run_ts
from siu_base.json import SiuJSONEncoder
from server.task_registry import get_cron_jobs
from server.sentry import sentry_sdk

logger = logging.getLogger(__name__)

QUEUE_KEYS_IN_PRIORITY = [
    "siu:job_queue:high",
    "siu:job_queue:default",
    "siu:job_queue:low",
    "siu:job_queue:mail",
]
WORKER_ID = str(os.getpid())

shutting_down = False

def initiate_shutdown():
    logger.info("Initiating shutdown...")
    global shutting_down
    shutting_down = True

async def enqueue_job(function_name, args=None, kwargs=None, queue_name="default", scheduled_for=None, job_type=None, dedupe_key=None):

    if queue_name not in [q.split(':')[-1] for q in QUEUE_KEYS_IN_PRIORITY]:
        raise ValueError(f"Invalid queue_name: {queue_name}. Must be one of {[q.split(':')[-1] for q in QUEUE_KEYS_IN_PRIORITY]}.")

    redis_conn = get_redis()
    actual_queue_key = f"siu:job_queue:{queue_name}"

    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}

    if scheduled_for is None:
        scheduled_timestamp = time.time()
    elif isinstance(scheduled_for, timedelta):
        scheduled_timestamp = time.time() + scheduled_for.total_seconds()
    elif isinstance(scheduled_for, datetime):
        if scheduled_for.tzinfo is None: # Must be timezone-aware
            raise ValueError("datetime object provided for scheduled_for must be timezone-aware.")
        # Convert to UTC and get timestamp
        scheduled_timestamp = scheduled_for.astimezone(dt_timezone.utc).timestamp()
    elif isinstance(scheduled_for, (int, float)): # Assume it's a Unix timestamp
        scheduled_timestamp = float(scheduled_for)
    else:
        raise TypeError(f"Invalid type for scheduled_for: {type(scheduled_for)}. Must be None, timedelta, datetime, int, or float.")

    job_payload = {
        "task": function_name,
        "args": args,
        "kwargs": kwargs,
        "job_type": job_type,
        "dedupe_key": dedupe_key,
    }
    job_id = uuid.uuid4().hex

    if dedupe_key:
        args_str = "_".join([str(arg) for arg in args])
        kwargs_str = "_".join([f"{k}:{v}" for k, v in kwargs.items()])
        job_id = "dedupe:"+str(dedupe_key)+":"+function_name+":"+args_str+":"+kwargs_str
    elif job_type:
        args_str = "_".join([str(arg) for arg in args])
        kwargs_str = "_".join([f"{k}:{v}" for k, v in kwargs.items()])
        job_id = job_type+":"+function_name+":"+args_str+":"+kwargs_str

    now_ts = time.time()
    delay_seconds = max(0, int(scheduled_timestamp - now_ts))
    payload_ttl = max(3600, delay_seconds + 3600)

    async with redis_conn.pipeline(transaction=True) as pipe:
        pipe.zadd(actual_queue_key, {"siu:job:"+job_id: scheduled_timestamp}, nx=True)
        pipe.set("siu:job:payload:"+job_id, json.dumps(job_payload, cls=SiuJSONEncoder), nx=True, ex=payload_ttl)
        await pipe.execute()


def enqueue_job_from_sync(function_name, args=None, kwargs=None, queue_name="default", scheduled_for=None, job_type=None, dedupe_key=None):
    from django_rq import get_connection
    if queue_name not in [q.split(':')[-1] for q in QUEUE_KEYS_IN_PRIORITY]:
        raise ValueError(f"Invalid queue_name: {queue_name}. Must be one of {[q.split(':')[-1] for q in QUEUE_KEYS_IN_PRIORITY]}.")

    redis_conn = get_connection()
    actual_queue_key = f"siu:job_queue:{queue_name}"

    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}

    if scheduled_for is None:
        scheduled_timestamp = time.time()
    elif isinstance(scheduled_for, timedelta):
        scheduled_timestamp = time.time() + scheduled_for.total_seconds()
    elif isinstance(scheduled_for, datetime):
        if scheduled_for.tzinfo is None: # Must be timezone-aware
            raise ValueError("datetime object provided for scheduled_for must be timezone-aware.")
        # Convert to UTC and get timestamp
        scheduled_timestamp = scheduled_for.astimezone(dt_timezone.utc).timestamp()
    elif isinstance(scheduled_for, (int, float)): # Assume it's a Unix timestamp
        scheduled_timestamp = float(scheduled_for)
    else:
        raise TypeError(f"Invalid type for scheduled_for: {type(scheduled_for)}. Must be None, timedelta, datetime, int, or float.")

    job_payload = {
        "task": function_name,
        "args": args,
        "kwargs": kwargs,
        "job_type": job_type,
        "dedupe_key": dedupe_key,
    }
    job_id = uuid.uuid4().hex

    if dedupe_key:
        args_str = "_".join([str(arg) for arg in args])
        kwargs_str = "_".join([f"{k}:{v}" for k, v in kwargs.items()])
        job_id = "dedupe:"+str(dedupe_key)+":"+function_name+":"+args_str+":"+kwargs_str
    elif job_type:
        args_str = "_".join([str(arg) for arg in args])
        kwargs_str = "_".join([f"{k}:{v}" for k, v in kwargs.items()])
        job_id = job_type+":"+function_name+":"+args_str+":"+kwargs_str

    now_ts = time.time()
    delay_seconds = max(0, int(scheduled_timestamp - now_ts))
    payload_ttl = max(3600, delay_seconds + 3600)

    with redis_conn.pipeline(transaction=True) as pipe:
        pipe.zadd(actual_queue_key, {"siu:job:"+job_id: scheduled_timestamp}, nx=True)
        pipe.set("siu:job:payload:"+job_id, json.dumps(job_payload, cls=SiuJSONEncoder), nx=True, ex=payload_ttl)
        pipe.execute()

async def worker_loop(worker_num):
    redis_conn = get_redis()
    queue_keys_to_check = QUEUE_KEYS_IN_PRIORITY

    logger.info(f"Worker {WORKER_ID}-{worker_num} started, monitoring queues: {[q.split(':')[-1] for q in queue_keys_to_check]}")

    while True:
        try:
            # BZPOPMIN will block until a job is available in one of the specified queues
            # or the timeout is reached. It checks keys in the order they are provided.
            popped_item = await redis_conn.bzpopmin(queue_keys_to_check, timeout=1)

            if popped_item:
                queue_name_bytes, job_id_bytes, scheduled_time = popped_item
                queue_name_complete = queue_name_bytes.decode()
                queue_name = queue_name_complete.split(":")[-1]
                current_time = time.time()
                if shutting_down:
                    new_ts = max(float(scheduled_time), current_time + 10)
                    await asyncio.shield(redis_conn.zadd(queue_name_complete, {job_id_bytes: new_ts}))
                    break
                if scheduled_time <= current_time:
                    await execute_job(job_id_bytes, queue_name)
                else:
                    wait_time = scheduled_time - current_time
                    sleep_duration = max(0, min(wait_time, 2))
                    try:
                        await asyncio.sleep(sleep_duration)
                        new_ts = scheduled_time if not shutting_down else max(float(scheduled_time), time.time() + 10)
                        await redis_conn.zadd(queue_name_complete, {job_id_bytes: new_ts})
                    except asyncio.CancelledError:
                        new_ts = max(float(scheduled_time), time.time() + 10)
                        await asyncio.shield(redis_conn.zadd(queue_name_complete, {job_id_bytes: new_ts}))
                        raise

        except asyncio.CancelledError:
            logger.info(f"Worker task {WORKER_ID}-{worker_num} cancelled.")
            break
        except Exception as e:
            logger.error(f"Worker task {WORKER_ID}-{worker_num} crashed with exception: {e}", exc_info=True)
            await asyncio.sleep(5)
            logger.info(f"Worker task {WORKER_ID}-{worker_num} restarting after error...")

async def execute_job(job_id_bytes, queue_name):
    start_time = time.time()
    redis_conn = get_redis()
    job_id = job_id_bytes.decode()
    job_id_parts = job_id.split(":")
    job_id = ":".join(job_id_parts[2:])
    job_payload_raw = await redis_conn.get("siu:job:payload:"+job_id)
    if job_payload_raw is None:
        logger.error(f"Worker {WORKER_ID} job payload missing for job_id: {job_id}. Job may have been processed already or payload creation failed.")
        return
    job_data = json.loads(job_payload_raw)
    job_task_path = job_data["task"]
    job_args = job_data.get("args", [])
    job_kwargs = job_data.get("kwargs", {})
    job_type = job_data.get("job_type")

    function_parts = job_task_path.split(".")
    module_path = ".".join(function_parts[:-1])
    function_name = function_parts[-1]

    try:
        if job_type in ("cron", "interval"):
            await get_redis().set(f"siu:scheduler:job_last_run_ts:{job_task_path}", str(time.time()))
        module = importlib.import_module(module_path)
        function_to_execute = getattr(module, function_name, None)

        if not function_to_execute:
            logger.error(f"Worker {WORKER_ID} could not find function for job: {job_task_path} in module {module_path}")
            return

        logger.debug(f"Worker {WORKER_ID} executing {job_task_path}")
        sentry_sdk.add_breadcrumb(
            category="rq_job",
            message="Job context",
            level="info",
            data={
                "job_id": job_id,
                "queue": queue_name,
                "task": job_task_path,
                "args": job_args,
                "kwargs": job_kwargs,
            },
        )
        await function_to_execute(*job_args, **job_kwargs)
        exec_time = time.time() - start_time
        logger.debug(f"Worker {WORKER_ID} completed {job_task_path} in {exec_time:.3f}s")
        await store_job_result(job_id, job_task_path, queue_name, job_args, job_kwargs)

        if job_type not in ("cron", "interval"):
            return

        cron_jobs_map = await get_cron_jobs()
        current_job_definition = cron_jobs_map.get(job_task_path)
        if not current_job_definition:
            logger.warning(f"Worker {WORKER_ID} scheduled job missing in registry: {job_task_path}")
            return
        next_run_ts, job_type = await get_next_run_ts(current_job_definition, job_task_path)
        await enqueue_job(job_task_path, job_args, job_kwargs, queue_name, next_run_ts, job_type)


    except asyncio.CancelledError:
        try:
            await asyncio.shield(store_job_result(job_id, job_task_path, queue_name, job_args, job_kwargs, "cancelled"))
        finally:
            try:
                await asyncio.shield(enqueue_job(job_task_path, job_args, job_kwargs, queue_name, time.time() + 10, job_type))
            finally:
                raise
    except ImportError as e:
        logger.error(f"Worker {WORKER_ID} could not import module for job: {job_task_path} (module: {module_path})", exc_info=True)
        await store_job_result(job_id, job_task_path, queue_name, job_args, job_kwargs, str(e))
    except AttributeError as e:
        logger.error(f"Worker {WORKER_ID} could not find function '{function_name}' in module for job: {job_task_path}", exc_info=True)
        await store_job_result(job_id, job_task_path, queue_name, job_args, job_kwargs, str(e))
    except Exception as job_exec_err:
        sentry_sdk.add_breadcrumb(
            category="rq_job",
            message="Job failed",
            level="error",
            data={
                "job_id": job_id,
                "queue": queue_name,
                "task": job_task_path,
            },
        )
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("worker.queue", queue_name)
            scope.set_tag("worker.id", WORKER_ID)
            scope.set_tag("job.func", function_name)
            scope.set_extra("job_id", job_id)
            scope.set_extra("args", job_args)
            scope.set_extra("kwargs", job_kwargs)
            sentry_sdk.capture_exception(job_exec_err)
            sentry_sdk.flush(2.0)
        logger.error(f"Worker {WORKER_ID} CRITICAL error executing job {job_task_path}: {job_exec_err}", exc_info=True)
        await store_job_result(job_id, job_task_path, queue_name, job_args, job_kwargs, str(job_exec_err))


async def store_job_result(job_id, task, queue, args, kwargs, error=None):
    status = "success" if error is None else "failed"
    redis = get_redis()
    now = time.time()
    entry = {
        "job_id": job_id,
        "task": task,
        "queue": queue,
        "args": args,
        "kwargs": kwargs,
        "status": status,
        "timestamp": now,
    }
    if error:
        entry["error"] = error

    key = f"siu:job_results:{status}"

    async with redis.pipeline(transaction=True) as pipe:
        await pipe.zadd(key, {job_id: now})
        await pipe.set(f"siu:job_result:{job_id}", json.dumps(entry, cls=SiuJSONEncoder), ex=3600)  # 1 hour
        if status == "success":
            await pipe.zremrangebyscore(key, 0, now - 1000)
        await pipe.delete(f"siu:job:payload:{job_id}")
        await pipe.execute()

async def get_jobs_counts():
    success_key = "siu:job_results:success"
    failed_key = "siu:job_results:failed"

    redis = get_redis()
    now = time.time()
    await redis.zremrangebyscore(success_key, 0, now - 1000)

    successes = await redis.zrangebyscore(success_key, now - 1000, "+inf", withscores=True)
    failed    = await redis.zrange(failed_key, 0, -1, withscores=True)

    return len(successes), len(failed)

async def get_jobs(status="success", page=1):
    redis = get_redis()
    key = f"siu:job_results:{status}"
    limit = 50
    offset = (max(1, int(page)) - 1) * limit

    job_ids_bytes = await redis.zrangebyscore(key, 0, "+inf", start=offset, num=limit)
    job_ids = [jid.decode() for jid in job_ids_bytes]

    raw_entries = await redis.mget([f"siu:job_result:{jid}" for jid in job_ids])

    jobs = []
    for raw, jid in zip(raw_entries, job_ids):
        if raw:
            job = json.loads(raw)
            jobs.append(job)

    return jobs

async def get_job(job_id):
    redis = get_redis()

    job_result = await redis.get(f"siu:job_result:{job_id}")
    if job_result is not None:
        return json.loads(job_result)

    return None

async def clear_failed_jobs():
    """Clear all failed job results from Redis."""
    redis = get_redis()
    failed_key = "siu:job_results:failed"

    # Get all failed job IDs
    failed_job_ids = await redis.zrange(failed_key, 0, -1)

    if not failed_job_ids:
        return 0

    # Delete individual job result entries
    job_result_keys = [f"siu:job_result:{jid.decode()}" for jid in failed_job_ids]
    await redis.delete(*job_result_keys)

    # Clear the failed jobs sorted set
    await redis.delete(failed_key)

    return len(failed_job_ids)