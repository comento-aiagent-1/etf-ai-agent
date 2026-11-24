"""Reuse a MongoDB connection pool across Streamlit reruns."""
import atexit
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import OperationFailure

BASE_DIR = Path(__file__).resolve().parents[2]
LOG_TIMEOUT_MS = 2000
DEFAULT_LOG_RETENTION_DAYS = 90
# MongoDB 오류 코드: 같은 필드에 옵션이 다른 인덱스가 이미 있음
INDEX_OPTIONS_CONFLICT = (85, 86)


def get_log_retention_days():
    """로그 보관 기간(일). .env의 LOG_RETENTION_DAYS로 바꿀 수 있습니다."""
    load_dotenv(BASE_DIR / ".env")
    days = int(os.getenv("LOG_RETENTION_DAYS", str(DEFAULT_LOG_RETENTION_DAYS)))
    if days < 1:
        raise ValueError("LOG_RETENTION_DAYS must be 1 or more")
    return days


@lru_cache(maxsize=1)
def get_mongo_client():
    load_dotenv(BASE_DIR / ".env")
    # 로그 전용 계정(MONGO_APP_*)이 있으면 관리자 계정 대신 사용합니다.
    username = os.getenv("MONGO_APP_USERNAME") or os.getenv(
        "MONGO_ROOT_USERNAME", "etf_admin"
    )
    password = os.getenv("MONGO_APP_PASSWORD") or os.getenv(
        "MONGO_ROOT_PASSWORD", "local_mongo_password"
    )
    client = MongoClient(
        host=os.getenv("MONGO_HOST", "127.0.0.1"),
        port=int(os.getenv("MONGO_PORT", "27017")),
        username=username,
        password=password,
        authSource=os.getenv("MONGO_AUTH_SOURCE", "admin"),
        tz_aware=True,
        serverSelectionTimeoutMS=LOG_TIMEOUT_MS,
        connectTimeoutMS=LOG_TIMEOUT_MS,
        socketTimeoutMS=LOG_TIMEOUT_MS,
        timeoutMS=LOG_TIMEOUT_MS,
        appname="etf-ai-agent",
    )
    atexit.register(client.close)
    return client


@lru_cache(maxsize=1)
def get_log_collection():
    client = get_mongo_client()
    collection = client[os.getenv("MONGO_DB", "etf_agent")]["request_logs"]
    ensure_log_retention(collection)
    return collection


def ensure_log_retention(collection):
    """created_at 기준으로 보관 기간이 지난 로그를 MongoDB가 자동 삭제하게 합니다."""
    seconds = get_log_retention_days() * 24 * 60 * 60
    try:
        collection.create_index("created_at", expireAfterSeconds=seconds)
    except OperationFailure as error:
        if error.code not in INDEX_OPTIONS_CONFLICT:
            raise
        # 예전 일반 인덱스나 다른 보관 기간이 있으면 그 인덱스를 고쳐 씁니다.
        collection.database.command(
            "collMod",
            collection.name,
            index={"keyPattern": {"created_at": 1}, "expireAfterSeconds": seconds},
        )
