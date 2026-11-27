"""OpenAI embeddings shared by indexing and retrieval."""
import hashlib
import json
import math
import os

from dotenv import load_dotenv
from openai import OpenAI

from src.db.postgres import BASE_DIR

MODEL = "text-embedding-3-large"
DIMENSIONS = 1536


def document_text(row):
    """Stable, complete representation of source fields (excluding timestamps)."""
    values = {key: value for key, value in row.items()
              if key not in ("created_at", "updated_at") and value is not None}
    return json.dumps(values, ensure_ascii=False, sort_keys=True, default=str)


def chunks(text):
    # At most 4,000 UTF-8 bytes per chunk, safely below the model token limit.
    return [text[start:start + 1000] for start in range(0, len(text), 900)]


def content_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def embed_texts(texts):
    if not texts:
        return []
    if any(not text.strip() or len(text) > 1000 for text in texts):
        raise ValueError("Embedding input must contain 1-1000 characters per item")
    load_dotenv(BASE_DIR / ".env")
    with OpenAI(timeout=20, max_retries=1) as client:
        response = client.embeddings.create(
            model=MODEL, dimensions=DIMENSIONS, input=texts,
        )
    items = sorted(response.data, key=lambda item: item.index)
    if [item.index for item in items] != list(range(len(texts))):
        raise ValueError("Incomplete embedding response")
    vectors = [item.embedding for item in items]
    for vector in vectors:
        if len(vector) != DIMENSIONS or not all(math.isfinite(v) for v in vector) or not any(vector):
            raise ValueError("Invalid embedding vector")
    return vectors


def minimum_similarity():
    load_dotenv(BASE_DIR / ".env")
    threshold = float(os.getenv("FAQ_MIN_SIMILARITY", "0.55"))
    if not 0 <= threshold <= 1:
        raise ValueError("FAQ_MIN_SIMILARITY must be between 0 and 1")
    return threshold
