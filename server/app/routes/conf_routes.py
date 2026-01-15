from fastapi import APIRouter, HTTPException
from app.db import conf_col
from app.schemas.conf import AddUrlRequest, CreateConferenceRequest

router = APIRouter()

@router.get("/kinds")
async def get_kinds():
    kinds = conf_col.distinct("kind")
    return {"kinds": kinds}

@router.get("/by-kind/{kind}")
async def get_conferences_by_kind(kind: str):
    docs = list(conf_col.find(
        {"kind": kind},
        {"_id": 0}
    ))

    if not docs:
        raise HTTPException(404, "No conferences for this kind")

    return docs

@router.get("/{param}")
async def get_conference(param: str):
    doc = conf_col.find_one({"param": param}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Conference not found")
    return doc

@router.post("/{param}/urls")
async def add_conference_url(param: str, body: AddUrlRequest):
    result = conf_col.update_one(
        {"param": param},
        {"$addToSet": {"urls": body.url}}  # 중복 방지
    )

    if result.matched_count == 0:
        raise HTTPException(404, "Conference not found")

    return {"status": "added", "url": body.url}

@router.delete("/{param}/urls")
async def delete_conference_url(param: str, url: str):
    result = conf_col.update_one(
        {"param": param},
        {"$pull": {"urls": url}}
    )

    if result.matched_count == 0:
        raise HTTPException(404, "Conference not found")

    return {"status": "deleted", "url": url}

@router.post("/")
async def create_conference(body: CreateConferenceRequest):
    if conf_col.find_one({"param": body.param}):
        raise HTTPException(409, "param already exists")

    conf_col.insert_one(body.dict())
    return {"status": "created", "param": body.param}

@router.delete("/{param}")
async def delete_conference(param: str):
    result = conf_col.delete_one({"param": param})
    if result.deleted_count == 0:
        raise HTTPException(404, "Conference not found")
    return {"status": "deleted", "param": param}
