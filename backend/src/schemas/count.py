from pydantic import BaseModel,Field
class CountOutput(BaseModel):
    id:int
    lot_id:int
    lot_code:str
    lot_name:str
    n:int
    k:int
    raw_rate:float|None
    note:str
class CountAnnotation(BaseModel):
    note:str=Field(min_length=8,max_length=1500)
