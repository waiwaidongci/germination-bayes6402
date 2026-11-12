"""Worker entry point.

A run is claimed with a fresh attempt token. Status/result writes are
conditional on that token, so a duplicate hand-off or a late worker can never
overwrite an accepted result. While the fit runs, the lease is refreshed from
the worker loop; a crashed worker leaves a stale lease that the sweeper expires
and re-queues bound to the original input snapshot.
"""
import json,os,threading,time,traceback,uuid
from pathlib import Path
from redis import Redis
from .config.database import Base,engine,SessionLocal
from .config.settings import REDIS_URL,ARTIFACT_DIR
from .services.run_queue import (
    JOBS_KEY,claim,complete,fail,heartbeat,register_worker,
    recover_at_startup,sweep,
)
from .services.analysis_service import analyze_germination
from .services.audit_service import log

# Refresh the run lease well before RUNNING_STALE_SECONDS expires it.
LEASE_INTERVAL=10

def run_fit(db_factory,run_id,token,calculator,snapshot,threshold,future_n,keepalive=None):
    """Run the fit on a helper thread while refreshing this run's lease.

    The calculator is CPU-bound, so a thread keeps the lease loop responsive.
    ``keepalive`` (optional) republishes the worker's own liveness key so a
    long fit is not mistaken for a dead worker. A lost token means a takeover
    already owns the run: stop refreshing and let the conditional write reject
    this attempt.
    """
    outcome={"result":None,"error":None}
    def target():
        try:outcome["result"]=calculator(snapshot,threshold,future_n)
        except Exception as exc:outcome["error"]=exc
    thread=threading.Thread(target=target,daemon=True)
    thread.start()
    while thread.is_alive():
        thread.join(LEASE_INTERVAL)
        if not thread.is_alive():break
        if keepalive:keepalive()
        with db_factory() as lease_db:
            if not heartbeat(lease_db,run_id,token):break
    thread.join()
    if outcome["error"]:raise outcome["error"]
    return outcome["result"]

def _write_artifact(run_id,result):
    """Persist the accepted result next to the worker; a failure here must not
    flip an already-committed completed run to failed."""
    try:
        Path(ARTIFACT_DIR).mkdir(parents=True,exist_ok=True)
        Path(f"{ARTIFACT_DIR}/run-{run_id}.json").write_text(json.dumps(result,ensure_ascii=False))
    except OSError:traceback.print_exc()

def process(db,run_id,worker_id,calculator=analyze_germination,db_factory=SessionLocal,keepalive=None):
    """Claim and execute a single wake-up, returning the claimed run or None."""
    run=claim(db,run_id,worker_id)
    if not run:return None
    token=run.attempt_token
    try:
        log(db,"worker","bayes.started",run.id)
        if run.recovery_count:log(db,"worker","bayes.recovered",run.id)
        db.commit()
        # The persisted snapshot, not live counts, is the retry contract.
        result=run_fit(db_factory,run.id,token,calculator,run.input_snapshot,run.threshold,run.future_n,keepalive)
        if complete(db,run.id,token,result):
            _write_artifact(run.id,result)
            log(db,"worker","bayes.completed",run.id)
        else:
            # A duplicate claim or takeover already owns the result.
            log(db,"worker","bayes.superseded",run.id)
        db.commit()
    except Exception as exc:
        traceback.print_exc()
        # Losing the token means a takeover already owns the run: a late
        # failure must not rewrite its status or error.
        if fail(db,run.id,token,str(exc)):log(db,"worker","bayes.failed",run.id)
        else:log(db,"worker","bayes.superseded",run.id)
        db.commit()
    return run

def recover_after_restart(db,redis_client):
    """Re-emit waiting wake-ups and retry work a dead worker left running."""
    return recover_at_startup(db,redis_client)

def main():
    Base.metadata.create_all(engine)
    Path(ARTIFACT_DIR).mkdir(parents=True,exist_ok=True)
    worker_id=f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
    redis_client=Redis.from_url(REDIS_URL,decode_responses=True)
    def keepalive():
        Path(f"{ARTIFACT_DIR}/heartbeat").write_text(str(time.time()))
        register_worker(redis_client,worker_id)
    keepalive()
    with SessionLocal() as db:recover_after_restart(db,redis_client)
    while True:
        keepalive()
        try:
            with SessionLocal() as db:
                sweep(db,redis_client)
                job=redis_client.blpop(JOBS_KEY,timeout=1)
                if job:process(db,int(job[1]),worker_id,keepalive=keepalive)
        except Exception:traceback.print_exc();time.sleep(1)

if __name__=="__main__":main()
