"""Best-effort request logging; database failures never replace an answer."""
import logging
from datetime import datetime, timezone
from uuid import uuid4

import pymongo
from pymongo.errors import PyMongoError

from src.db.mongo import LOG_TIMEOUT_MS, get_log_collection
from src.services.diagnostic_logging import log_safe_exception

logger = logging.getLogger(__name__)


def save_request_log(*, question, elapsed_seconds, result, used_tools,
                     status="success", error_type=None):
    document = {
        "_id": str(uuid4()),
        "created_at": datetime.now(timezone.utc),
        "question": question,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "result": result,
        "status": status,
        "error_type": error_type,
        "used_tools": list(used_tools),
        "used_etf_api": "get_etf_price" in used_tools,
    }
    try:
        # Includes index initialization and insertion in one time budget.
        with pymongo.timeout(LOG_TIMEOUT_MS / 1000):
            get_log_collection().insert_one(document)
        return True
    except (PyMongoError, ValueError, TypeError, OSError) as error:
        log_safe_exception(logger, "MongoDB request-log write", error)
        return False
