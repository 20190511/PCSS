import os
import time
import asyncio
import traceback
from datetime import datetime
from dateutil.relativedelta import relativedelta
import tool.extract_authors as extract_authors
import tool.extract_papers as extract_papers
from app.services.subscription_service import SubscriptionNotifier

def run_job():
    """
    1. DBLP XML 파일 정리
    2. 논문 추출 (DB 적재)
    3. 저자 추출 (DB 적재)
    4. [New] 구독자 이메일 알림 발송
    """
    xml_path = os.path.join(os.path.dirname(__file__), "dblp.xml")
    
    # 1~3단계: 데이터 업데이트
    steps = [
        ("DBLP XML 정리", lambda: extract_papers.cleanup_files(xml_path) if os.path.exists(xml_path) else None),
        ("논문 추출", extract_papers.main),
        ("저자 추출", extract_authors.main),
    ]

    print(f"\n[{datetime.now()}] === 월간 업데이트 작업 시작 ===")

    for name, func in steps:
        print(f"[{datetime.now()}] {name} 시작...")
        try:
            func()
            print(f"[{datetime.now()}] {name} 완료.")
        except Exception as e:
            print(f"!!! {name} 중 에러 발생: {e}")
            traceback.print_exc()

    # 4단계: 구독 알림 발송 (비동기 함수를 동기로 실행)
    print(f"[{datetime.now()}] 구독 알림 발송 서비스 시작...")
    try:
        notifier = SubscriptionNotifier()
        # 여기서 asyncio.run()을 호출하여 비동기인 notifier.run()을 실행
        asyncio.run(notifier.run())
        print(f"[{datetime.now()}] 구독 알림 발송 완료.")
    except Exception as e:
        print(f"!!! 구독 알림 발송 중 에러 발생: {e}")
        traceback.print_exc()

    print(f"[{datetime.now()}] === 모든 작업 종료 ===\n")


def next_monthly_run(now: datetime) -> datetime:
    """
    다음 실행 시각 계산: 매달 1일 00:00:00
    """
    candidate = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # 이미 지났으면 다음 달 1일로 설정
    if candidate <= now:
        candidate = candidate + relativedelta(months=1)
    return candidate


def format_timedelta(seconds: int) -> str:
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    return f"{days}일 {hours}시간 {minutes}분"


def main():
    print("=== DBLP Scheduler & Notifier Started ===")
    print("매달 1일 00:00에 데이터 갱신 및 구독 메일을 발송합니다.\n")

    # [옵션] 테스트를 위해 실행 직후 한 번 바로 돌리려면 아래 주석 해제
    # run_job()

    while True:
        now = datetime.now()
        target_time = next_monthly_run(now)
        wait_seconds = int((target_time - now).total_seconds())

        print(f"현재 시각: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"다음 실행: {target_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"대기 시간: {format_timedelta(wait_seconds)}")
        print("대기 중... (Ctrl+C로 종료)")

        # 긴 대기시간 동안 1분마다 체크하며 sleep
        while wait_seconds > 0:
            sleep_sec = min(60, wait_seconds)
            time.sleep(sleep_sec)
            wait_seconds -= sleep_sec

        # 대기 종료 후 작업 실행
        run_job()


if __name__ == "__main__":
    main()