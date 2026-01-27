from typing import List
import requests
import gzip
import html
import re
import os
import json
import math
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.progress import (
    Progress,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
    TimeElapsedColumn,
    TextColumn,
)
from rich.console import Console
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

LLM_URL = os.getenv("CUSTOM_API_URL")
CUSTOM_TOKEN = os.getenv("CUSTOM_TOKEN")
LLM_MODEL = os.getenv("LLM_MODEL", "")

console = Console()

def get_headers():    
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CUSTOM_TOKEN}",
    }

# 모델 자동 설정
if not LLM_MODEL and LLM_URL:
    try:
        model_resp = requests.get(f"{LLM_URL}/models", headers=get_headers())
        model_resp.raise_for_status()
        LLM_MODEL = model_resp.json()["data"][0]["id"]
    except Exception as e:
        console.print(f"[red]Failed to fetch model list:[/] {e}")
        LLM_MODEL = "llama3:70b"

def llm_api_answer(query, model):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an expert in determining the likelihood that a given name is Korean."},
            {"role": "user", "content": query},
        ],
        "temperature": 0.1,  # 일관성을 위해 낮춤
        "max_tokens": 10,   # 숫자만 받으므로 최소화
    }
    try:
        response = requests.post(
            f"{LLM_URL}/chat/completions",
            json=payload,
            headers=get_headers(),
            timeout=60,
        )
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"ERROR: {str(e)}"

def judge_name(name):    
    result = llm_api_answer(
        query = f"Express the likelihood of this {name} being Korean using only a number between 0~1. You need to say number only",
        model = LLM_MODEL
    )
    
    match = re.findall(r"\d+\.\d+|\d+", result)
    if not match:
        return [False, result]

    try:
        value = float(match[0])
        value = max(0.0, min(1.0, value))
        return float("{:.1f}".format(value))
    except:
        return [False, "Parsing Error"]

# ======= 저자 추출 및 다운로드 함수 (기존과 동일) =======
# (공간상 생략하지만 기존 코드의 extract_authors_iteratively, download_dblp_xml_gz 그대로 사용)
from app.db import name_col # DB 연결은 실제 환경에 맞게 임포트

def cleanup_files(*paths: Path | str):
    for p in paths:
        try:
            p = Path(p)
            if p.exists(): p.unlink()
        except: pass

# ======= 메인 로직 (병렬화 적용) =======

def main():
    # 1. XML 처리 및 저자 추출 (생략된 기존 로직 수행)
    # ... (생략: authors 리스트 준비 과정) ...
    authors = [] # 예시를 위해 비워둠, 실제론 추출된 리스트
    
    # 중복 및 DB 체크 후 처리할 대상 선정
    name_dict = {doc["name"]: doc["score"] for doc in name_col.find({}, {"_id": 0, "name": 1, "score": 1})}
    authors = [name for name in list(set(authors)) if name not in name_dict]

    print(f"\n=== LLM 병렬 처리 시작 (Batch) ===")
    print(f"모델: {LLM_MODEL} | 대상: {len(authors)}명")
    
    MAX_WORKERS = 16 # TITAN RTX 4장 사양에 최적화
    BULK_SIZE = 100

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TextColumn("Last Score: [bold yellow]{task.fields[score]}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:

        task = progress.add_task("LLM Processing", total=len(authors), score="-")

        for i in range(0, len(authors), BULK_SIZE):
            batch = authors[i : i + BULK_SIZE]
            ops: list[UpdateOne] = []
            
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_author = {executor.submit(judge_name, name): name for name in batch}
                
                for future in as_completed(future_to_author):
                    author = future_to_author[future]
                    score = 0.0
                    try:
                        res = future.result()
                        if isinstance(res, list): # 에러 발생 시
                            console.print(f"[red]Error for {author}:[/] {res[1]}")
                        else:
                            score = res
                            ops.append(UpdateOne(
                                {"name": author},
                                {
                                    "$set": {"score": score},
                                    "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
                                    "$currentDate": {"updated_at": True},
                                },
                                upsert=True
                            ))
                    except Exception as e:
                        console.print(f"[red]Thread fail for {author}:[/] {e}")
                    
                    progress.update(task, advance=1, score=score)

            if ops:
                try:
                    name_col.bulk_write(ops, ordered=False)
                except Exception as e:
                    console.print(f"[yellow]DB Bulk Error:[/] {e}")

def rejudge_high_score_names(threshold: float = 0.7, batch_size: int = 500, bulk_size: int = 100):
    console.print(f"\n[bold cyan]=== Rejudge start (Parallel) ===[/] threshold={threshold}")
    
    targets = list(name_col.find({"score": {"$gte": threshold}}, {"_id": 0, "name": 1}))
    total = len(targets)
    
    if total == 0:
        console.print("No targets found."); return

    MAX_WORKERS = 16

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TextColumn("New Score: [bold magenta]{task.fields[score]}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Rejudging", total=total, score="-")

        for i in range(0, total, bulk_size):
            batch = [doc["name"] for doc in targets[i : i + bulk_size]]
            ops = []

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_name = {executor.submit(judge_name, n): n for n in batch}
                for future in as_completed(future_to_name):
                    name = future_to_name[future]
                    new_score = 0.0
                    try:
                        res = future.result()
                        if not isinstance(res, list):
                            new_score = res
                            ops.append(UpdateOne({"name": name}, {"$set": {"score": new_score}, "$currentDate": {"updated_at": True}}))
                    except: pass
                    progress.update(task, advance=1, score=new_score)

            if ops:
                name_col.bulk_write(ops, ordered=False)

if __name__ == "__main__":
    choice = input("1: Main Extraction\n2: Rejudge\nSelect: ")
    if choice == "1": main()
    elif choice == "2":
        t = input("Threshold (default 0.7): ")
        rejudge_high_score_names(threshold=float(t) if t else 0.7)