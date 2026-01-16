import extract_authors
import extract_papers
import os
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta


def run_job():
    xml_path = os.path.join(os.path.dirname(__file__), "dblp.xml")

    steps = [
        ("DBLP XML 정리", lambda: extract_papers.cleanup_files(xml_path) if os.path.exists(xml_path) else None),
        ("논문 추출", extract_papers.main),
        ("저자 추출", extract_authors.main),
    ]

    for name, func in steps:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {name} 시작")
        func()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {name} 완료")


def seconds_until_next_run(now: datetime) -> int:
    next_run = now + relativedelta(months=1)
    return int((next_run - now).total_seconds())


def format_timedelta(seconds: int) -> str:
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    return f"{days}d {hours}h {minutes}m"


def main():
    print("=== DBLP Monthly Extractor ===")
    print("논문 / 저자 정보 월 1회 자동 갱신\n")

    while True:
        start_time = datetime.now()
        print(f"=== 작업 시작: {start_time.strftime('%Y-%m-%d %H:%M:%S')} ===")

        try:
            run_job()
            print("=== 모든 작업 성공적으로 완료 ===")
        except Exception:
            print("=== 작업 중 오류 발생 ===")
            import traceback
            traceback.print_exc()

        now = datetime.now()
        wait_seconds = seconds_until_next_run(now)
        next_run_time = now + relativedelta(months=1)

        print("\n=== 대기 상태 ===")
        print(f"다음 실행 시각: {next_run_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"남은 시간: {format_timedelta(wait_seconds)}")
        print("1분 단위로 대기합니다. (Ctrl+C로 종료)\n")

        while wait_seconds > 0:
            sleep_sec = min(60, wait_seconds)
            time.sleep(sleep_sec)
            wait_seconds -= sleep_sec


if __name__ == "__main__":
    main()
