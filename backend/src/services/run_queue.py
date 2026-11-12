"""Durable, idempotent run-queue helpers.

Redis is only a wake-up signal: every queued run is also tracked in
``bayes_runs.status`` + ``queued_at``, so a lost wake-up is re-enqueued by the
sweeper. Each claim rotates ``attempt_token``; status/result writes are
conditional on that token, so a duplicate hand-off or a late worker cannot
overwrite an accepted result.

Recovery has two triggers: a worker whose liveness key expired (died mid-fit)
and a per-run lease that went stale despite a live worker. A worker restart
re-emits every wake-up that may have been lost.
"""
import uuid
from datetime import datetime,timezone
from ..models import BayesRun
from ..constants.status import RunStatus,RunPhase
from ..utils.clock import now
from ..config.settings import QUEUE_STALE_SECONDS,RUNNING_STALE_SECONDS,MAX_RECOVERIES
from ..worker_lease import register_worker,worker_alive

JOBS_KEY="germination:jobs"

def _parse(ts):
    try:return datetime.fromisoformat(ts) if ts else None
    except ValueError:return None

def _age_seconds(ts):
    parsed=_parse(ts)
    if not parsed:return float("inf")
    return (datetime.now(timezone.utc)-parsed).total_seconds()

def phase_of(row):
    """Map persisted status and recovery counters onto the page lifecycle.

    An interrupted run shows as recovering/重算 both while it waits for its
    retry and while the retry runs, so waiting and recomputation stay distinct.
    """
    if row.status in (RunStatus.COMPLETED,RunStatus.FAILED):return RunPhase(row.status)
    if row.status==RunStatus.RECOVERING:return RunPhase.RECOVERING
    if row.recovery_count and row.recovery_count>0:return RunPhase.RECOVERING
    if row.status==RunStatus.RUNNING:return RunPhase.CALCULATING
    return RunPhase.WAITING

def enqueue(row,redis_client):
    """Emit a wake-up for a run whose queued state is already committed."""
    redis_client.rpush(JOBS_KEY,row.id)

def reset_for_queue(row):
    """Prepare a row for a fresh claim; recovery_count is set by expire()."""
    row.status=RunStatus.QUEUED
    row.queued_at=now()
    row.worker_id=""
    row.lease_at=""
    row.started_at=""
    row.attempt_token=""
    return row

def claim(db,run_id,worker_id,attempts=3):
    """Atomically claim one queued row, returning it with a fresh token or None.

    The conditional UPDATE means concurrent workers can never both win; the
    loser simply drops its wake-up. On SQLite a busy write lock can surface as
    OperationalError before the guard runs; retrying is safe because a claim
    that already committed would no longer match status='queued'.
    """
    from sqlalchemy.exc import OperationalError
    for _ in range(max(1,attempts)):
        try:return _claim_once(db,run_id,worker_id)
        except OperationalError:db.rollback()
    return None

def _claim_once(db,run_id,worker_id):
    token=uuid.uuid4().hex;stamp=now()
    rows=db.query(BayesRun).filter(
        BayesRun.id==run_id,BayesRun.status==RunStatus.QUEUED,
    ).update({
        BayesRun.status:RunStatus.RUNNING,BayesRun.attempt_token:token,
        BayesRun.worker_id:worker_id,BayesRun.lease_at:stamp,BayesRun.started_at:stamp,
        BayesRun.error:"",
    },synchronize_session=False)
    db.commit()
    if rows!=1:return None
    db.expire_all()
    row=db.get(BayesRun,run_id)
    if row.attempt_token!=token:return None
    row.attempt=(row.attempt or 0)+1
    db.commit()
    return row

def heartbeat(db,run_id,token):
    """Refresh the lease of an attempt that still owns the run."""
    rows=db.query(BayesRun).filter(
        BayesRun.id==run_id,BayesRun.attempt_token==token,BayesRun.status==RunStatus.RUNNING,
    ).update({BayesRun.lease_at:now()},synchronize_session=False)
    db.commit()
    return rows==1

def _owned(run_id,token):
    """Filter selecting the one attempt currently allowed to write."""
    return (BayesRun.id==run_id,BayesRun.attempt_token==token,BayesRun.status==RunStatus.RUNNING)

def complete(db,run_id,token,result):
    """Persist a result only if this attempt token still owns the run."""
    rows=db.query(BayesRun).filter(*_owned(run_id,token)).update({
        BayesRun.result:result,BayesRun.status:RunStatus.COMPLETED,
        BayesRun.finished_at:now(),BayesRun.error:"",BayesRun.lease_at:"",
    },synchronize_session=False)
    db.commit()
    return rows==1

def fail(db,run_id,token,error):
    rows=db.query(BayesRun).filter(*_owned(run_id,token)).update({
        BayesRun.status:RunStatus.FAILED,BayesRun.error:error,
        BayesRun.finished_at:now(),BayesRun.lease_at:"",
    },synchronize_session=False)
    db.commit()
    return rows==1

def expire(db,run_id,token):
    """Return an interrupted run to recovery, discarding any partial result.

    The input snapshot is untouched, so a retry uses the original counts,
    threshold and future_n. Repeated interruptions eventually fail the run
    instead of looping forever.
    """
    row=db.get(BayesRun,run_id,populate_existing=True)
    if not row or row.attempt_token!=token or row.status!=RunStatus.RUNNING:return None
    # Conditional updates so a concurrent claim/sweeper cannot resurrect or
    # double-expire the same attempt.
    current_recovery=row.recovery_count or 0
    if current_recovery+1>MAX_RECOVERIES:
        rows=db.query(BayesRun).filter(*_owned(run_id,token)).update({
            BayesRun.status:RunStatus.FAILED,BayesRun.error:"中断恢复次数超过上限，请重提",
            BayesRun.result:{},BayesRun.finished_at:now(),BayesRun.lease_at:"",
            BayesRun.attempt_token:"",BayesRun.worker_id:"",
            BayesRun.recovery_count:current_recovery+1,
        },synchronize_session=False)
    else:
        rows=db.query(BayesRun).filter(*_owned(run_id,token)).update({
            BayesRun.status:RunStatus.RECOVERING,BayesRun.error:"",BayesRun.result:{},
            BayesRun.lease_at:"",BayesRun.attempt_token:"",BayesRun.worker_id:"",
            BayesRun.recovery_count:current_recovery+1,
        },synchronize_session=False)
    db.commit()
    if rows!=1:return None
    db.expire_all()
    return db.get(BayesRun,run_id)

def requeue_recovering(db,run_id,redis_client):
    """Move a RECOVERING row back to queued and emit its wake-up."""
    row=db.get(BayesRun,run_id,populate_existing=True)
    if not row or row.status!=RunStatus.RECOVERING:return None
    reset_for_queue(row)
    db.commit()
    try:enqueue(row,redis_client)
    except Exception:
        # queued_at still lets a later sweep re-emit the wake-up.
        pass
    return row

def requeue_all_queued(db,redis_client):
    """Re-emit wake-ups for durably queued runs (worker restart)."""
    count=0
    for row in db.query(BayesRun).filter(BayesRun.status==RunStatus.QUEUED).all():
        try:enqueue(row,redis_client);count+=1
        except Exception:pass
    return count

def recover_at_startup(db,redis_client):
    """Re-emit lost wake-ups and recover runs no live worker owns.

    A run whose worker key already expired (or whose lease went stale) is
    returned to the queue immediately; a run another live worker is still
    computing is left untouched.
    """
    waiting=requeue_all_queued(db,redis_client)
    recovered=sweep(db,redis_client)
    return waiting,recovered

def sweep(db,redis_client):
    """Find orphaned runs: stale queued rows and abandoned running attempts.

    A running row is expired when its owning worker stopped publishing
    liveness, or when the per-run lease has gone stale despite a live worker.
    """
    handled=[]
    for row in db.query(BayesRun).filter(BayesRun.status==RunStatus.QUEUED).all():
        if not row.attempt_token and _age_seconds(row.queued_at or row.created_at)>QUEUE_STALE_SECONDS:
            # Stamp the retry so one orphan produces one wake-up per interval.
            row.queued_at=now()
            try:enqueue(row,redis_client);handled.append(("requeued",row.id))
            except Exception:pass
            db.commit()
    for row in db.query(BayesRun).filter(BayesRun.status==RunStatus.RUNNING).all():
        stale_lease=_age_seconds(row.lease_at or row.started_at)>RUNNING_STALE_SECONDS
        if worker_alive(redis_client,row.worker_id) and not stale_lease:continue
        expired=expire(db,row.id,row.attempt_token)
        if not expired:continue
        handled.append(("expired",row.id))
        if expired.status==RunStatus.RECOVERING:
            requeue_recovering(db,row.id,redis_client);handled.append(("requeued",row.id))
    return handled
