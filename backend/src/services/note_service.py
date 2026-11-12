from fastapi import HTTPException
from ..models import BayesRun,SamplingNote
from ..constants.status import RunStatus
from ..utils.serialize import record
from .audit_service import log

def list_notes(db):return [record(n) for n in db.query(SamplingNote).order_by(SamplingNote.id.desc())]
def create_note(db,data,user):
    run=db.get(BayesRun,data.run_id)
    if not run or run.status!=RunStatus.COMPLETED or not run.result:raise HTTPException(409,"只能对已完成批次概率研究提交补种建议")
    row=SamplingNote(**data.model_dump(),owner=user.name,status="submitted")
    db.add(row);db.flush();log(db,user.email,"sampling.submit",row.id);db.commit();return record(row)
def review_note(db,nid,data,user):
    row=db.get(SamplingNote,nid)
    if not row:raise HTTPException(404,"补种建议不存在")
    if row.status!="submitted":raise HTTPException(409,"已审阅建议不可重复审批")
    row.status=data.status;row.reviewer=user.name;row.review_note=data.review_note
    log(db,user.email,"sampling."+data.status,row.id);db.commit();return record(row)
