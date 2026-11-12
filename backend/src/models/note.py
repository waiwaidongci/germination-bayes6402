from sqlalchemy import Text,JSON,ForeignKey,Double,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from ..config.database import Base
from ..utils.clock import now
class SamplingNote(Base):
    __tablename__="sampling_notes"
    id:Mapped[int]=mapped_column(primary_key=True)
    run_id:Mapped[int]=mapped_column(ForeignKey("bayes_runs.id"))
    title:Mapped[str]
    interpretation:Mapped[str]=mapped_column(Text)
    proposal:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(default="submitted")
    owner:Mapped[str]
    reviewer:Mapped[str]=mapped_column(default="")
    review_note:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[str]=mapped_column(default=now)
