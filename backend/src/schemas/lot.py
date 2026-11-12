from pydantic import BaseModel
class LotOutput(BaseModel):
    id:int
    study_id:int
    code:str
    name:str
    origin:str
