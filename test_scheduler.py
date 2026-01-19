import os
import asyncio
from datetime import datetime, timezone
from app.db import subscription_col, papers_col
from app.services.subscription_service import SubscriptionNotifier
from app.data import name_dict

# ======================================================
# [설정] DB에 저장된 본인의 이메일 주소를 입력하세요.
TARGET_EMAIL = "yojun313@postech.ac.kr"
# ======================================================

async def test_existing_user_subscription():
    print(f"=== [실제 구독 정보 기반] 테스트 시작: {TARGET_EMAIL} ===")

    # 1. 내 구독 정보 가져오기
    my_sub = subscription_col.find_one({"email": TARGET_EMAIL})
    if not my_sub:
        print(f"[Error] '{TARGET_EMAIL}'에 해당하는 구독 정보가 DB에 없습니다.")
        return

    my_confs = my_sub.get("conferences", [])
    if not my_confs:
        print("[Error] 구독한 학회가 하나도 없습니다. DB를 확인해주세요.")
        return

    print(f"[Check] 구독 중인 학회: {my_confs}")

    # 2. 구독한 학회 중 실제 논문 몇 개만 찾기 (최대 3개)
    target_papers = list(papers_col.find(
        {"conference": {"$in": my_confs}},
        limit=3
    ))

    if not target_papers:
        print(f"[Error] 구독하신 학회({my_confs})에 해당하는 논문 데이터가 DB에 하나도 없습니다.")
        return

    print(f"[Check] 테스트용으로 사용할 실제 논문 {len(target_papers)}개를 찾았습니다.")

    # 백업용 리스트
    backup_data = []

    print("[Setup] 논문 날짜를 '현재'로 잠시 변경하고, 저자를 '한국인'으로 설정합니다...")
    
    for paper in target_papers:
        pid = paper["_id"]
        original_created_at = paper.get("created_at")
        
        authors = paper.get("author_names", [])
        first_author = authors[0] if authors else None
        
        backup_data.append({
            "id": pid,
            "original_created_at": original_created_at,
            "author": first_author,
            "original_score": name_dict.get(first_author) if first_author else None
        })

        # DB 업데이트: created_at = 지금
        papers_col.update_one(
            {"_id": pid},
            {"$set": {"created_at": datetime.now(timezone.utc)}}
        )

        # 메모리 해킹: 1저자 한국인(1.0) 설정
        if first_author:
            name_dict[first_author] = 1.0

    # =================================================================
    # [핵심 수정] DB 조회를 가로채서(Monkey Patch) 60만 개 대신 3개만 리턴하게 함
    # =================================================================
    original_find = papers_col.find  # 원래 함수 백업

    def mock_find(*args, **kwargs):
        # 어떤 쿼리가 들어오든 우리가 준비한 3개 논문 리스트만 반환
        return target_papers

    # 함수 바꿔치기
    papers_col.find = mock_find
    # =================================================================

    try:
        # 4. Notifier 실행
        print("\n[Action] Notifier 가동! (이메일 발송 시도)")
        
        notifier = SubscriptionNotifier()
        await notifier.run()
        
        print("[Action] Notifier 실행 완료. 메일함을 확인하세요.")

    except Exception as e:
        print(f"\n[Error] 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # [중요] DB 함수 원상복구
        papers_col.find = original_find

        # 5. [복구 단계] 데이터 원상복구
        print("\n[Cleanup] 변경한 논문 날짜와 점수를 원상복구합니다...")
        
        for item in backup_data:
            pid = item["id"]
            orig_date = item["original_created_at"]
            author = item["author"]
            orig_score = item["original_score"]

            if orig_date:
                papers_col.update_one({"_id": pid}, {"$set": {"created_at": orig_date}})
            else:
                papers_col.update_one({"_id": pid}, {"$unset": {"created_at": ""}})

            if author:
                if orig_score is not None:
                    name_dict[author] = orig_score
                else:
                    if author in name_dict:
                        del name_dict[author]

        print("[Cleanup] 복구 완료. DB는 안전합니다.")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_existing_user_subscription())