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


def next_monthly_run(now: datetime) -> datetime:
    """
    다음 실행 시각: 매달 1일 00:00:00
    - 지금이 1일 00:00:00 이전이면 이번 달 1일 00:00:00 (이미 지났다면 아래에서 다음 달로 넘김)
    - 지금이 그 시각 이후면 다음 달 1일 00:00:00
    """
    # 이번 달 1일 00:00:00
    candidate = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 이미 지났으면 다음 달 1일 00:00:00
    if candidate <= now:
        candidate = candidate + relativedelta(months=1)

    return candidate


def seconds_until_next_run(now: datetime) -> int:
    target = next_monthly_run(now)
    return int((target - now).total_seconds())


def format_timedelta(seconds: int) -> str:
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    return f"{days}d {hours}h {minutes}m"


def main():
    print("=== DBLP Monthly Extractor ===")
    print("논문 / 저자 정보 매달 1일 00:00에 자동 갱신\n")

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
        next_run_time = next_monthly_run(now)
        wait_seconds = int((next_run_time - now).total_seconds())

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
