import json
from datetime import timezone
from pathlib import Path

from loguru import logger

_log_path = Path("logs/tertulia.log")
_log_path.parent.mkdir(parents=True, exist_ok=True)


def _json_sink(message):
    record = message.record
    entry = {
        "timestamp": record["time"]
        .astimezone(timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        + "Z",
        "level": record["level"].name,
        "source": "tertulia",
        "message": record["message"],
    }
    with open(_log_path, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


logger.add(_json_sink, level="INFO")
