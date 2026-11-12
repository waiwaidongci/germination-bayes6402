from sqlalchemy import Text,JSON,ForeignKey,Double,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from ..config.database import Base
from ..utils.clock import now
class BayesRun(Base):
    __tablename__="bayes_runs"
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]
    study_id:Mapped[int]=mapped_column(ForeignKey("germination_studies.id"))
    threshold:Mapped[float]=mapped_column(Double)
    future_n:Mapped[int]
    input_snapshot:Mapped[dict]=mapped_column(JSON)
    status:Mapped[str]=mapped_column(default="queued")
    result:Mapped[dict]=mapped_column(JSON,default=dict)
    error:Mapped[str]=mapped_column(Text,default="")
    owner:Mapped[str]
    created_at:Mapped[str]=mapped_column(default=now)
