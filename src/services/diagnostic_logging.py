"""Log exception types and source locations without exception contents."""
import traceback
from pathlib import Path


def log_safe_exception(logger, stage, error):
    frames = traceback.extract_tb(error.__traceback__)
    location = " <- ".join(
        f"{Path(frame.filename).name}:{frame.lineno} in {frame.name}"
        for frame in frames[-8:]
    ) or "unknown"
    logger.error(
        "%s failed (type=%s, location=%s)",
        stage,
        type(error).__name__,
        location,
    )
