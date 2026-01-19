import os
import asyncio
from datetime import datetime, timezone
from app.db import subscription_col, papers_col
from app.services.subscription_service import SubscriptionNotifier
from app.data import name_dict  # LLM 점수 캐시

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
    #    (이미 DB에 있는 논문을 가져옵니다)
    target_papers = list(papers_col.find(
        {"conference": {"$in": my_confs}},
        limit=3
    ))

    if not target_papers:
        print(f"[Error] 구독하신 학회({my_confs})에 해당하는 논문 데이터가 DB에 하나도 없습니다.")
        print("extract_papers를 실행해서 논문 데이터를 먼저 채워주세요.")
        return

    print(f"[Check] 테스트용으로 사용할 실제 논문 {len(target_papers)}개를 찾았습니다.")

    # 3. [조작 단계] Notifier가 '신규 논문'으로 인식하도록 날짜와 저자 점수 조작
    #    데이터를 훼손하지 않기 위해 변경 전 상태를 백업합니다.
    backup_data = []

    print("[Setup] 논문 날짜를 '현재'로 잠시 변경하고, 저자를 '한국인'으로 설정합니다...")
    
    for paper in target_papers:
        pid = paper["_id"]
        original_created_at = paper.get("created_at")
        
        # 저자 중 첫 번째 사람을 가져옴
        authors = paper.get("author_names", [])
        first_author = authors[0] if authors else None
        
        # 백업
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

        # 메모리 해킹: 1저자를 한국인(1.0점)으로 강제 설정 (LLM 호출 방지 및 필터 통과 보장)
        if first_author:
            name_dict[first_author] = 1.0

    try:
        # 4. Notifier 실행
        print("\n[Action] Notifier 가동! (이메일 발송 시도)")
        
        # 주의: Notifier는 DB의 모든 구독자를 훑지만, 
        # 우리가 날짜를 조작한 논문은 '내 구독 학회' 논문뿐이므로 나에게만 메일이 올 확률이 높습니다.
        notifier = SubscriptionNotifier()
        await notifier.run()
        
        print("[Action] Notifier 실행 완료. 메일함을 확인하세요.")

    except Exception as e:
        print(f"\n[Error] 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # 5. [복구 단계] DB와 메모리를 원래대로 되돌림
        print("\n[Cleanup] 변경한 논문 날짜와 점수를 원상복구합니다...")
        
        for item in backup_data:
            pid = item["id"]
            orig_date = item["original_created_at"]
            author = item["author"]
            orig_score = item["original_score"]

            # 날짜 복구
            if orig_date:
                papers_col.update_one({"_id": pid}, {"$set": {"created_at": orig_date}})
            else:
                papers_col.update_one({"_id": pid}, {"$unset": {"created_at": ""}})

            # 점수 복구
            if author:
                if orig_score is not None:
                    name_dict[author] = orig_score
                else:
                    # 원래 캐시에 없던 사람이면 삭제
                    if author in name_dict:
                        del name_dict[author]

        print("[Cleanup] 복구 완료. DB는 안전합니다.")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_existing_user_subscription())