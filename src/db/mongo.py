"""Reuse a MongoDB connection pool across Streamlit reruns."""
import atexit
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

BASE_DIR = Path(__file__).resolve().parents[2]
LOG_TIMEOUT_MS = 2000


@lru_cache(maxsize=1)
def get_mongo_client():
    load_dotenv(BASE_DIR / ".env")
    client = MongoClient(
        host=os.getenv("MONGO_HOST", "127.0.0.1"),
        port=int(os.getenv("MONGO_PORT", "27017")),
        username=os.getenv("MONGO_ROOT_USERNAME", "etf_admin"),
        password=os.getenv("MONGO_ROOT_PASSWORD", "local_mongo_password"),
        authSource="admin",
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
    collection.create_index("created_at")
    return collection
