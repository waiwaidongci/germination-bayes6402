"""Shared worker-liveness helpers (kept apart to avoid circular imports)."""
from .utils.clock import now
WORKER_TTL=15

def worker_key(worker_id):
    return f"germination:worker:{worker_id}"

def register_worker(redis_client,worker_id):
    """Publish liveness with a short TTL, refreshed by the worker loop."""
    redis_client.setex(worker_key(worker_id),WORKER_TTL,now())

def worker_alive(redis_client,worker_id):
    if not worker_id:return False
    try:return bool(redis_client.exists(worker_key(worker_id)))
    except Exception:return False
