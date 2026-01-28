import os
import re
import gzip
import html
import json
import requests
from pathlib import Path
from typing import List
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
import sys
import threading

session = requests.Session()

# DB 연결 (사용자 환경의 app.db 구조 유지)
try:
    from app.db import name_col
except ImportError:
    # 테스트용 또는 모듈 경로 문제시 직접 연결 설정 가능
    import pymongo
    client = pymongo.MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    name_col = client["your_db"]["names"]

# 환경 변수 로드
load_dotenv()

LLM_URL = os.getenv("CUSTOM_API_URL")
CUSTOM_TOKEN = os.getenv("CUSTOM_TOKEN")
LLM_MODEL = os.getenv("LLM_MODEL", "")

console = Console()

# ======= 초기 설정 =======

def get_headers():    
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CUSTOM_TOKEN}",
    }

# 모델명 자동 조회
if not LLM_MODEL:
    try:
        model_resp = requests.get(f"{LLM_URL}/models", headers=get_headers())
        model_resp.raise_for_status()
        LLM_MODEL = model_resp.json()["data"][0]["id"]
    except Exception as e:
        console.print(f"[red]모델 정보를 가져올 수 없습니다:[/] {e}")
        LLM_MODEL = "llama3:70b"

# ======= LLM 핵심 함수 =======

stop_event = threading.Event()

def llm_api_answer(query, model):
    payload = {
        "model": model,
        "messages": [
            # 시스템 프롬프트를 curl 예시와 동일하게 수정
            {"role": "system", "content": "You are a helpful assistant that only responds with numbers."},
            {"role": "user", "content": query},
        ],
        "temperature": 0.0,  # curl 테스트와 동일하게 0.0으로 설정
        "max_tokens": 10,
    }
    try:
        response = session.post(
            f"{LLM_URL}/v1/chat/completions",
            json=payload,
            headers=get_headers(),
            timeout=120,
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"ERROR: {str(e)}"

def judge_name(name):
    if stop_event.is_set():
        return [False, "STOPPED"]

    # curl에서 성공한 쿼리 템플릿 그대로 적용
    query = (
        f"Task: Output only a single float number between 0.0 and 1.0 "
        f"representing the probability that '{name}' is a Korean name. "
        f"No JSON, no explanation.\nExample: 0.95\nValue:"
    )

    result = llm_api_answer(query=query, model=LLM_MODEL)

    if "ERROR:" in result:
        return [False, f"API Error: {result}"]

    # 숫자 추출 (문자열에서 숫자만 골라냄)
    match = re.search(r"([0-1]\.\d+|[01])", result)
    if not match:
        return 0.0 

    try:
        value = float(match.group(1))
        value = max(0.0, min(1.0, value))
        return round(value, 2)
    except:
        return 0.0

# ======= 파일 다운로드 및 XML 추출 =======

def download_dblp_xml_gz(
    url: str = "https://dblp.uni-trier.de/xml/dblp.xml.gz",
    out_dir: str | Path = os.path.dirname(__file__),
    gz_name: str = "dblp.xml.gz",
    xml_name: str = "dblp.xml",
    chunk_size: int = 1024 * 1024,
) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    gz_path, xml_path = out_dir / gz_name, out_dir / xml_name

    progress = Progress(TextColumn("[bold blue]{task.description}"), BarColumn(), DownloadColumn(), TransferSpeedColumn(), TimeRemainingColumn())
    with progress:
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            download_task = progress.add_task("Downloading", total=int(r.headers.get("Content-Length", 0)))
            with open(gz_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    f.write(chunk)
                    progress.update(download_task, advance=len(chunk))

        gz_size = gz_path.stat().st_size
        extract_task = progress.add_task("Extracting", total=gz_size)
        with gzip.open(gz_path, "rb") as f_in, open(xml_path, "wb") as f_out:
            while chunk := f_in.read(chunk_size):
                f_out.write(chunk)
                progress.update(extract_task, advance=len(chunk))
    cleanup_files(gz_path)
    return gz_path, xml_path

def extract_authors_iteratively(xml_file_path: str, max_authors: int = None) -> List[str]:
    authors = []
    author_count = 0
    progress = Progress(TextColumn("[bold blue]{task.description}"), BarColumn(), TextColumn("Lines: {task.completed}"), TextColumn("Authors: [bold green]{task.fields[authors]}"), TimeElapsedColumn(), console=console)

    def parse(file):
        nonlocal author_count
        with progress:
            task = progress.add_task("Parsing XML", total=None, authors=0)
            for line in file:
                matches = re.findall(r"<author[^>]*>(.*?)</author>", line)
                for m in matches:
                    name = html.unescape(m.strip())
                    if name:
                        authors.append(name)
                        author_count += 1
                        progress.update(task, authors=author_count)
                        if max_authors and author_count >= max_authors: return
                progress.advance(task, 1)

    try:
        with open(xml_file_path, "r", encoding="utf-8") as f: parse(f)
    except UnicodeDecodeError:
        with open(xml_file_path, "r", encoding="latin-1") as f: parse(f)
    return authors

def cleanup_files(*paths: Path | str):
    for p in paths:
        try:
            p = Path(p)
            if p.exists(): p.unlink()
        except: pass

# ======= 메인 실행 로직 =======

def main():
    xml_path = os.path.join(os.path.dirname(__file__), "dblp.xml")
    if not os.path.exists(xml_path):
        download_dblp_xml_gz()

    authors_json = os.path.join(os.path.dirname(__file__), 'all_authors.json')
    if not os.path.exists(authors_json):
        authors = extract_authors_iteratively(xml_path)
        authors = list(set([re.sub(r'\s*\d+\s*$', '', s) for s in authors]))
        with open(authors_json, 'w', encoding='utf-8') as f:
            json.dump(authors, f, ensure_ascii=False, indent=2)
    else:
        with open(authors_json, 'r', encoding='utf-8') as f:
            authors = json.load(f)

    # DB 중복 제거
    name_dict = {doc["name"]: 1 for doc in name_col.find({}, {"_id": 0, "name": 1})}
    new_authors = [a for a in authors if a not in name_dict]
    console.print(f"Total: {len(authors)} | New: {len(new_authors)}")

    if not new_authors:
        console.print("[yellow]처리할 새로운 저자가 없습니다. 종료합니다.[/]")
        return

    MAX_WORKERS = 16 
    BULK_SIZE = 100

    with Progress(
        TextColumn("[bold blue]{task.description}"), 
        BarColumn(), 
        TextColumn("{task.completed}/{task.total}"), 
        TextColumn("Score: [bold yellow]{task.fields[score]}"), 
        TimeElapsedColumn(), 
        TimeRemainingColumn(), 
        console=console
    ) as progress:
        task = progress.add_task("LLM Processing", total=len(new_authors), score="-")
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for i in range(0, len(new_authors), BULK_SIZE):
                if stop_event.is_set(): 
                    console.print("[red]Stop event detected. Exiting loop...[/]")
                    break

                batch = new_authors[i : i + BULK_SIZE]
                
                # 디버깅: 현재 배치 사이즈 확인
                # console.print(f"Processing batch {i} to {i+len(batch)}") 

                futures = {executor.submit(judge_name, name): name for name in batch}
                
                ops = []
                for future in as_completed(futures):
                    name = futures[future]
                    try:
                        res = future.result()
                    except Exception as e:
                        console.print(f"\n[red]Thread Error:[/] {e}")
                        continue
                    
                    if isinstance(res, list) and res[0] is False:
                        # 503 에러면 잠깐 쉬었다가 다시 하게 하거나 스킵
                        if "503" in str(res[1]):
                            console.print(f"\n[yellow]Server busy (503), skipping {name}[/]")
                            continue
                        
                        # 진짜 치명적인 에러면 중단
                        console.print(f"\n[bold red]Critical Error:[/] {res[1]}")
                        stop_event.set()
                        break

                    ops.append(UpdateOne(
                        {"name": name}, 
                        {"$set": {"score": res}, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}, "$currentDate": {"updated_at": True}}, 
                        upsert=True
                    ))
                    progress.update(task, advance=1, score=res)

                if ops:
                    try:
                        name_col.bulk_write(ops, ordered=False)
                    except BulkWriteError as bwe:
                        # console.print(f"\n[red]Bulk Write Error:[/] {bwe.details}")
                        pass

    console.print("[bold green]모든 작업이 완료되었습니다.[/]")

def rejudge_high_score_names(threshold: float = 0.7):
    targets = list(name_col.find({"score": {"$gte": threshold}}, {"_id": 0, "name": 1, "score": 1}))
    console.print(f"Rejudging {len(targets)} targets...")
    
    MAX_WORKERS = 16
    BULK_SIZE = 100

    with Progress(TextColumn("[bold blue]{task.description}"), BarColumn(), TextColumn("{task.completed}/{task.total}"), TextColumn("New: [bold magenta]{task.fields[score]}"), TimeElapsedColumn(), TimeRemainingColumn(), console=console) as progress:
        task = progress.add_task("Rejudging", total=len(targets), score="-")
        for i in range(0, len(targets), BULK_SIZE):
            batch = [doc["name"] for doc in targets[i : i + BULK_SIZE]]
            ops = []
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {executor.submit(judge_name, n): n for n in batch}
                for f in as_completed(futures):
                    name = futures[f]
                    new_score = 0.0
                    try:
                        res = f.result()
                        if not isinstance(res, list):
                            new_score = res
                            ops.append(UpdateOne({"name": name}, {"$set": {"score": new_score}, "$currentDate": {"updated_at": True}}))
                    except: pass
                    progress.update(task, advance=1, score=new_score)
            if ops: name_col.bulk_write(ops, ordered=False)

if __name__ == "__main__":
    choice = input("1: Main Extraction\n2: Rejudge\nSelect (1/2): ")
    if choice == "1": main()
    elif choice == "2":
        t = input("Threshold (default 0.7): ")
        rejudge_high_score_names(threshold=float(t) if t else 0.7)