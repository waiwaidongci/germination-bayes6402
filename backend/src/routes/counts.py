from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from ..config.database import get_db
from ..controllers.dependencies import current_user,roles
from ..constants.roles import Role
from ..schemas.count import CountOutput,CountAnnotation
from ..services.count_service import list_counts,annotate
router=APIRouter(tags=['counts'])
@router.get('/studies/{sid}/counts',response_model=list[CountOutput])
def index(sid:int,db:Session=Depends(get_db),user=Depends(current_user)):return list_counts(db,sid)
@router.patch('/counts/{cid}')
def update(cid:int,data:CountAnnotation,db:Session=Depends(get_db),user=Depends(roles(Role.ADMIN,Role.ANALYST))):return annotate(db,cid,data,user)
