from pydantic import BaseModel
from typing import List, Optional, Tuple
from pydantic import BaseModel

class SearchRequest(BaseModel):
    option: List[int]
    uncertainty: float
    startyear: int
    endyear: int
    selectedConferences: List[str]
    countOption: bool = False


class SearchResponse(BaseModel):
    result_path: str


class AuthorStatsRequest(BaseModel):
    target_author: str
    include_papers: bool = False

    # 선택: 필터가 필요하면 추가
    conf_list: Optional[List[str]] = None
    startyear: Optional[int] = None
    endyear: Optional[int] = None

class AuthorStatsResponse(BaseModel):
    stats: Tuple[int, int, int, int]
    total: int
    papers: Optional[list] = None
