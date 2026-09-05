import logging
import os

_level = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    level=getattr(logging, _level, logging.INFO),
)

log = logging.getLogger("recruit")
