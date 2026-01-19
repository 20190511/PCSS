from lxml import etree
import os
import sys
from datetime import datetime, timezone
from pymongo import UpdateOne
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    SpinnerColumn,
)
from rich.console import Console

# ---------------------------------------------------------------------------
# [DB 설정]
# authors 컬렉션만 가져옵니다. (점수 저장용 컬렉션과는 분리됨을 가정)
# ---------------------------------------------------------------------------
try:
    from app.db import authors_col  # author_col = db["authors"]
except ImportError:
    # 테스트용: app.db가 없을 경우를 대비한 더미 설정 (실제 환경에선 삭제하세요)
    from pymongo import MongoClient
    client = MongoClient("mongodb://localhost:27017")
    authors_col = client["pcss"]["authors"]

# =========================
# 설정
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
xml_path = os.path.join(BASE_DIR, "dblp.xml")
BATCH_SIZE = 2000 
console = Console()

def _extract_pid_from_homepages_key(key: str) -> str | None:
    """
    DBLP key format: "homepages/k/Knuth" -> PID: "k/Knuth"
    """
    if not key:
        return None
    key = key.strip()
    if not key.startswith("homepages/"):
        return None
    # "homepages/" (10글자) 제거
    pid = key[10:].strip()
    return pid or None

def extract_authors_basic_info(xml_path: str):
    abs_xml_path = os.path.abspath(xml_path)
    xml_dir = os.path.dirname(abs_xml_path)
    filename_only = os.path.basename(abs_xml_path)
    dtd_path = os.path.join(xml_dir, "dblp.dtd")

    if not os.path.exists(dtd_path):
        console.print(f"[bold red]DTD 파일 없음:[/bold red] {dtd_path}")
        return

    original_cwd = os.getcwd()
    os.chdir(xml_dir)

    # ---------------------------------------------------------
    # 동기화 마커: 이번 실행 시각
    # 이 시각으로 업데이트되지 않은 데이터는 XML에서 삭제된 저자로 간주
    # ---------------------------------------------------------
    run_ts = datetime.now(timezone.utc)

    batch_ops = []
    saved_count = 0
    
    # 통계용
    total_upserted = 0
    total_modified = 0
    
    context = None
    completed = False

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold green]저자 기본 정보(PID, Name) 추출 중[/bold green]"),
        BarColumn(),
        TextColumn("saved: {task.fields[saved]}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    )

    try:
        # DTD 로드 (Parse 안정성 확보)
        etree.DTD(file=dtd_path)
        console.print("[green]DTD 로드 성공[/green]")

        context = etree.iterparse(
            filename_only,
            events=("end",),
            load_dtd=True,
            huge_tree=True,
            recover=True,
        )

        with progress:
            task_id = progress.add_task("extract", total=None, saved=0)

            for event, elem in context:
                # DBLP 인명 정보는 <www> 태그 중 title이 "Home Page"인 것
                if elem.tag == "www":
                    title = elem.findtext("title")
                    if title != "Home Page":
                        _clear_element(elem)
                        continue

                    # 1. PID 추출
                    key = elem.get("key")
                    pid = _extract_pid_from_homepages_key(key)
                    
                    if not pid:
                        _clear_element(elem)
                        continue

                    # 2. 이름 추출 (author 태그가 여러 개면 alias임)
                    # 첫 번째 author를 대표 이름(primary name)으로 간주
                    authors = [a.text.strip() for a in elem.findall("author") if a.text]
                    
                    if not authors:
                        _clear_element(elem)
                        continue

                    primary_name = authors[0]

                    # 3. 소속(Affiliation) 추출 (부가 정보)
                    affiliations = []
                    for note in elem.findall("note"):
                        if note.get("type") == "affiliation" and note.text:
                            affiliations.append(note.text.strip())

                    saved_count += 1
                    progress.update(task_id, saved=saved_count)

                    # -------------------------------------------------
                    # [DB 저장 로직]
                    # 점수(Score) 관련 필드는 건드리지 않고,
                    # 신원 정보(Identity)만 Upsert 합니다.
                    # -------------------------------------------------
                    now = datetime.now(timezone.utc)
                    
                    update_doc = {
                        "name": primary_name,       # 대표 이름
                        "aliases": authors,         # 이명(Alias) 리스트
                        "affiliations": affiliations,
                        "dblp_key": key,
                        "updated_at": now,
                        "last_seen_at": run_ts,     # 동기화 마커
                    }

                    batch_ops.append(
                        UpdateOne(
                            {"pid": pid},  # PID를 고유 키로 사용
                            {
                                "$set": update_doc,
                                # 생성 시점에만 넣을 데이터
                                "$setOnInsert": {
                                    "created_at": now
                                }
                            },
                            upsert=True,
                        )
                    )

                    # 배치 실행
                    if len(batch_ops) >= BATCH_SIZE:
                        res = authors_col.bulk_write(batch_ops, ordered=False)
                        total_upserted += res.upserted_count
                        total_modified += res.modified_count
                        batch_ops.clear()

                    _clear_element(elem)

                elif elem.tag == "dblp":
                    _clear_element(elem)

            # 남은 배치 처리
            if batch_ops:
                res = authors_col.bulk_write(batch_ops, ordered=False)
                total_upserted += res.upserted_count
                total_modified += res.modified_count
                batch_ops.clear()

        completed = True

    except Exception:
        console.print("[bold red]추출 중 치명적 오류 발생[/bold red]")
        import traceback
        console.print(traceback.format_exc())

    finally:
        os.chdir(original_cwd)
        if context:
            del context

    console.print(
        f"[bold green]완료[/bold green]: "
        f"총 [bold]{saved_count}[/bold]명 처리 "
        f"(신규: {total_upserted}, 갱신: {total_modified})"
    )

    # ---------------------------------------------------------
    # [동기화 삭제]
    # 이번 실행(run_ts)에 갱신되지 않은 데이터는
    # DBLP XML에서 삭제된 저자이므로 DB에서도 제거합니다.
    # ---------------------------------------------------------
    if completed:
        del_res = authors_col.delete_many({"last_seen_at": {"$ne": run_ts}})
        if del_res.deleted_count > 0:
            console.print(f"[yellow]동기화[/yellow]: 삭제된 저자 {del_res.deleted_count}명 정리 완료")
    else:
        console.print("[dim]비정상 종료로 인해 삭제 단계 건너뜀[/dim]")

def _clear_element(elem):
    """메모리 누수 방지를 위한 요소 정리"""
    elem.clear()
    while elem.getprevious() is not None:
        del elem.getparent()[0]

def main():
    print("=== DBLP 저자 기본 정보 추출 (Score 제외) ===")
    if not os.path.exists(xml_path):
        console.print(f"[red]DBLP XML 없음:[/red] {xml_path}")
        sys.exit(1)

    extract_authors_basic_info(xml_path)

if __name__ == "__main__":
    main()