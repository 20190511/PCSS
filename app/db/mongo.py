# app/db/mongo_async.py
import os
import asyncio
from typing import Optional
import platform
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection

load_dotenv()

DB_NAME = os.getenv("DB_NAME", "pcss")

# 컬렉션 이름(네 기존 그대로)
COLLECTION_NAMES = {
    "llm_names": os.getenv("LLM_NAMES_COLLECTION", "llm_names"),
    "errors": os.getenv("ERRORS_COLLECTION", "errors"),
    "conferences": os.getenv("CONFERENCES_COLLECTION", "conferences"),
    "papers": os.getenv("PAPERS_COLLECTION", "papers"),
}

SSH_HOST = os.getenv("SSH_HOST")
SSH_PORT = int(os.getenv("SSH_PORT", 22))
SSH_USER = os.getenv("SSH_USER")
SSH_KEY  = os.getenv("SSH_KEY")

MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_AUTH_DB = os.getenv("MONGO_AUTH_DB", "admin")


_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None

# SSH 터널 전역(로컬에서만 사용)
_tunnel = None
_tunnel_local_port: Optional[int] = None


def _is_server() -> bool:
    is_server = platform.system() == "Linux" and os.path.exists("/etc/os-release") and "ubuntu" in open("/etc/os-release").read().lower()
    return is_server


def _build_mongo_uri(host: str, port: int) -> str:
    # authSource 포함
    # (주의) password에 특수문자 있으면 URL 인코딩 필요할 수 있음
    return (
        f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
        f"@{host}:{port}/?authSource={MONGO_AUTH_DB}"
    )


async def _ensure_tunnel_started() -> int:
    """
    로컬 환경에서 SSH 터널을 1번만 열고 local_bind_port를 반환.
    start()가 블로킹이라 to_thread로 실행.
    """
    global _tunnel, _tunnel_local_port

    if _tunnel_local_port is not None:
        return _tunnel_local_port

    # 서버 환경이면 터널 필요 없음
    if _is_server():
        _tunnel_local_port = MONGO_PORT
        return _tunnel_local_port

    # 로컬 환경: SSH 터널 오픈
    import warnings
    warnings.filterwarnings("ignore", module="paramiko")
    from sshtunnel import SSHTunnelForwarder

    if not (SSH_HOST and SSH_USER and SSH_KEY):
        raise RuntimeError("SSH tunnel required but SSH_HOST/SSH_USER/SSH_KEY is missing in env")

    def _start():
        nonlocal SSHTunnelForwarder
        t = SSHTunnelForwarder(
            (SSH_HOST, SSH_PORT),
            ssh_username=SSH_USER,
            ssh_pkey=SSH_KEY,
            remote_bind_address=(MONGO_HOST, MONGO_PORT),
        )
        t.start()
        return t

    _tunnel = await asyncio.to_thread(_start)
    _tunnel_local_port = int(_tunnel.local_bind_port)
    return _tunnel_local_port


async def get_mongo_client() -> AsyncIOMotorClient:
    """
    AsyncIOMotorClient를 싱글턴으로 생성.
    로컬이면 SSH 터널을 열고 127.0.0.1:<local_port>로 접속.
    """
    global _client

    if _client is not None:
        return _client

    if _is_server():
        uri = _build_mongo_uri("localhost", MONGO_PORT)
        _client = AsyncIOMotorClient(uri)
        return _client

    local_port = await _ensure_tunnel_started()
    uri = _build_mongo_uri("127.0.0.1", local_port)
    _client = AsyncIOMotorClient(uri)
    return _client


async def get_db() -> AsyncIOMotorDatabase:
    global _db
    if _db is not None:
        return _db
    client = await get_mongo_client()
    _db = client[DB_NAME]
    return _db


async def get_collection(name: str) -> AsyncIOMotorCollection:
    db = await get_db()
    return db[name]


# ---- 편의: 네가 기존처럼 papers_col 이런식으로 쓰고 싶다면 ----
async def get_name_col() -> AsyncIOMotorCollection:
    return await get_collection(COLLECTION_NAMES["llm_names"])

async def get_errors_col() -> AsyncIOMotorCollection:
    return await get_collection(COLLECTION_NAMES["errors"])

async def get_conf_col() -> AsyncIOMotorCollection:
    return await get_collection(COLLECTION_NAMES["conferences"])

async def get_papers_col() -> AsyncIOMotorCollection:
    return await get_collection(COLLECTION_NAMES["papers"])
