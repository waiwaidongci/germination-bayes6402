from fastapi import HTTPException
from ..models import GerminationStudy,SeedLot,LotCount
from ..utils.serialize import record
from .analysis_service import prepare_snapshot

def get_study(db,sid):
    row=db.get(GerminationStudy,sid)
    if not row:raise HTTPException(404,"萌发研究不存在")
    return row
def create_snapshot(db,study):
    lots=db.query(SeedLot).filter_by(study_id=study.id).order_by(SeedLot.code).all();ids=[l.id for l in lots]
    return {'study':record(study),'lots':[record(l) for l in lots],'counts':[record(c) for c in db.query(LotCount).filter(LotCount.lot_id.in_(ids)).order_by(LotCount.lot_id)]}
def list_studies(db):
    out=[]
    for s in db.query(GerminationStudy).order_by(GerminationStudy.code):
        snap=create_snapshot(db,s);supported=True;reason='计数完整，可多起点拟合；贴边将标弱识别'
        try:prepare_snapshot(snap)
        except ValueError as e:supported=False;reason=str(e)
        out.append({**record(s),'lot_count':len(snap['lots']),'reading_count':len(snap['counts']),'total_n':sum(c['n'] for c in snap['counts']),'total_k':sum(c['k'] for c in snap['counts']),'supported':supported,'reason':reason})
    return out
