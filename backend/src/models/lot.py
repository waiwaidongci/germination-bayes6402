from sqlalchemy import Text,JSON,ForeignKey,Double,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from ..config.database import Base
from ..utils.clock import now
class SeedLot(Base):
    __tablename__="seed_lots"
    id:Mapped[int]=mapped_column(primary_key=True)
    __table_args__=(UniqueConstraint("study_id","code"),)
    study_id:Mapped[int]=mapped_column(ForeignKey("germination_studies.id"))
    code:Mapped[str]
    name:Mapped[str]
    origin:Mapped[str]
