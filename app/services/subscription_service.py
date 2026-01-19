import asyncio
import os
import json
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.services.search_service import PCSSEARCHMongo
from app.db import subscription_col, papers_col
from app.core.templates import templates  

# [템플릿 에러 방지] 가짜 Request 객체 정의
class MockRequest:
    def __init__(self):
        self.headers = {}
        self.state = type("State", (), {"user": None})() 
        self.query_params = {}
        self.url = "https://pcss.r-e.kr"
        self.base_url = "https://pcss.r-e.kr"
        self.cookies = {}
        self.client = None

    def url_for(self, name, **kwargs):
        return f"/{name}"

class SubscriptionProcessor(PCSSEARCHMongo):
    def __init__(self, target_papers: list, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_papers = target_papers

    async def _fetch_papers(self, conf_list: list) -> list:
        return [p for p in self.target_papers if p.get("conference") in conf_list]

class SubscriptionNotifier:
    def __init__(self):
        self.mail_config = self._load_mail_config()
        self.option_map = {
            1: "1저자",
            2: "2저자",
            3: "마지막 저자",
            4: "기타 공저자",
        }

    def _load_mail_config(self):
        try:
            # 경로 조정
            path = os.path.join(os.path.dirname(__file__), "..", "data", "mail_lock.json")    
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Notifier] Mail config load failed: {e}")
            return None

    def _send_email_sync(self, receiver, title, html_body):
        if not self.mail_config:
            print(f"[Notifier] No mail config. Skipping email to {receiver}")
            return

        sender = self.mail_config['sender']
        password = self.mail_config['password']
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = title
        msg['From'] = sender
        msg['To'] = receiver
        
        # HTML 본문 추가
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        try:
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(sender, password)
                server.sendmail(sender, receiver, msg.as_string())
            print(f"[Notifier] Sent to {receiver}")
        except Exception as e:
            print(f"[Notifier] Fail {receiver}: {e}")

    # [수정] threshold 인자 추가
    def _generate_result_html(self, python_result: dict, options: list, threshold: float, manage_token: str):
        """
        router.get("/page/{job_id}")의 로직을 그대로 재현
        """
        selected_texts = []
        if options:
            for opt in options:
                try:
                    txt = self.option_map.get(int(opt))
                    if txt:
                        selected_texts.append(txt)
                except ValueError:
                    continue
        
        option_text = ", ".join(selected_texts) if selected_texts else "옵션 미선택"
        
        # [수정] 템플릿이 요구하는 데이터 구조를 맞춰줌 (uncertainty 등 추가)
        mock_options_obj = {
            "options": options,       # [1, 2] 형태의 리스트
            "uncertainty": threshold, # 템플릿의 options.uncertainty 대응
            "startyear": datetime.now().year, # 기본값 (에러 방지용)
            "endyear": datetime.now().year,   # 기본값 (에러 방지용)
            "countOption": False
        }

        context = {
            "request": MockRequest(),      
            "user": None,                  
            "options": mock_options_obj,   # [수정] 딕셔너리 교체
            "option_text": option_text,
            "pythonResult": python_result,
            "FASTAPI_BASE": "https://pcss.r-e.kr",
        }

        try:
            template = templates.env.get_template("search/results.html")
            html_content = template.render(**context)
            
            # 수신거부 링크 주입
            unsubscribe_link = f"<br><div style='text-align:center; color:#999; font-size:12px; margin-top:20px;'><a href='https://pcss.r-e.kr/subscriptions/manage?token={manage_token}'>구독 관리 / 수신 거부</a></div>"
            
            if "</body>" in html_content:
                html_content = html_content.replace("</body>", f"{unsubscribe_link}</body>")
            else:
                html_content += unsubscribe_link
                
            return html_content
        except Exception as e:
            print(f"[Notifier] Template render error: {e}")
            import traceback
            traceback.print_exc()
            return "<h1>Result Rendering Error</h1><p>관리자에게 문의해주세요.</p>"

    async def run(self):
        print("[Notifier] Start")
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=32)
        
        recent_papers_cursor = papers_col.find(
            {"created_at": {"$gte": cutoff_date}},
            {"_id": 0, "title": 1, "author_names": 1, "author_pids": 1, "conference": 1, "year": 1, "source": 1, "dblp_url": 1}
        )
        recent_papers = await asyncio.to_thread(lambda: list(recent_papers_cursor))
        
        if not recent_papers:
            print("[Notifier] No new papers.")
            return

        subs = list(subscription_col.find({"is_enabled": True}))
        print(f"[Notifier] Papers: {len(recent_papers)}, Subs: {len(subs)}")

        for sub in subs:
            email = sub["email"]
            confs = sub.get("conferences", [])
            options = sub.get("options", [1])
            threshold = sub.get("threshold", 0.8)
            manage_token = sub.get("manage_token", "")

            if not confs:
                continue
            
            processor = SubscriptionProcessor(
                target_papers=recent_papers,
                options=options,
                threshold=threshold,
                startyear=0, endyear=0, countOption=False
            )
            result_dict = await processor.run(confs)

            if result_dict:
                # [수정] threshold 인자 전달
                html_body = self._generate_result_html(result_dict, options, threshold, manage_token)
                title = f"[New Papers] {len(result_dict)}개의 새로운 관심 논문이 도착했습니다."
                
                await asyncio.to_thread(self._send_email_sync, email, title, html_body)