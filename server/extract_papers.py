from lxml import etree
from app.db import conf_col, papers_col
import os
import urllib.parse
import re
import sys
import requests
import gzip
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
xml_path = os.path.join(BASE_DIR, "dblp.xml")

BATCH_SIZE = 1000  # MongoDB bulk insert 크기
console = Console()


# =========================
# Params 기반 룰 파싱/로딩
# =========================
def _parse_param_to_rule(param: str, conf_name: str) -> dict | None:
    """
    conf_col.params에 들어갈 수 있는 문자열을 룰로 변환.
      - "pldi"                : base=pldi (그 venue_id 전체 매칭)
      - "pacmpl:PLDI"         : base=pacmpl + article의 number="PLDI"일 때만 매칭
      - "pacmmod:3:1"         : base=pacmmod + article의 volume="3" and number="1"
      - "pacmmod:3:1:2025"    : base=pacmmod + volume/number/year 모두 일치
      - "crossref:...."       : elem.crossref가 정확히 일치할 때 매칭 (원하면 사용)
    """
    if not param:
        return None

    raw = param.strip()
    if not raw:
        return None

    low = raw.lower()

    # crossref 매칭 (옵션)
    if low.startswith("crossref:"):
        return {
            "kind": "crossref",
            "base": "__crossref__",
            "crossref": low[len("crossref:") :].strip(),
            "conf": conf_name,
            "specificity": 100,
            "raw": raw,
        }

    parts = [p.strip() for p in raw.split(":") if p.strip()]
    if not parts:
        return None

    base = parts[0].lower()

    # "pldi"
    if len(parts) == 1:
        return {
            "kind": "base",
            "base": base,
            "conf": conf_name,
            "specificity": 10,
            "raw": raw,
        }

    # "pacmpl:PLDI" -> article number 트랙
    if len(parts) == 2:
        return {
            "kind": "track",
            "base": base,
            "number": parts[1].lower(),
            "conf": conf_name,
            "specificity": 50,
            "raw": raw,
        }

    # "pacmmod:3:1" -> article volume/number 이슈
    if len(parts) == 3:
        return {
            "kind": "issue",
            "base": base,
            "volume": parts[1],  # 문자열로 비교 (DBLP XML도 문자열)
            "number": parts[2].lower(),
            "conf": conf_name,
            "specificity": 60,
            "raw": raw,
        }

    # "pacmmod:3:1:2025" -> article volume/number/year
    if len(parts) >= 4:
        return {
            "kind": "issue_year",
            "base": base,
            "volume": parts[1],
            "number": parts[2].lower(),
            "year": parts[3],
            "conf": conf_name,
            "specificity": 70,
            "raw": raw,
        }

    return None


def load_conference_rules_index() -> dict[str, list[dict]]:
    """
    반환: base(venue_id) -> [rule, rule, ...]
    rules는 specificity 높은 순으로 정렬되어 더 구체적인 규칙이 우선 적용됨.
    """
    conferences = conf_col.find({}, {"_id": 0, "params": 1, "name": 1})
    index: dict[str, list[dict]] = {}

    for conf in conferences:
        conf_name = conf.get("name")
        for p in (conf.get("params") or []):
            rule = _parse_param_to_rule(p, conf_name)
            if not rule:
                continue
            index.setdefault(rule["base"], []).append(rule)

    # 더 구체적인 규칙을 먼저 적용
    for base in list(index.keys()):
        index[base].sort(key=lambda r: r.get("specificity", 0), reverse=True)

    return index


def resolve_conf_name(elem, rules_index: dict[str, list[dict]]) -> str | None:
    """
    elem 하나를 보고 rules_index(params 기반 규칙들)로 어떤 conf인지 결정.
    - hardcoding 없이 rules_index(=DB에 저장된 params)로만 판단
    - 같은 base에 여러 규칙이 있으면 specificity 높은 규칙부터 적용
    """
    key = (elem.get("key") or "").strip()
    venue_id = None
    if key:
        parts = key.split("/")
        if len(parts) >= 2:
            venue_id = parts[1].lower()

    # crossref 규칙이 있으면 먼저 검사
    crossref = (elem.findtext("crossref") or "").strip().lower()
    if crossref and "__crossref__" in rules_index:
        for rule in rules_index["__crossref__"]:
            if rule["kind"] == "crossref" and crossref == rule["crossref"]:
                return rule["conf"]

    if not venue_id:
        return None

    rules = rules_index.get(venue_id)
    if not rules:
        return None

    # article에서 사용할 수 있는 정보
    number = (elem.findtext("number") or "").strip().lower()
    volume = (elem.findtext("volume") or "").strip()
    year = (elem.findtext("year") or "").strip()

    # 규칙 적용 (정렬되어 있으니 첫 매칭 리턴)
    for rule in rules:
        kind = rule["kind"]

        # base 규칙: venue_id만 맞으면 OK (inproceedings/article 둘 다 허용)
        if kind == "base":
            return rule["conf"]

        # 아래는 article에서만 의미 있음
        if elem.tag != "article":
            continue

        if kind == "track":
            # 예: pacmpl:PLDI -> elem.number == "PLDI"
            if number and number == rule["number"]:
                return rule["conf"]

        elif kind == "issue":
            # 예: pacmmod:3:1 -> elem.volume == "3" and elem.number == "1"
            if volume and number and volume == rule["volume"] and number == rule["number"]:
                return rule["conf"]

        elif kind == "issue_year":
            if (
                volume
                and number
                and year
                and volume == rule["volume"]
                and number == rule["number"]
                and year == rule["year"]
            ):
                return rule["conf"]

    return None


# =========================
# 메인 트랙 판별
# =========================
def is_main_track(elem, title, booktitle):
    if not title:
        return False

    title_lower = title.lower()
    booktitle_lower = booktitle.lower() if booktitle else ""

    key = elem.get("key", "").lower()
    crossref = elem.findtext("crossref")
    crossref_lower = crossref.lower() if crossref else ""

    # 구조적 필터
    indicators = ["workshop", "adjunct", "companion", "supplement"]
    for ind in indicators:
        if ind in key or ind in crossref_lower:
            return False

    venue_blacklist_patterns = [
        r"\bworkshops?\b",
        r"\btutorials?\b",
        r"\bdoctoral\b",
        r"\bconsortium\b",
        r"\badjunct\b",
        r"\bcompanion\b",
        r"\bdemo\b",
        r"\bdemonstrations?\b",
        r"\bposters?\b",
        r"\bshort papers?\b",
        r"\bphd symposium\b",
        r"\bextended abstracts?\b",
        r"\bchallenge\b",
        r"\bcompetitions?\b",
    ]

    title_blacklist_patterns = [
        r"\bmessage from\b",
        r"\bwelcome\b",
        r"\bpreface\b",
        r"\bforeword\b",
        r"\bkeynote\b",
        r"\bpanel\b",
        r"\bopening remarks\b",
        r"\bcommittee\b",
        r"\bauthor index\b",
        r"\breviewers\b",
        r"\bsession\b",
        r"\bpresentation\b",
        r"\bbest paper awards?\b",
        r"\bprogram\b",
        r"\bcall for papers\b",
    ]

    for pattern in venue_blacklist_patterns:
        if re.search(pattern, booktitle_lower):
            return False

    for pattern in title_blacklist_patterns:
        if re.search(pattern, title_lower):
            return False

    pages = elem.findtext("pages")
    if pages and re.match(r"^[ivxlcdm]+$", pages.lower()):
        return False

    return True


# =========================
# DBLP 파싱 & DB 적재
# =========================
def parse_dblp(xml_path, rules_index):
    paper_tags = {"inproceedings", "article"}

    abs_xml_path = os.path.abspath(xml_path)
    xml_dir = os.path.dirname(abs_xml_path)
    filename_only = os.path.basename(abs_xml_path)
    dtd_path = os.path.join(xml_dir, "dblp.dtd")

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
        transient=False,
    )

    try:
        context = etree.iterparse(
            filename_only,
            events=("end",),
            load_dtd=True,
            huge_tree=True,
            recover=True,
        )

        with progress:
            task_id = progress.add_task("parse", total=None, scan=0, saved=0)

            for event, elem in context:
                if elem.tag in paper_tags:
                    count += 1
                    progress.update(task_id, scan=count)

                    # params 기반으로 conf name resolve (하드코딩 없음)
                    official_conf_name = resolve_conf_name(elem, rules_index)
                    if not official_conf_name:
                        elem.clear()
                        while elem.getprevious() is not None:
                            del elem.getparent()[0]
                        continue

                    title = elem.findtext("title")
                    booktitle_xml = elem.findtext("booktitle")
                    venue_str = booktitle_xml if booktitle_xml else elem.findtext("journal")

                    if not is_main_track(elem, title, venue_str):
                        elem.clear()
                        while elem.getprevious() is not None:
                            del elem.getparent()[0]
                        continue

                    matched_count += 1
                    progress.update(task_id, saved=matched_count)

                    year = elem.findtext("year")

                    source = elem.findtext("ee")
                    if not source:
                        raw_url = elem.findtext("url")
                        if raw_url:
                            source = f"https://dblp.org/{raw_url}"

                    dblp_rel_path = elem.findtext("url")
                    if dblp_rel_path:
                        dblp_url = f"https://dblp.org/{dblp_rel_path}"
                    else:
                        key = elem.get("key")
                        dblp_url = f"https://dblp.org/rec/{key}.html" if key else ""

                    authors = []
                    author_urls = []
                    for author in elem.findall("author"):
                        if author.text:
                            authors.append(author.text)
                            pid = author.get("pid")
                            if pid:
                                author_urls.append(f"https://dblp.org/pid/{pid}")
                            else:
                                enc = urllib.parse.quote_plus(author.text)
                                author_urls.append(f"https://dblp.org/search/author?q={enc}")

                    record = {
                        "title": title,
                        "author_name": authors,
                        "author_url": author_urls,
                        "conference": official_conf_name,
                        "year": int(year) if year and year.isdigit() else year,
                        "source": source,
                        "dblp_url": dblp_url,
                        # ---- 추천: 추후 검증/디버깅용 메타 ----
                        "dblp_key": elem.get("key"),
                        "type": elem.tag,
                        "journal": elem.findtext("journal"),
                        "booktitle": elem.findtext("booktitle"),
                        "volume": elem.findtext("volume"),
                        "number": elem.findtext("number"),
                        "crossref": elem.findtext("crossref"),
                    }

                    batch_docs.append(record)

                    if len(batch_docs) >= BATCH_SIZE:
                        papers_col.insert_many(batch_docs, ordered=False)
                        batch_docs.clear()

                    elem.clear()
                    while elem.getprevious() is not None:
                        del elem.getparent()[0]

                elif elem.tag == "dblp":
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


# =========================
# 다운로드/압축해제
# =========================
def download_dblp_xml_gz(
    url: str = "https://dblp.uni-trier.de/xml/dblp.xml.gz",
    out_dir: str | Path = os.path.dirname(__file__),
    gz_name: str = "dblp.xml.gz",
    xml_name: str = "dblp.xml",
    chunk_size: int = 1024 * 1024,  # 1MB
) -> tuple[Path, Path]:
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
        console=console,
    )

    with progress:
        # 1) 다운로드
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("Content-Length", 0))

            download_task = progress.add_task("Downloading dblp.xml.gz", total=total_size)

            with open(gz_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        progress.update(download_task, advance=len(chunk))

        # 2) 압축 해제
        gz_size = gz_path.stat().st_size
        extract_task = progress.add_task("Extracting dblp.xml", total=gz_size)

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


# =========================
# main
# =========================
def main():
    print("=== DBLP 논문 추출 시작 ===")
    if not os.path.exists(os.path.join(os.path.dirname(__file__), "dblp.xml")):
        print("=== DBLP 데이터 다운로드 ===")
        download_dblp_xml_gz()

    print("학회 정보 로드 중...")
    rules_index = load_conference_rules_index()
    if not rules_index:
        print("학회 정보 로드 실패")
        sys.exit(1)

    # (참고) rules_index는 base별 룰 목록이라 "타겟 학회 수"는 conf 수와 다를 수 있음
    total_rules = sum(len(v) for v in rules_index.values())
    print(f"로드된 params(rule) 수: {total_rules}")

    print("기존 papers_col 전체 삭제 중...")
    result = papers_col.delete_many({})
    print(f"삭제된 문서 수: {result.deleted_count}")

    parse_dblp(xml_path, rules_index)


if __name__ == "__main__":
    main()
