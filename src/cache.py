"""
Local JSON cache for non-sensitive lookup data.
Stores work types, resource ID, priority ID, onsite/offsite mapping,
recent companies, submission history, window geometry, and last client.
Never stores secrets or credentials.
"""
import json
import logging
from datetime import datetime, date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from src.autotask_client import AutotaskClient, WorkType

logger = logging.getLogger(__name__)

CACHE_FILE = Path.home() / ".autotask_time_entry" / "cache.json"
HISTORY_FILE = Path.home() / ".autotask_time_entry" / "history.json"

ONSITE_KEYWORDS = {"onsite", "on-site", "on site", "in-person", "in person", "went to", "drove to"}
OFFSITE_KEYWORDS = {"remote", "offsite", "off-site", "off site", "rdp", "teamviewer", "zoom", "called", "phone", "remotely", "remoted"}


class Cache:
    def __init__(self) -> None:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict = self._load()
        self._history: list = self._load_history()

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    @property
    def is_populated(self) -> bool:
        return bool(
            self._data.get("work_types")
            and self._data.get("resource_id")
            and self._data.get("priority_medium_id")
        )

    def populate(self, autotask: AutotaskClient, on_status=None) -> None:
        def status(msg, done=False):
            logger.info(msg)
            if on_status:
                on_status(msg, done)

        status("Authenticating with Autotask…")
        resource_id = autotask.get_my_resource_id()
        status(f"✓  Authenticated  (Resource ID: {resource_id})", True)

        status("Fetching work types…")
        work_types = autotask.get_work_types()
        status(f"✓  {len(work_types)} work types loaded", True)

        status("Loading priority settings…")
        priority_id = autotask.get_priority_medium_id()
        status(f"✓  Priority Medium = {priority_id}", True)

        status("Validating queue…")
        queue_valid = autotask.validate_queue(autotask._config.queue_id)
        status(f"✓  Queue ID {autotask._config.queue_id} confirmed", True)

        self._data["resource_id"] = resource_id
        self._data["work_types"] = [{"id": wt.id, "name": wt.name} for wt in work_types]
        self._data["priority_medium_id"] = priority_id
        self._data["queue_valid"] = queue_valid

        if "onsite_work_type_id" not in self._data or "offsite_work_type_id" not in self._data:
            status("Mapping work modes…")
            self._auto_map_work_modes(work_types)
            status("✓  Onsite / Offsite work types mapped", True)

        self._save()

    def get_work_types(self) -> list:
        return [WorkType(id=d["id"], name=d["name"]) for d in self._data.get("work_types", [])]

    def get_resource_id(self) -> int:
        return int(self._data["resource_id"])

    def get_priority_medium_id(self) -> int:
        return int(self._data.get("priority_medium_id", 2))

    def get_onsite_work_type_id(self) -> Optional[int]:
        v = self._data.get("onsite_work_type_id")
        return int(v) if v is not None else None

    def get_offsite_work_type_id(self) -> Optional[int]:
        v = self._data.get("offsite_work_type_id")
        return int(v) if v is not None else None

    def set_onsite_work_type_id(self, wt_id: int) -> None:
        self._data["onsite_work_type_id"] = wt_id
        self._save()

    def set_offsite_work_type_id(self, wt_id: int) -> None:
        self._data["offsite_work_type_id"] = wt_id
        self._save()

    # ------------------------------------------------------------------
    # Window geometry
    # ------------------------------------------------------------------

    def get_window_geometry(self) -> Optional[str]:
        return self._data.get("window_geometry")

    def set_window_geometry(self, geometry: str) -> None:
        self._data["window_geometry"] = geometry
        self._save()

    # ------------------------------------------------------------------
    # Last client
    # ------------------------------------------------------------------

    def get_last_client(self) -> str:
        return self._data.get("last_client", "")

    def set_last_client(self, name: str) -> None:
        self._data["last_client"] = name
        self._save()

    # ------------------------------------------------------------------
    # Recent companies
    # ------------------------------------------------------------------

    def get_recent_companies(self) -> list:
        return self._data.get("recent_companies", [])

    def add_recent_company(self, company_id: int, company_name: str) -> None:
        recent = [c for c in self._data.get("recent_companies", [])
                  if c["id"] != company_id]
        recent.insert(0, {"id": company_id, "name": company_name})
        self._data["recent_companies"] = recent[:20]
        self._save()

    # ------------------------------------------------------------------
    # Submission history
    # ------------------------------------------------------------------

    def add_history_entry(self, company_id: int, company_name: str,
                          ticket_id: int, ticket_number: str,
                          time_entry_id: int, title: str,
                          work_date: str, start_time: str,
                          duration_hours: float, work_mode: str) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "company_id": company_id,
            "company_name": company_name,
            "ticket_id": ticket_id,
            "ticket_number": ticket_number,
            "time_entry_id": time_entry_id,
            "title": title,
            "work_date": work_date,
            "start_time": start_time,
            "duration_hours": duration_hours,
            "work_mode": work_mode,
        }
        self._history.insert(0, entry)
        self._history = self._history[:100]  # keep last 100
        self._save_history()

    def get_history(self) -> list:
        return self._history

    def check_duplicate(self, company_id: int, work_date: str) -> Optional[dict]:
        """Return existing entry if same company + date already submitted today."""
        for entry in self._history:
            if (entry.get("company_id") == company_id and
                    entry.get("work_date") == work_date):
                return entry
        return None

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def clear(self) -> None:
        self._data = {}
        self._save()

    @staticmethod
    def infer_work_mode_from_notes(notes: str) -> str:
        lower = notes.lower()
        if any(kw in lower for kw in ONSITE_KEYWORDS):
            return "onsite"
        if any(kw in lower for kw in OFFSITE_KEYWORDS):
            return "offsite"
        return "unknown"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    # Known-good billing code IDs for JDK Consulting
    _KNOWN_ONSITE_ID  = 29682800
    _KNOWN_OFFSITE_ID = 29682801

    def _auto_map_work_modes(self, work_types: list) -> None:
        wt_ids = {wt.id for wt in work_types}

        # Prefer hardcoded known-good IDs; fall back to fuzzy match
        onsite_id = (self._KNOWN_ONSITE_ID if self._KNOWN_ONSITE_ID in wt_ids
                     else self._best_match(work_types, ONSITE_KEYWORDS))
        offsite_id = (self._KNOWN_OFFSITE_ID if self._KNOWN_OFFSITE_ID in wt_ids
                      else self._best_match(work_types, OFFSITE_KEYWORDS))

        if onsite_id:
            self._data["onsite_work_type_id"] = onsite_id
        if offsite_id:
            self._data["offsite_work_type_id"] = offsite_id
        logger.info("Auto-mapped onsite=%s, offsite=%s", onsite_id, offsite_id)

    @staticmethod
    def _best_match(work_types: list, keywords: set) -> Optional[int]:
        best_score = 0.0
        best_id = None
        for wt in work_types:
            name_lower = wt.name.lower()
            for kw in keywords:
                score = SequenceMatcher(None, kw, name_lower).ratio()
                if score > best_score:
                    best_score = score
                    best_id = wt.id
        return best_id if best_score > 0.4 else None

    def _load(self) -> dict:
        if CACHE_FILE.exists():
            try:
                return json.loads(CACHE_FILE.read_text())
            except Exception:
                logger.warning("Cache file corrupt; starting fresh.")
        return {}

    def _save(self) -> None:
        try:
            CACHE_FILE.write_text(json.dumps(self._data, indent=2))
        except Exception as exc:
            logger.error("Failed to write cache: %s", exc)

    def _load_history(self) -> list:
        if HISTORY_FILE.exists():
            try:
                return json.loads(HISTORY_FILE.read_text())
            except Exception:
                pass
        return []

    def _save_history(self) -> None:
        try:
            HISTORY_FILE.write_text(json.dumps(self._history, indent=2))
        except Exception as exc:
            logger.error("Failed to write history: %s", exc)
