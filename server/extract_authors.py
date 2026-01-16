from typing import List
import requests
import gzip
import html
import re
import os
from pathlib import Path
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
import json
from app.db import name_col

def get_headers():    
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CUSTOM_TOKEN}",
    }

LLM_URL = os.getenv("CUSTOM_API_URL")
CUSTOM_TOKEN = os.getenv("CUSTOM_TOKEN")

console = Console()

# ======= LLM 함수 =======
model_resp = requests.get(f"{LLM_URL}/models", headers=get_headers())
model_resp.raise_for_status()
LLM_MODEL = model_resp.json()["data"][0]["id"]

def single_name_llm(name):    
    result = llm_api_answer(
        query = f"Express the likelihood of this {name} being Korean using only a number between 0~1. You need to say number only",
        model = LLM_MODEL
    )
    
    # 숫자만 추출 (지수 표기법 방지)
    match = re.findall(r"\d+\.\d+|\d+", result)
    if not match:
        console.print(f"[red]No numeric result found in LLM response for '{name}':[/] {result}")
        return False

    value = float(match[0])  # 숫자 문자열을 float으로 변환

    # 숫자 범위 고정 (0.0 ~ 1.0)
    value = max(0.0, min(1.0, value))

    # 소수점 1자리까지 포맷팅
    formatted_value = "{:.1f}".format(value)
    
    formatted_value = float(formatted_value)
    name_dict[name] = formatted_value
    
    name_col.update_one(
        {"name": name},
        {"$set": {"score": formatted_value}},
        upsert=True
    )
    return formatted_value  # 결과 반환 (0.0 ~ 1.0)

def llm_api_answer(query, model):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an expert in determining the likelihood that a given name is Korean."},
            {"role": "user", "content": query},
        ],
        "temperature": 0.7,
        "max_tokens": 300,
    }
    response = requests.post(
        f"{LLM_URL}/chat/completions",
        json=payload,
        headers=get_headers(),
        timeout=60,
    )
    result = response.json()
    return result["choices"][0]["message"]["content"]

# ======= 저자 추출 함수 =======
def extract_authors_iteratively(
    xml_file_path: str,
    max_authors: int | None = None,
) -> List[str]:
    """
    큰 XML 파일을 메모리 효율적으로 처리하여 저자를 추출합니다.
    (rich 진행률 표시)
    """
    authors = []
    author_count = 0

    def process_file(file):
        nonlocal author_count

        progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("Lines: {task.completed}"),
            TextColumn("Authors: [bold green]{task.fields[authors]}"),
            TimeElapsedColumn(),
            console=console,
        )

        with progress:
            task = progress.add_task(
                "Parsing XML",
                total=None,        # 전체 라인 수를 모르므로 무한 진행
                authors=0,
            )

            for line_num, line in enumerate(file, 1):
                author_matches = re.findall(
                    r"<author[^>]*>(.*?)</author>", line
                )

                for match in author_matches:
                    author_name = html.unescape(match.strip())
                    if author_name:
                        authors.append(author_name)
                        author_count += 1

                        progress.update(
                            task,
                            authors=author_count,
                        )

                        if max_authors and author_count >= max_authors:
                            progress.stop()
                            console.print(
                                f"[bold yellow]Reached limit:[/] {max_authors} authors"
                            )
                            return

                progress.advance(task, 1)

    try:
        with open(xml_file_path, "r", encoding="utf-8") as file:
            process_file(file)

    except UnicodeDecodeError:
        console.print("[yellow]UTF-8 실패 → latin-1 재시도[/]")
        try:
            with open(xml_file_path, "r", encoding="latin-1") as file:
                process_file(file)
        except Exception as e:
            console.print(f"[red]대체 인코딩 실패:[/] {e}")

    except FileNotFoundError:
        console.print(f"[red]파일을 찾을 수 없습니다:[/] {xml_file_path}")

    except Exception as e:
        console.print(f"[red]오류 발생:[/] {e}")

    return authors

def download_dblp_xml_gz(
    url: str = "https://dblp.uni-trier.de/xml/dblp.xml.gz",
    out_dir: str | Path = os.path.dirname(__file__),
    gz_name: str = "dblp.xml.gz",
    xml_name: str = "dblp.xml",
    chunk_size: int = 1024 * 1024,  # 1MB
) -> tuple[Path, Path]:
    """
    DBLP dblp.xml.gz를 다운로드하고 압축을 해제하여 dblp.xml까지 저장합니다.
    (다운로드 + 압축해제까지만, rich 진행률 표시)
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    gz_path = out_dir / gz_name
    xml_path = out_dir / xml_name

    progress = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    )

    with progress:
        # 1) 다운로드
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("Content-Length", 0))

            download_task = progress.add_task(
                "Downloading dblp.xml.gz",
                total=total_size,
            )

            with open(gz_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        progress.update(download_task, advance=len(chunk))

        # 2) 압축 해제
        gz_size = gz_path.stat().st_size
        extract_task = progress.add_task(
            "Extracting dblp.xml",
            total=gz_size,
        )

        with gzip.open(gz_path, "rb") as f_in, open(xml_path, "wb") as f_out:
            while True:
                chunk = f_in.read(chunk_size)
                if not chunk:
                    break
                f_out.write(chunk)
                progress.update(extract_task, advance=len(chunk))

    cleanup_files(gz_path)
    return gz_path, xml_path

def cleanup_files(*paths: Path | str):
    for p in paths:
        try:
            p = Path(p)
            if p.exists():
                p.unlink()
                console.print(f"[dim]Deleted:[/] {p.name}")
        except Exception as e:
            console.print(f"[red]Failed to delete {p}:[/] {e}")


if __name__ == "__main__": 
    if not os.path.exists(os.path.join(os.path.dirname(__file__), "dblp.xml")):
        print("=== DBLP 데이터 다운로드 ===")
        download_dblp_xml_gz()

    print("\n=== 저자 추출 ===")
    if not os.path.exists(os.path.join(os.path.dirname(__file__), "all_authors.json")):
        authors = extract_authors_iteratively(os.path.join(os.path.dirname(__file__), "dblp.xml"))  # 1000명으로 제한
        print(f"총 {len(authors)}명의 저자를 찾았습니다.")
    else:
        with open(os.path.join(os.path.dirname(__file__), 'all_authors.json'), 'r', encoding='utf-8') as f:
            authors = json.load(f)
        print(f"'all_authors.json'에서 {len(authors)}명의 저자를 불러왔습니다.")
    
    authors = [re.sub(r'\s*\d+\s*$', '', s) for s in authors]  # 이름 끝의 숫자 제거
    authors = list(set(authors))  # 중복 제거
    
    with open(os.path.join(os.path.dirname(__file__), 'all_authors.json'), 'w', encoding='utf-8') as f:
        json.dump(authors, f, ensure_ascii=False, indent=2)
        
    from app.libs.llm import single_name_llm, name_dict
    authors = [name for name in authors if name not in name_dict]
    print(f"새로운 {len(authors)}명의 저자를 찾았습니다.")
    
    print("\n=== LLM 처리 시작 ===")
    print(f"모델: {LLM_MODEL}")
    interrupted = False

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TextColumn("Current: [bold green]{task.fields[name]}"),
        TextColumn("Score: [bold yellow]{task.fields[score]}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:

        task = progress.add_task(
            "Processing authors with LLM",
            total=len(authors),
            name="-",
            score="-",
        )

        try:
            for author in authors:
                # (중요) 여기서는 Exception과 KeyboardInterrupt를 섞어 잡지 말고,
                # LLM 에러만 처리
                try:
                    score = single_name_llm(author)
                    if score == False:
                        console.print(f"[red]LLM error for '{author}':[/] No numeric result found.")
                        continue
                except Exception as e:
                    score = 0.0
                    console.print(f"[red]LLM error for '{author}':[/] {e}")

                progress.update(task, advance=1, name=author, score=score)

        except KeyboardInterrupt:
            interrupted = True
            console.print("\n[yellow]Interrupted by user. Stopping LLM processing...[/]")
            os._exit(0)

    print("LLM 처리 완료.")
    print("결과는 DB에 저장되었습니다.")
    
    cleanup_files(
        os.path.join(os.path.dirname(__file__), "dblp.xml"),
        os.path.join(os.path.dirname(__file__), "all_authors.json"),
    )

    