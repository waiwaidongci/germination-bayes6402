from pydantic import BaseModel
class StudyOutput(BaseModel):
    id:int
    code:str
    name:str
    description:str
    source:str
    lot_count:int
    reading_count:int
    total_n:int
    total_k:int
    supported:bool
    reason:str
