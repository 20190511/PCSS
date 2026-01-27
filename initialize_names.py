from pymongo import MongoClient
import os
from dotenv import load_dotenv 
import socket
load_dotenv()

DB_NAME = "pcss"
COLLECTION_NAME = "llm_names"

SSH_HOST = os.getenv("SSH_HOST")
SSH_PORT = int(os.getenv("SSH_PORT", 22))
SSH_USER = os.getenv("SSH_USER")
SSH_KEY = os.getenv("SSH_KEY")

# MongoDB 설정
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_AUTH_DB = os.getenv("MONGO_AUTH_DB", "admin")

hostname = socket.gethostname()
is_server = ("knpu" in hostname or "server" in hostname)  # 서버 이름 기준으로 판단

if is_server:
    # 서버 내부에서 실행 → 로컬 MongoDB 바로 사용
    client = MongoClient(
        f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
        f"@localhost:{MONGO_PORT}/?authSource={MONGO_AUTH_DB}"
    )
else:
    import warnings
    warnings.filterwarnings("ignore", module="paramiko")
    from sshtunnel import SSHTunnelForwarder
    # 외부에서 실행 → SSH 터널 사용
    server = SSHTunnelForwarder(
        (SSH_HOST, SSH_PORT),
        ssh_username=SSH_USER,
        ssh_pkey=SSH_KEY,
        remote_bind_address=(MONGO_HOST, MONGO_PORT)
    )
    server.start()

    client = MongoClient(
        f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
        f"@127.0.0.1:{server.local_bind_port}/?authSource={MONGO_AUTH_DB}"
    )
    
mongo_db = client[DB_NAME]
name_col = mongo_db[COLLECTION_NAME]
errors_col = mongo_db['errors']
conf_col = mongo_db["conferences"]
papers_col = mongo_db["papers"]
dblp_col = mongo_db['dblp']
log_col = mongo_db['logs']
req_korean_col = mongo_db['req_korean']
subscription_col = mongo_db['subscription']
auth_col = mongo_db['auth']
admin_col = mongo_db['admin']
board_notice_col = mongo_db['board_notice']
board_bug_col = mongo_db['board_bug']
authors_col = mongo_db['authors']

import json

json_file_path = os.path.join(os.path.dirname(__file__), 'llm_name.json')
with open(json_file_path, 'r', encoding='utf-8') as f:
    json_data = json.load(f)

json_names = {item['name'] for item in json_data}

db_names = set()
for doc in name_col.find({}, {"_id": 0, "name": 1}):
    if "name" in doc:
        db_names.add(doc["name"])

names_to_delete = list(db_names - json_names)

if names_to_delete:
    chunk_size = 1000
    total_deleted = 0
    for i in range(0, len(names_to_delete), chunk_size):
        chunk = names_to_delete[i:i + chunk_size]
        result = name_col.delete_many({"name": {"$in": chunk}})
        total_deleted += result.deleted_count
    
    print(f"삭제 완료: {total_deleted}개의 데이터가 삭제되었습니다.")
else:
    print("삭제할 데이터가 없습니다.")

if not is_server:
    server.stop()