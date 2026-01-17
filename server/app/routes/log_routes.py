# app/routes/log_routes.py

from __future__ import annotations

from fastapi import APIRouter, Query
from datetime import datetime, timezone
from typing import Optional, Literal, Any, Dict, List
from app.db import log_col

router = APIRouter()

# -----------------------------
# Helpers
# -----------------------------

def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    """
    ISO8601 string -> datetime(UTC)
    Accepts:
      - 2026-01-17T15:32:28Z
      - 2026-01-17T15:32:28.521Z
      - 2026-01-17T15:32:28+00:00
    """
    if not s:
        return None
    ss = s.strip()
    if ss.endswith("Z"):
        ss = ss[:-1] + "+00:00"
    dt = datetime.fromisoformat(ss)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def _match_time(start: Optional[datetime], end: Optional[datetime]) -> Dict[str, Any]:
    cond: Dict[str, Any] = {}
    if start:
        cond["$gte"] = start
    if end:
        cond["$lt"] = end
    return {"ts": cond} if cond else {}

def _base_match(
    start: Optional[datetime],
    end: Optional[datetime],
    type_: Optional[str],
    path: Optional[str],
    ip: Optional[str],
) -> Dict[str, Any]:
    m: Dict[str, Any] = {}
    m.update(_match_time(start, end))
    if type_:
        m["type"] = type_
    if path:
        m["path"] = path
    if ip:
        m["ip"] = ip
    return m

def _bucket_date_trunc_unit(granularity: str) -> str:
    # MongoDB $dateTrunc unit values: "minute", "hour", "day", "week", "month"
    allowed = {"minute", "hour", "day", "week", "month"}
    if granularity not in allowed:
        return "hour"
    return granularity

def _safe_int(x: Optional[int], default: int) -> int:
    if x is None:
        return default
    return x

# -----------------------------
# 1) 전체 요약: counts / uniques / breakdowns
# -----------------------------

@router.get("/summary")
async def logs_summary(
    start: Optional[str] = Query(None, description="ISO8601 start (UTC). e.g. 2026-01-01T00:00:00Z"),
    end: Optional[str] = Query(None, description="ISO8601 end (UTC). e.g. 2026-02-01T00:00:00Z"),
    type: Optional[str] = Query(None, description="Filter by log.type (homepage, search_start, http, ...)"),
    top_n: int = Query(10, ge=1, le=100),
):
    """
    응답 예시:
    {
      "range": {"start": "2026-01-01T00:00:00+00:00", "end": "2026-02-01T00:00:00+00:00"},
      "filters": {"type": null},
      "total_events": 12345,
      "unique_ips": 678,
      "first_ts": "2026-01-01T00:01:02.123+00:00",
      "last_ts":  "2026-01-31T23:59:59.999+00:00",
      "by_type": [
        {"type": "homepage", "count": 3000},
        {"type": "search_start", "count": 1200}
      ],
      "by_method": [
        {"method": "GET", "count": 8000},
        {"method": "POST", "count": 4345}
      ],
      "top_paths": [
        {"path": "/", "count": 3000},
        {"path": "/api/search/start", "count": 1200}
      ],
      "top_referrers": [
        {"referer": "https://pcss.r-e.kr/", "count": 900},
        {"referer": "", "count": 700}
      ],
      "top_user_agents": [
        {"user_agent": "Mozilla/5.0 ...", "count": 2500}
      ]
    }
    """
    dt_start = _parse_dt(start)
    dt_end = _parse_dt(end)
    match = _base_match(dt_start, dt_end, type, path=None, ip=None)

    # total + unique + first/last
    pipeline_main = [
        {"$match": match} if match else {"$match": {}},
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "unique_ips": {"$addToSet": "$ip"},
            "first_ts": {"$min": "$ts"},
            "last_ts": {"$max": "$ts"},
        }},
        {"$project": {
            "_id": 0,
            "total": 1,
            "unique_ips": {"$size": "$unique_ips"},
            "first_ts": 1,
            "last_ts": 1,
        }},
    ]
    main = list(log_col.aggregate(pipeline_main))
    main_doc = main[0] if main else {"total": 0, "unique_ips": 0, "first_ts": None, "last_ts": None}

    # breakdown by type
    pipeline_by_type = [
        {"$match": match} if match else {"$match": {}},
        {"$group": {"_id": "$type", "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "type": "$_id", "count": 1}},
        {"$sort": {"count": -1}},
    ]
    by_type = list(log_col.aggregate(pipeline_by_type))

    # breakdown by method
    pipeline_by_method = [
        {"$match": match} if match else {"$match": {}},
        {"$group": {"_id": "$method", "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "method": "$_id", "count": 1}},
        {"$sort": {"count": -1}},
    ]
    by_method = list(log_col.aggregate(pipeline_by_method))

    def _top(field: str, key_name: str):
        pipe = [
            {"$match": match} if match else {"$match": {}},
            {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
            {"$project": {"_id": 0, key_name: "$_id", "count": 1}},
            {"$sort": {"count": -1}},
            {"$limit": top_n},
        ]
        return list(log_col.aggregate(pipe))

    return {
        "range": {
            "start": dt_start.isoformat() if dt_start else None,
            "end": dt_end.isoformat() if dt_end else None,
        },
        "filters": {"type": type},
        "total_events": main_doc["total"],
        "unique_ips": main_doc["unique_ips"],
        "first_ts": main_doc["first_ts"].isoformat() if main_doc["first_ts"] else None,
        "last_ts": main_doc["last_ts"].isoformat() if main_doc["last_ts"] else None,
        "by_type": by_type,
        "by_method": by_method,
        "top_paths": _top("path", "path"),
        "top_referrers": _top("referer", "referer"),
        "top_user_agents": _top("user_agent", "user_agent"),
    }


# -----------------------------
# 2) 타임시리즈: 시간 단위별 이벤트 수
# -----------------------------

@router.get("/timeseries")
async def logs_timeseries(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    granularity: Literal["minute", "hour", "day", "week", "month"] = Query("hour"),
):
    """
    응답 예시:
    {
      "granularity": "hour",
      "range": {"start": "2026-01-17T00:00:00+00:00", "end": "2026-01-18T00:00:00+00:00"},
      "filters": {"type": null},
      "points": [
        {"bucket": "2026-01-17T15:00:00+00:00", "count": 12, "unique_ips": 5, "types": {"homepage": 3, "search_start": 9}},
        {"bucket": "2026-01-17T16:00:00+00:00", "count": 20, "unique_ips": 8, "types": {"homepage": 6, "search_start": 14}}
      ]
    }
    """
    dt_start = _parse_dt(start)
    dt_end = _parse_dt(end)
    unit = _bucket_date_trunc_unit(granularity)
    match = _base_match(dt_start, dt_end, type, path=None, ip=None)

    pipeline = [
        {"$match": match} if match else {"$match": {}},
        {"$addFields": {
            "bucket": {"$dateTrunc": {"date": "$ts", "unit": unit, "timezone": "UTC"}}
        }},
        # bucket 별 total / unique_ips / type별 카운트
        {"$group": {
            "_id": {"bucket": "$bucket", "type": "$type"},
            "count": {"$sum": 1},
            "ips": {"$addToSet": "$ip"},
        }},
        {"$group": {
            "_id": "$_id.bucket",
            "count": {"$sum": "$count"},
            "unique_ips_set": {"$addToSet": "$ips"},  # set of sets
            "types": {"$push": {"k": "$_id.type", "v": "$count"}},
        }},
        {"$project": {
            "_id": 0,
            "bucket": "$_id",
            "count": 1,
            # unique ips flatten: reduce(setOfSets) -> set
            "unique_ips": {
                "$size": {
                    "$reduce": {
                        "input": "$unique_ips_set",
                        "initialValue": [],
                        "in": {"$setUnion": ["$$value", "$$this"]},
                    }
                }
            },
            "types": {"$arrayToObject": "$types"},
        }},
        {"$sort": {"bucket": 1}},
    ]

    points = list(log_col.aggregate(pipeline))
    for p in points:
        if isinstance(p.get("bucket"), datetime):
            p["bucket"] = p["bucket"].replace(tzinfo=timezone.utc).isoformat()

    return {
        "granularity": unit,
        "range": {"start": dt_start.isoformat() if dt_start else None, "end": dt_end.isoformat() if dt_end else None},
        "filters": {"type": type},
        "points": points,
    }


# -----------------------------
# 3) Top N: 특정 필드 기준 상위값
# -----------------------------

@router.get("/top")
async def logs_top(
    field: Literal["ip", "path", "user_agent", "referer", "type"] = Query("ip"),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    type: Optional[str] = Query(None, description="type 필터 (예: homepage만)"),
    limit: int = Query(20, ge=1, le=200),
):
    """
    응답 예시:
    {
      "field": "ip",
      "range": {"start": null, "end": null},
      "filters": {"type": null},
      "items": [
        {"value": "122.202.51.93", "count": 120, "last_ts": "2026-01-17T15:32:41.615+00:00"},
        {"value": "1.2.3.4", "count": 44, "last_ts": "2026-01-17T14:10:11.000+00:00"}
      ]
    }
    """
    dt_start = _parse_dt(start)
    dt_end = _parse_dt(end)
    match = _base_match(dt_start, dt_end, type, path=None, ip=None)

    pipeline = [
        {"$match": match} if match else {"$match": {}},
        {"$group": {"_id": f"${field}", "count": {"$sum": 1}, "last_ts": {"$max": "$ts"}}},
        {"$project": {"_id": 0, "value": "$_id", "count": 1, "last_ts": 1}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    items = list(log_col.aggregate(pipeline))
    for it in items:
        if it.get("last_ts"):
            it["last_ts"] = it["last_ts"].isoformat()

    return {
        "field": field,
        "range": {"start": dt_start.isoformat() if dt_start else None, "end": dt_end.isoformat() if dt_end else None},
        "filters": {"type": type},
        "items": items,
    }


# -----------------------------
# 4) 검색 옵션 통계: search_start.options 상세 분포
# -----------------------------

@router.get("/search/options")
async def search_options_stats(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
):
    """
    응답 예시(프론트에서 그래프/표로 뽑기 쉽게 설계):
    {
      "range": {"start": null, "end": null},
      "search_start_total": 1200,

      "by_option": [
        {"option": 1, "count": 300},
        {"option": 2, "count": 400},
        {"option": 5, "count": 500}
      ],

      "uncertainty": {
        "min": 0.1,
        "max": 0.9,
        "avg": 0.52,
        "histogram": [
          {"bucket": "0.0-0.1", "count": 10},
          {"bucket": "0.1-0.2", "count": 60},
          ...
          {"bucket": "0.9-1.0", "count": 5}
        ]
      },

      "year_ranges": {
        "startyear_min": 1990,
        "startyear_max": 2025,
        "endyear_min": 1990,
        "endyear_max": 2025,
        "top_ranges": [
          {"startyear": 2020, "endyear": 2025, "count": 120},
          {"startyear": 2025, "endyear": 2025, "count": 80}
        ]
      },

      "countOption": [
        {"countOption": false, "count": 1100},
        {"countOption": true,  "count": 100}
      ],

      "selectedConferences": {
        "top_conferences": [
          {"conf": "CC", "count": 450},
          {"conf": "CGO", "count": 380}
        ],
        "selection_size_histogram": [
          {"k": 1, "count": 300},
          {"k": 2, "count": 500},
          {"k": 3, "count": 200}
        ]
      }
    }
    """
    dt_start = _parse_dt(start)
    dt_end = _parse_dt(end)

    match = _base_match(dt_start, dt_end, "search_start", path=None, ip=None)

    # 전체 search_start 수
    total_pipe = [
        {"$match": match} if match else {"$match": {"type": "search_start"}},
        {"$group": {"_id": None, "total": {"$sum": 1}}},
        {"$project": {"_id": 0, "total": 1}},
    ]
    total_docs = list(log_col.aggregate(total_pipe))
    total = total_docs[0]["total"] if total_docs else 0

    # option 분포
    by_option_pipe = [
        {"$match": match} if match else {"$match": {"type": "search_start"}},
        {"$group": {"_id": "$options.option", "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "option": "$_id", "count": 1}},
        {"$sort": {"count": -1}},
    ]
    by_option = list(log_col.aggregate(by_option_pipe))

    # countOption 분포
    by_countopt_pipe = [
        {"$match": match} if match else {"$match": {"type": "search_start"}},
        {"$group": {"_id": "$options.countOption", "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "countOption": "$_id", "count": 1}},
        {"$sort": {"count": -1}},
    ]
    by_countopt = list(log_col.aggregate(by_countopt_pipe))

    # uncertainty: min/max/avg + histogram(0.1 단위)
    uncert_pipe = [
        {"$match": match} if match else {"$match": {"type": "search_start"}},
        {"$group": {
            "_id": None,
            "min": {"$min": "$options.uncertainty"},
            "max": {"$max": "$options.uncertainty"},
            "avg": {"$avg": "$options.uncertainty"},
        }},
        {"$project": {"_id": 0, "min": 1, "max": 1, "avg": 1}},
    ]
    uncert_doc = (list(log_col.aggregate(uncert_pipe)) or [{"min": None, "max": None, "avg": None}])[0]

    hist_pipe = [
        {"$match": match} if match else {"$match": {"type": "search_start"}},
        {"$project": {
            "u": "$options.uncertainty",
            "bucket": {
                "$concat": [
                    {"$toString": {"$floor": {"$multiply": ["$options.uncertainty", 10]}}},
                    "0"
                ]
            }
        }},
        # bucket: 0..9 (0.0~0.9) 형태로 만들어서 나중에 라벨링
        {"$group": {"_id": "$bucket", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    raw_hist = list(log_col.aggregate(hist_pipe))
    # 라벨을 "0.0-0.1" 형태로 변환
    histogram = []
    for h in raw_hist:
        # h["_id"]가 "00","10"... 같은 형태(의도)
        try:
            base = int(h["_id"]) / 100.0  # "10" -> 0.1
        except Exception:
            base = None
        if base is None:
            continue
        upper = min(base + 0.1, 1.0)
        histogram.append({"bucket": f"{base:.1f}-{upper:.1f}", "count": h["count"]})

    # year ranges: min/max + top ranges
    year_pipe = [
        {"$match": match} if match else {"$match": {"type": "search_start"}},
        {"$group": {
            "_id": None,
            "startyear_min": {"$min": "$options.startyear"},
            "startyear_max": {"$max": "$options.startyear"},
            "endyear_min": {"$min": "$options.endyear"},
            "endyear_max": {"$max": "$options.endyear"},
        }},
        {"$project": {"_id": 0, "startyear_min": 1, "startyear_max": 1, "endyear_min": 1, "endyear_max": 1}},
    ]
    year_doc = (list(log_col.aggregate(year_pipe)) or [{
        "startyear_min": None, "startyear_max": None, "endyear_min": None, "endyear_max": None
    }])[0]

    top_ranges_pipe = [
        {"$match": match} if match else {"$match": {"type": "search_start"}},
        {"$group": {"_id": {"startyear": "$options.startyear", "endyear": "$options.endyear"}, "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "startyear": "$_id.startyear", "endyear": "$_id.endyear", "count": 1}},
        {"$sort": {"count": -1}},
        {"$limit": 20},
    ]
    top_ranges = list(log_col.aggregate(top_ranges_pipe))

    # selectedConferences: top conferences + selection size histogram
    top_conf_pipe = [
        {"$match": match} if match else {"$match": {"type": "search_start"}},
        {"$unwind": "$options.selectedConferences"},
        {"$group": {"_id": "$options.selectedConferences", "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "conf": "$_id", "count": 1}},
        {"$sort": {"count": -1}},
        {"$limit": 50},
    ]
    top_confs = list(log_col.aggregate(top_conf_pipe))

    size_hist_pipe = [
        {"$match": match} if match else {"$match": {"type": "search_start"}},
        {"$project": {"k": {"$size": {"$ifNull": ["$options.selectedConferences", []]}}}},
        {"$group": {"_id": "$k", "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "k": "$_id", "count": 1}},
        {"$sort": {"k": 1}},
    ]
    size_hist = list(log_col.aggregate(size_hist_pipe))

    return {
        "range": {"start": dt_start.isoformat() if dt_start else None, "end": dt_end.isoformat() if dt_end else None},
        "search_start_total": total,
        "by_option": by_option,
        "uncertainty": {"min": uncert_doc["min"], "max": uncert_doc["max"], "avg": uncert_doc["avg"], "histogram": histogram},
        "year_ranges": {**year_doc, "top_ranges": top_ranges},
        "countOption": by_countopt,
        "selectedConferences": {"top_conferences": top_confs, "selection_size_histogram": size_hist},
    }


# -----------------------------
# 5) 퍼널: 홈페이지 방문 -> 검색 시작 전환률 (IP 기반)
# -----------------------------

@router.get("/funnel/home-to-search")
async def funnel_home_to_search(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
):
    """
    IP 기준 퍼널(동일 기간 내):
    - homepage를 본 unique ip
    - search_start를 한 unique ip
    - 둘 다 한 unique ip (교집합)
    - conversion = both / homepage_viewers

    응답 예시:
    {
      "range": {"start": null, "end": null},
      "unique_homepage_ips": 1000,
      "unique_search_ips": 400,
      "unique_both_ips": 350,
      "conversion_rate": 0.35,
      "notes": [
        "동일 기간 내 IP 교집합 기반(세션 추적 아님)",
        "NAT 환경에서는 여러 사용자가 같은 IP로 보일 수 있음"
      ]
    }
    """
    dt_start = _parse_dt(start)
    dt_end = _parse_dt(end)

    match_home = _base_match(dt_start, dt_end, "homepage", path=None, ip=None)
    match_search = _base_match(dt_start, dt_end, "search_start", path=None, ip=None)

    home_ips_pipe = [
        {"$match": match_home} if match_home else {"$match": {"type": "homepage"}},
        {"$group": {"_id": "$ip"}},
    ]
    search_ips_pipe = [
        {"$match": match_search} if match_search else {"$match": {"type": "search_start"}},
        {"$group": {"_id": "$ip"}},
    ]

    home_ips = {d["_id"] for d in log_col.aggregate(home_ips_pipe) if d.get("_id")}
    search_ips = {d["_id"] for d in log_col.aggregate(search_ips_pipe) if d.get("_id")}
    both = home_ips & search_ips

    unique_home = len(home_ips)
    unique_search = len(search_ips)
    unique_both = len(both)
    conv = (unique_both / unique_home) if unique_home else 0.0

    return {
        "range": {"start": dt_start.isoformat() if dt_start else None, "end": dt_end.isoformat() if dt_end else None},
        "unique_homepage_ips": unique_home,
        "unique_search_ips": unique_search,
        "unique_both_ips": unique_both,
        "conversion_rate": conv,
        "notes": [
            "동일 기간 내 IP 교집합 기반(세션 추적 아님)",
            "NAT/공유망에서는 여러 사용자가 같은 IP로 보일 수 있음",
        ],
    }


# -----------------------------
# 6) 상세 탐색용: 특정 IP의 최근 로그(디버깅/운영용)
# -----------------------------

@router.get("/recent/by-ip")
async def recent_logs_by_ip(
    ip: str = Query(..., description="조회할 IP"),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
):
    """
    응답 예시:
    {
      "ip": "122.202.51.93",
      "range": {"start": null, "end": null},
      "limit": 200,
      "items": [
        {
          "ts": "2026-01-17T15:32:28.521+00:00",
          "type": "homepage",
          "path": "/",
          "method": "GET",
          "referer": "",
          "job_id": null,
          "options": null
        },
        {
          "ts": "2026-01-17T15:32:41.615+00:00",
          "type": "search_start",
          "path": null,
          "method": null,
          "referer": "https://pcss.r-e.kr/",
          "job_id": "3d870a4f-...",
          "options": {...}
        }
      ]
    }
    """
    dt_start = _parse_dt(start)
    dt_end = _parse_dt(end)
    match = _base_match(dt_start, dt_end, type_=None, path=None, ip=ip)

    pipeline = [
        {"$match": match} if match else {"$match": {"ip": ip}},
        {"$sort": {"ts": -1}},
        {"$limit": limit},
        {"$project": {
            "_id": 0,
            "ts": 1,
            "type": 1,
            "ip": 1,
            "method": 1,
            "path": 1,
            "query": 1,
            "user_agent": 1,
            "referer": 1,
            "job_id": 1,
            "options": 1,
        }},
    ]
    items = list(log_col.aggregate(pipeline))
    for it in items:
        if it.get("ts"):
            it["ts"] = it["ts"].isoformat()
    return {
        "ip": ip,
        "range": {"start": dt_start.isoformat() if dt_start else None, "end": dt_end.isoformat() if dt_end else None},
        "limit": limit,
        "items": items,
    }
