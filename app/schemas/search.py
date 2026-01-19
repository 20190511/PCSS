from pydantic import BaseModel
from typing import List
from pydantic import BaseModel

class SearchRequest(BaseModel):
    options: List[int]
    uncertainty: float
    startyear: int
    endyear: int
    selectedConferences: List[str]
    countOption: bool = False