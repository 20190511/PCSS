from app.db import dblp_col

while True:
    title = input("논문 제목 입력: ")
    paper = dblp_col.find_one({"title": title}, {"_id": 0})
    
    if paper:
        print("\n--- 논문 정보 ---")
        for key, value in paper.items():
            print(f"{key}: {value}")
        print("----------------\n")
    else:
        print("해당 제목의 논문을 찾을 수 없습니다.\n") 