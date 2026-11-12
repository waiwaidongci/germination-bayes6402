import csv,io
from fastapi import HTTPException
from ..models import BayesRun,SamplingNote
from ..utils.serialize import record
from ..constants.status import RunStatus
from .study_service import get_study,create_snapshot
from .analysis_service import prepare_snapshot
from .audit_service import log
from .run_queue import phase_of,reset_for_queue
_queue=None
def queue_client():
    """Lazily build the Redis wake-up channel (kept out of import time)."""
    global _queue
    if _queue is None:
        from redis import Redis
        from ..config.settings import REDIS_URL
        _queue=Redis.from_url(REDIS_URL,decode_responses=True)
    return _queue
def display(row):
    out=record(row)
    out.pop("attempt_token",None)
    out["phase"]=phase_of(row).value
    out["recoverable"]=row.status not in (RunStatus.COMPLETED,RunStatus.FAILED)
    out["recovered"]=bool(row.recovery_count)
    # Half-finished predictions never leave the worker: expose results only
    # for a completed run, never for queued/running/recovering/failed ones.
    if row.status!=RunStatus.COMPLETED:out["result"]={}
    return out
def list_runs(db):return [display(r) for r in db.query(BayesRun).order_by(BayesRun.id.desc())]
def get_run(db,rid):
    row=db.get(BayesRun,rid)
    if not row:raise HTTPException(404,"批次概率运行不存在")
    return row
def create_run(db,data,user):
    study=get_study(db,data.study_id);snapshot=create_snapshot(db,study)
    try:prepare_snapshot(snapshot)
    except ValueError as e:raise HTTPException(422,str(e))
    row=BayesRun(**data.model_dump(),input_snapshot=snapshot,owner=user.name,result={});reset_for_queue(row);db.add(row);db.flush();log(db,user.email,'bayes.enqueue',row.id);db.commit()
    try:queue_client().rpush('germination:jobs',row.id)
    except Exception:
        # The run stays durably queued; the sweeper re-emits the wake-up once
        # Redis is reachable again instead of failing the research.
        log(db,user.email,'bayes.enqueue.deferred',row.id);db.commit()
    return display(row)
def export_run(db,rid,kind='summary'):
    row=get_run(db,rid)
    if row.status!=RunStatus.COMPLETED or not row.result:raise HTTPException(403,'仅已完成批次研究可导出')
    if not db.query(SamplingNote).filter_by(run_id=rid,status='approved').first():raise HTTPException(403,'仅获批完成研究可导出')
    o=io.StringIO();w=csv.writer(o);r=row.result;fit=r['fit']
    if kind=='predictive':
        w.writerow(['lot','future_n','future_k','conditional_probability','fit_alpha','fit_beta','weak_identification','input_hash'])
        for x in r['lots']:
            for p in x['prediction']['pmf']:w.writerow([x['lot']['code'],row.future_n,p['k'],p['probability'],fit['alpha'],fit['beta'],fit['weak_identification'],r['input_hash']])
    else:
        w.writerow(['lot','n','k','raw_rate','post_alpha','post_beta','conditional_mean','conditional_q025','conditional_q975','Pr_p_gt_threshold','threshold','future_n','future_mean','future_variance','fit_alpha','fit_beta','weak_identification','fit_hash','input_hash'])
        for x in r['lots']:w.writerow([x['lot']['code'],x['count']['n'],x['count']['k'],x['raw_rate'],x['post_alpha'],x['post_beta'],x['mean'],x['lower'],x['upper'],x['prob_gt_threshold'],row.threshold,row.future_n,x['prediction']['mean'],x['prediction']['variance'],fit['alpha'],fit['beta'],fit['weak_identification'],r['fit_hash'],r['input_hash']])
    return o.getvalue()
