from fastapi import APIRouter, HTTPException, Query
from app.db import conf_col
from app.schemas.conf import AddUrlRequest, AddParamsRequest, AddParamRequest, DeleteParamRequest, CreateConferenceRequest

router = APIRouter()


def _normalize_params(doc: dict) -> list[str]:
    """
    DB 문서가
      - params: ["a","b"] (신 스키마)
      - param: "a"        (구 스키마)
    둘 중 무엇이든 와도 항상 List[str]로 정규화.
    """
    ps = doc.get("params")
    if isinstance(ps, list):
        out = [str(x).strip() for x in ps if str(x).strip()]
        if out:
            return out

    p = doc.get("param")
    if isinstance(p, str) and p.strip():
        return [p.strip()]

    return []


def _find_by_param(param: str) -> dict | None:
    """
    param 하나로 조회:
    - 신 스키마: params 배열에 포함
    - 구 스키마: param 필드 일치
    """
    return conf_col.find_one(
        {"$or": [{"params": param}, {"param": param}]},
        {"_id": 0},
    )


@router.get("/kinds")
async def get_kinds():
    # distinct는 동기지만 작은 데이터라 ok
    kinds = conf_col.distinct("kind")
    return {"kinds": kinds}


@router.get("/by-kind/{kind}")
async def get_conferences_by_kind(kind: str):
    docs = list(conf_col.find({"kind": kind}, {"_id": 0}))
    if not docs:
        raise HTTPException(404, "No conferences for this kind")

    # 응답에서 params 보장(구 스키마 문서도 포함)
    for d in docs:
        d["params"] = _normalize_params(d)
        d.pop("param", None)  # 구 필드 숨기고 싶으면 유지, 필요하면 제거하지 말 것

    return docs


@router.get("/{param}")
async def get_conference(param: str):
    doc = _find_by_param(param)
    if not doc:
        raise HTTPException(404, "Conference not found")

    doc["params"] = _normalize_params(doc)
    doc.pop("param", None)
    return doc


@router.post("/{param}/urls")
async def add_conference_url(param: str, body: AddUrlRequest):
    # params 배열 / param 단일 모두 대응
    result = conf_col.update_one(
        {"$or": [{"params": param}, {"param": param}]},
        {"$addToSet": {"urls": body.url}},  # 중복 방지
    )

    if result.matched_count == 0:
        raise HTTPException(404, "Conference not found")

    return {"status": "added", "param": param, "url": body.url}


@router.delete("/{param}/urls")
async def delete_conference_url(param: str, url: str = Query(...)):
    result = conf_col.update_one(
        {"$or": [{"params": param}, {"param": param}]},
        {"$pull": {"urls": url}},
    )

    if result.matched_count == 0:
        raise HTTPException(404, "Conference not found")

    return {"status": "deleted", "param": param, "url": url}


@router.post("/")
async def create_conference(body: CreateConferenceRequest):
    data = body.dict()

    params = data.get("params")
    if params is None:
        # 혹시 스키마가 아직 param만 받는다면 여기서 변환
        p = data.get("param")
        if isinstance(p, str) and p.strip():
            params = [p.strip()]
        else:
            params = []
    if not isinstance(params, list) or not any(str(x).strip() for x in params):
        raise HTTPException(422, "params must be a non-empty list")

    params = [str(x).strip() for x in params if str(x).strip()]
    data["params"] = params
    data.pop("param", None)  # 구 필드는 저장하지 않음(원하면 제거)

    if conf_col.find_one({"$or": [{"params": {"$in": params}}]}):
        raise HTTPException(409, "one of params already exists")

    conf_col.insert_one(data)
    return {"status": "created", "params": params}


@router.delete("/{param}")
async def delete_conference(param: str):
    # params 배열 / param 단일 모두 대응해서 삭제
    result = conf_col.delete_one({"$or": [{"params": param}, {"param": param}]})
    if result.deleted_count == 0:
        raise HTTPException(404, "Conference not found")
    return {"status": "deleted", "param": param}


@router.post("/{param}/params")
async def add_params_batch(param: str, body: AddParamsRequest):
    new_params = [p.strip() for p in body.params if p.strip()]
    if not new_params:
        raise HTTPException(422, "params is empty")

    # 다른 문서에서 이미 쓰는 param이면 막기 (전체 검사)
    exists = conf_col.find_one(
        {"$or": [{"params": {"$in": new_params}}, {"param": {"$in": new_params}}]},
        {"_id": 1}
    )
    if exists:
        raise HTTPException(409, "one of params already exists in another conference")

    result = conf_col.update_one(
        {"$or": [{"params": param}, {"param": param}]},
        {"$addToSet": {"params": {"$each": new_params}}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Conference not found")

    conf_col.update_one({"$or": [{"params": param}, {"param": param}]}, {"$unset": {"param": ""}})
    return {"status": "added", "base": param, "params": new_params}



@router.delete("/{param}/params")
async def delete_param(param: str, body: DeleteParamRequest):
    del_param = body.param.strip()
    if not del_param:
        raise HTTPException(422, "param is empty")

    doc = conf_col.find_one({"$or": [{"params": param}, {"param": param}]}, {"_id": 0, "params": 1})
    if not doc:
        raise HTTPException(404, "Conference not found")

    params = doc.get("params") or []
    if del_param not in params:
        raise HTTPException(404, "param not in this conference")

    # params가 1개만 남아있는데 그걸 삭제하려 하면 막기
    if len(params) <= 1:
        raise HTTPException(400, "cannot delete the last param")

    result = conf_col.update_one(
        {"$or": [{"params": param}, {"param": param}]},
        {"$pull": {"params": del_param}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Conference not found")

    return {"status": "deleted", "base": param, "param": del_param}
