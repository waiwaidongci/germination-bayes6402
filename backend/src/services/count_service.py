from fastapi import HTTPException
from ..models import SeedLot,LotCount
from ..utils.serialize import record
from .study_service import get_study
from .audit_service import log

def list_counts(db,sid):
    get_study(db,sid);rows=db.query(LotCount,SeedLot).join(SeedLot,LotCount.lot_id==SeedLot.id).filter(SeedLot.study_id==sid).order_by(SeedLot.code).all()
    return [{**record(c),'lot_code':l.code,'lot_name':l.name,'raw_rate':c.k/c.n if c.n>0 else None} for c,l in rows]
def annotate(db,cid,data,user):
    row=db.get(LotCount,cid)
    if not row:raise HTTPException(404,"批次计数不存在")
    row.note=data.note;log(db,user.email,'count.annotate',cid);db.commit();return record(row)
