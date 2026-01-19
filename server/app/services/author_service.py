from typing import Any, Dict, List, Optional
from app.db.mongo import get_papers_col

async def compute_author_stats_mongo(
    target_author: str,
    include_papers: bool = False,
    conf_list: Optional[List[str]] = None,
    startyear: Optional[int] = None,
    endyear: Optional[int] = None,
) -> Dict[str, Any]:
    if not target_author:
        return {"stats": (0, 0, 0, 0), "total": 0, "papers": [] if include_papers else None}

    col = await get_papers_col()

    match: Dict[str, Any] = {"author_names": target_author}  # 배열에 target_author 포함이면 매치됨

    if conf_list:
        match["conference"] = {"$in": conf_list}

    if startyear is not None and endyear is not None:
        # year가 문자열/정수 혼재 가능하면 둘 다 처리
        years_str = [str(y) for y in range(startyear, endyear + 1)]
        years_int = list(range(startyear, endyear + 1))
        match["$or"] = [{"year": {"$in": years_str}}, {"year": {"$in": years_int}}]

    pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": None,

                "first_author": {
                    "$sum": {
                        "$cond": [
                            {"$eq": [{"$arrayElemAt": ["$author_name", 0]}, target_author]},
                            1,
                            0,
                        ]
                    }
                },

                "first_or_second_author": {
                    "$sum": {
                        "$cond": [
                            {
                                "$or": [
                                    {"$eq": [{"$arrayElemAt": ["$author_name", 0]}, target_author]},
                                    {"$eq": [{"$arrayElemAt": ["$author_name", 1]}, target_author]},
                                ]
                            },
                            1,
                            0,
                        ]
                    }
                },

                "last_author": {
                    "$sum": {
                        "$cond": [
                            {"$eq": [{"$arrayElemAt": ["$author_name", -1]}, target_author]},
                            1,
                            0,
                        ]
                    }
                },

                # co_author = 순수 공저자 (1저자, 2저자, 마지막 제외)
                "co_author": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {
                                        "$gt": [
                                            {"$indexOfArray": ["$author_name", target_author]},
                                            1,
                                        ]
                                    },
                                    {
                                        "$lt": [
                                            {"$indexOfArray": ["$author_name", target_author]},
                                            {
                                                "$subtract": [
                                                    {"$size": "$author_name"},
                                                    1,
                                                ]
                                            },
                                        ]
                                    },
                                ]
                            },
                            1,
                            0,
                        ]
                    }
                },
            }
        },
    ]

    row = None
    async for r in col.aggregate(pipeline, allowDiskUse=True):
        row = r
        break

    if not row:
        result = {"stats": (0, 0, 0, 0), "total": 0}
        if include_papers:
            result["papers"] = []
        return result

    fa = int(row.get("first_author", 0))
    fs = int(row.get("first_or_second_author", 0))
    la = int(row.get("last_author", 0))
    co = int(row.get("co_author", 0))

    result: Dict[str, Any] = {
        "stats": (fa, fs, la, co),
        "total": co,  # 기존 로직에서 total=paperCnt, co_author도 동일
    }

    if include_papers:
        proj = {
            "_id": 0,
            "title": 1,
            "author_names": 1,
            "conference": 1,
            "year": 1,
            "dblp_url": 1,
            "source": 1,
        }

        cursor = col.find(match, proj)
        papers = []
        async for d in cursor:
            title = (d.get("title") or "").strip()
            authors = d.get("author_names") or []
            conf = d.get("conference") or ""
            year = d.get("year")

            # 기존 papers 포맷 최대한 유지
            papers.append(
                {
                    "title": title,
                    "authors": authors,
                    "conference": conf,
                    "year": year,
                    "dblp_url": d.get("dblp_url", ""),
                    "source": d.get("source", ""),
                }
            )

        result["papers"] = papers

    return result
