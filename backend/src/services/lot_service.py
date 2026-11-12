from ..models import SeedLot
from ..utils.serialize import record
from .study_service import get_study

def list_lots(db,sid):get_study(db,sid);return [record(l) for l in db.query(SeedLot).filter_by(study_id=sid).order_by(SeedLot.code)]
