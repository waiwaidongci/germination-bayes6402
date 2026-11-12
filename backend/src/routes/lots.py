from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from ..config.database import get_db
from ..controllers.dependencies import current_user,roles
from ..constants.roles import Role
from ..schemas.lot import LotOutput
from ..services.lot_service import list_lots
router=APIRouter(tags=['lots'])
@router.get('/studies/{sid}/lots',response_model=list[LotOutput])
def index(sid:int,db:Session=Depends(get_db),user=Depends(current_user)):return list_lots(db,sid)
