from lxml import etree
from app.db import conf_col, papers_col
import os
import urllib.parse
import re
import sys
import requests
import gzip
import re
import os
from pathlib import Path
from rich.progress import (
    Progress,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
    TextColumn,
    TimeElapsedColumn,
    SpinnerColumn,
)
from rich.console import Console

# =========================
# 설정
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
xml_path = os.path.join(BASE_DIR, 'dblp.xml')

BATCH_SIZE = 1000  # MongoDB bulk insert 크기
console = Console()

# Conference map 로드
def load_conference_map():
    conferences = conf_col.find({}, {"_id": 0, "params": 1, "name": 1})
    conf_map = {}
    for conf in conferences:
        if conf.get('params'):
            for param in conf['params']:
                conf_map[param] = conf['name']
    return conf_map

# 메인 트랙 판별
def is_main_track(elem, title, booktitle):
    if not title:
        return False

    title_lower = title.lower()
    booktitle_lower = booktitle.lower() if booktitle else ""

    key = elem.get('key', '').lower()
    crossref = elem.findtext('crossref')
    crossref_lower = crossref.lower() if crossref else ""

    # 구조적 필터
    indicators = ['workshop', 'adjunct', 'companion', 'supplement']
    for ind in indicators:
        if ind in key or ind in crossref_lower:
            return False

    venue_blacklist_patterns = [
        r'\bworkshops?\b', r'\btutorials?\b', r'\bdoctoral\b', r'\bconsortium\b',
        r'\badjunct\b', r'\bcompanion\b', r'\bdemo\b', r'\bdemonstrations?\b',
        r'\bposters?\b', r'\bshort papers?\b', r'\bphd symposium\b',
        r'\bextended abstracts?\b', r'\bchallenge\b', r'\bcompetitions?\b'
    ]

    title_blacklist_patterns = [
        r'\bmessage from\b', r'\bwelcome\b', r'\bpreface\b', r'\bforeword\b',
        r'\bkeynote\b', r'\bpanel\b', r'\bopening remarks\b', r'\bcommittee\b',
        r'\bauthor index\b', r'\breviewers\b', r'\bsession\b', r'\bpresentation\b',
        r'\bbest paper awards?\b', r'\bprogram\b', r'\bcall for papers\b'
    ]

    for pattern in venue_blacklist_patterns:
        if re.search(pattern, booktitle_lower):
            return False

    for pattern in title_blacklist_patterns:
        if re.search(pattern, title_lower):
            return False

    pages = elem.findtext('pages')
    if pages and re.match(r'^[ivxlcdm]+$', pages.lower()):
        return False

    return True

# DBLP 파싱 & DB 적재
def parse_dblp(xml_path, conf_map):
    paper_tags = {'inproceedings', 'article'}

    abs_xml_path = os.path.abspath(xml_path)
    xml_dir = os.path.dirname(abs_xml_path)
    filename_only = os.path.basename(abs_xml_path)
    dtd_path = os.path.join(xml_dir, "dblp.dtd")

    console = Console()

    if not os.path.exists(dtd_path):
        console.print(f"[bold red]DTD 파일 없음:[/bold red] {dtd_path}")
        return

    original_cwd = os.getcwd()
    os.chdir(xml_dir)

    try:
        etree.DTD(file=dtd_path)
        console.print("[green]DTD 로드 성공[/green]")
    except etree.DTDParseError as e:
        console.print(f"[bold red]DTD 파싱 실패:[/bold red] {e}")
        os.chdir(original_cwd)
        return

    batch_docs = []
    count = 0
    matched_count = 0
    context = None

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]DBLP 파싱 중[/bold blue]"),
        BarColumn(),
        TextColumn("scan: {task.fields[scan]}"),
        TextColumn("saved: {task.fields[saved]}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False
    )

    try:
        context = etree.iterparse(
            filename_only,
            events=('end',),
            load_dtd=True,
            huge_tree=True,
            recover=True
        )

        with progress:
            task_id = progress.add_task(
                "parse",
                total=None,
                scan=0,
                saved=0
            )

            for event, elem in context:
                if elem.tag in paper_tags:
                    count += 1
                    progress.update(task_id, scan=count)

                    key = elem.get('key')
                    venue_id = None
                    if key:
                        parts = key.split('/')
                        if len(parts) >= 2:
                            venue_id = parts[1]

                    if venue_id not in conf_map:
                        elem.clear()
                        while elem.getprevious() is not None:
                            del elem.getparent()[0]
                        continue

                    title = elem.findtext('title')
                    booktitle_xml = elem.findtext('booktitle')
                    venue_str = booktitle_xml if booktitle_xml else elem.findtext('journal')

                    if not is_main_track(elem, title, venue_str):
                        elem.clear()
                        while elem.getprevious() is not None:
                            del elem.getparent()[0]
                        continue

                    matched_count += 1
                    progress.update(task_id, saved=matched_count)

                    year = elem.findtext('year')
                    official_conf_name = conf_map[venue_id]

                    source = elem.findtext('ee')
                    if not source:
                        raw_url = elem.findtext('url')
                        if raw_url:
                            source = f"https://dblp.org/{raw_url}"

                    dblp_rel_path = elem.findtext('url')
                    if dblp_rel_path:
                        dblp_url = f"https://dblp.org/{dblp_rel_path}"
                    elif key:
                        dblp_url = f"https://dblp.org/rec/{key}.html"
                    else:
                        dblp_url = ""

                    authors = []
                    author_urls = []
                    for author in elem.findall('author'):
                        if author.text:
                            authors.append(author.text)
                            pid = author.get('pid')
                            if pid:
                                author_urls.append(f"https://dblp.org/pid/{pid}")
                            else:
                                enc = urllib.parse.quote_plus(author.text)
                                author_urls.append(f"https://dblp.org/search/author?q={enc}")

                    record = {
                        'title': title,
                        'author_name': authors,
                        'author_url': author_urls,
                        'conference': official_conf_name,
                        'year': int(year) if year and year.isdigit() else year,
                        'source': source,
                        'dblp_url': dblp_url
                    }

                    batch_docs.append(record)

                    if len(batch_docs) >= BATCH_SIZE:
                        papers_col.insert_many(batch_docs, ordered=False)
                        batch_docs.clear()

                    elem.clear()
                    while elem.getprevious() is not None:
                        del elem.getparent()[0]

                elif elem.tag == 'dblp':
                    elem.clear()

            if batch_docs:
                papers_col.insert_many(batch_docs, ordered=False)
                batch_docs.clear()

    except Exception:
        console.print("[bold red]파싱 중 오류 발생[/bold red]")
        import traceback
        console.print(traceback.format_exc())
    finally:
        os.chdir(original_cwd)
        if context:
            del context

    console.print(
        f"[bold green]완료[/bold green]: 메인 트랙 논문 "
        f"[bold]{matched_count}[/bold]개 DB 저장"
    )

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

def main():
    print("=== DBLP 논문 추출 시작 ===")
    if not os.path.exists(os.path.join(os.path.dirname(__file__), "dblp.xml")):
        print("=== DBLP 데이터 다운로드 ===")
        download_dblp_xml_gz()
    
    print("학회 정보 로드 중...")
    mapping = load_conference_map()
    if not mapping:
        print("학회 정보 로드 실패")
        sys.exit(1)

    print(f"타겟 학회 수: {len(mapping)}")

    print("기존 papers_col 전체 삭제 중...")
    result = papers_col.delete_many({})
    print(f"삭제된 문서 수: {result.deleted_count}")

    parse_dblp(xml_path, mapping)

if __name__ == '__main__':
    main()
