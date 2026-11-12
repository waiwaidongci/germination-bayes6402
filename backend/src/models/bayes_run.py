from sqlalchemy import Text,JSON,ForeignKey,Double,Integer,UniqueConstraint
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
    # Interruption recovery / single-owner bookkeeping. Every claim gets a fresh
    # attempt_token; only the holder of the current token may write status/result.
    attempt:Mapped[int]=mapped_column(Integer,default=0)
    attempt_token:Mapped[str]=mapped_column(default="")
    worker_id:Mapped[str]=mapped_column(default="")
    lease_at:Mapped[str]=mapped_column(default="")
    queued_at:Mapped[str]=mapped_column(default="")
    recovery_count:Mapped[int]=mapped_column(Integer,default=0)
    started_at:Mapped[str]=mapped_column(default="")
    finished_at:Mapped[str]=mapped_column(default="")
