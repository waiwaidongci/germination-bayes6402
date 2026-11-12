from sqlalchemy import Text,JSON,ForeignKey,Double,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from ..config.database import Base
from ..utils.clock import now
class GerminationStudy(Base):
    __tablename__="germination_studies"
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(unique=True)
    name:Mapped[str]
    description:Mapped[str]=mapped_column(Text)
    source:Mapped[str]
