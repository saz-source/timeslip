"""
Local storage for Foothill Systems billing entries.
Saves to ~/.autotask_time_entry/foothill_entries.json
"""
import json
import logging
import os
import re
import uuid
from datetime import date, datetime

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.expanduser("~/.autotask_time_entry")
_FILE = os.path.join(_DATA_DIR, "foothill_entries.json")


def _client_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _load() -> list:
    if not os.path.exists(_FILE):
        return []
    try:
        with open(_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("foothill_entries.json unreadable, starting fresh: %s", exc)
        return []


def load_entries() -> list:
    return _load()


def mark_invoiced(entry_ids: list[str], invoice_number: int) -> None:
    entries = _load()
    ids = set(entry_ids)
    for e in entries:
        if e["entry_id"] in ids:
            e["status"] = "invoiced"
            e["invoice_id"] = invoice_number
    with open(_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def save_entry(
    client_name: str,
    entry_date: date,
    start_dt: datetime,
    end_dt: datetime,
    duration_hours: float,
    raw_notes: str,
    title: str,
    summary: str,
    work_mode: str,
    billable_rate: float = 150.0,
) -> str:
    os.makedirs(_DATA_DIR, exist_ok=True)
    entries = _load()
    entry_id = str(uuid.uuid4())
    entries.append({
        "entry_id": entry_id,
        "billing_company": "Foothill Systems",
        "client_name": client_name,
        "client_id": _client_id(client_name),
        "date": entry_date.isoformat(),
        "start_time": start_dt.strftime("%H:%M"),
        "end_time": end_dt.strftime("%H:%M"),
        "duration_hours": duration_hours,
        "raw_notes": raw_notes,
        "generated_title": title,
        "generated_summary": summary,
        "work_mode": work_mode,
        "billable_rate": billable_rate,
        "billable_amount": round(billable_rate * duration_hours, 2),
        "status": "unbilled",
        "created_at": datetime.now().isoformat(),
    })
    with open(_FILE, "w") as f:
        json.dump(entries, f, indent=2)
    return entry_id
