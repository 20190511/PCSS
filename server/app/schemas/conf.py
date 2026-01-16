from pydantic import BaseModel
from typing import List

class AddUrlRequest(BaseModel):
    url: str
    
class CreateConferenceRequest(BaseModel):
    name: str
    param: str
    kind: str
    urls: List[str] = []

class AddParamRequest(BaseModel):
    param: str

class DeleteParamRequest(BaseModel):
    param: str