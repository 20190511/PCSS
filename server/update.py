import extract_authors
import extract_papers
import os
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta

from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.spinner import Spinner

console = extract_authors.console

def run_job():
    xml_path = os.path.join(os.path.dirname(__file__), "dblp.xml")

    steps = [
        ("DBLP XML 정리", lambda: extract_papers.cleanup_files(xml_path) if os.path.exists(xml_path) else None),
        ("논문 추출", extract_papers.main),
        ("저자 추출", extract_authors.main),
    ]

    for name, func in steps:
        with console.status(f"[bold cyan]{name} 실행 중...[/bold cyan]", spinner="dots"):
            func()
        console.print(f"[green]완료:[/green] {name}")


def seconds_until_next_run(now: datetime) -> int:
    next_run = now + relativedelta(months=1)
    return int((next_run - now).total_seconds())


def format_timedelta(seconds: int) -> str:
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    return f"{days}d {hours}h {minutes}m"


def main():
    console.print(
        Panel.fit(
            "[bold]DBLP Monthly Extractor[/bold]\n"
            "논문 / 저자 정보 월 1회 자동 갱신",
            border_style="blue"
        )
    )

    while True:
        start_time = datetime.now()

        console.print(
            Panel(
                f"[bold yellow]작업 시작[/bold yellow]\n{start_time.strftime('%Y-%m-%d %H:%M:%S')}",
                border_style="yellow"
            )
        )

        try:
            run_job()
            console.print("[bold green]모든 작업 성공적으로 완료[/bold green]")
        except Exception as e:
            console.print("[bold red]작업 중 오류 발생[/bold red]")
            console.print_exception()

        wait_seconds = seconds_until_next_run(datetime.now())
        next_run_time = datetime.now() + relativedelta(months=1)

        table = Table(show_header=False, box=None)
        table.add_row("다음 실행 시각:", next_run_time.strftime("%Y-%m-%d %H:%M:%S"))
        table.add_row("남은 시간:", format_timedelta(wait_seconds))

        console.print(Panel(table, title="대기 상태", border_style="cyan"))

        # 1분 단위로 sleep (Ctrl+C 대응 + 상태 유지)
        while wait_seconds > 0:
            time.sleep(min(60, wait_seconds))
            wait_seconds -= 60


if __name__ == "__main__":
    main()
