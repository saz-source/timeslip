"""
Offline submission queue. Persists un-submitted entries to disk when
Autotask is unreachable, so they can be flushed on the next launch.
"""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

QUEUE_FILE = Path.home() / ".autotask_time_entry" / "offline_queue.json"


class OfflineQueue:
    def __init__(self):
        QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._items: list = self._load()

    def add(self, item: dict) -> str:
        item["id"] = str(uuid.uuid4())
        item["queued_at"] = datetime.now().isoformat()
        self._items.append(item)
        self._save()
        logger.info("Queued entry for %s", item.get("company_name"))
        return item["id"]

    def remove(self, item_id: str) -> None:
        self._items = [i for i in self._items if i.get("id") != item_id]
        self._save()

    def pending(self) -> list:
        return list(self._items)

    def count(self) -> int:
        return len(self._items)

    def _load(self) -> list:
        if QUEUE_FILE.exists():
            try:
                return json.loads(QUEUE_FILE.read_text())
            except Exception:
                logger.warning("Offline queue file corrupt; starting fresh.")
        return []

    def _save(self) -> None:
        try:
            QUEUE_FILE.write_text(json.dumps(self._items, indent=2))
        except Exception as exc:
            logger.error("Failed to write offline queue: %s", exc)
