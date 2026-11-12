from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from ..config.database import get_db
from ..controllers.dependencies import current_user
from ..schemas.study import StudyOutput
from ..services.study_service import list_studies
router=APIRouter(prefix='/studies',tags=['studies'])
@router.get('',response_model=list[StudyOutput])
def index(db:Session=Depends(get_db),user=Depends(current_user)):return list_studies(db)
