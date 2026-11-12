from pydantic import BaseModel,Field,ConfigDict
class RunInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    name:str=Field(min_length=2,max_length=160)
    study_id:int=Field(gt=0,strict=True)
    threshold:float=Field(default=.7,gt=0,lt=1,allow_inf_nan=False,strict=True)
    future_n:int=Field(default=50,ge=1,le=200,strict=True)
