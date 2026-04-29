"""
Foothill Systems invoice export.

Usage:
    python -m src.foothill_invoice_export

Reads unbilled entries from foothill_entries.json, groups by client, writes
one .txt and one .csv per client under foothill_exports/, then marks entries
as invoiced. Invoice numbers are tracked in foothill_invoice_state.json.
"""
import csv
import json
import logging
import os
from collections import defaultdict
from datetime import date

from src.foothill_storage import load_entries, mark_invoiced

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.expanduser("~/.autotask_time_entry")
_EXPORTS_DIR = os.path.join(_DATA_DIR, "foothill_exports")
_STATE_FILE = os.path.join(_DATA_DIR, "foothill_invoice_state.json")

_STARTING_INVOICE = 1002


# ── Invoice state ──────────────────────────────────────────────────────────────

def _load_state() -> dict:
    if not os.path.exists(_STATE_FILE):
        return {"next_invoice_number": _STARTING_INVOICE}
    try:
        with open(_STATE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("invoice state unreadable, resetting: %s", exc)
        return {"next_invoice_number": _STARTING_INVOICE}


def _save_state(state: dict) -> None:
    with open(_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _next_invoice_number() -> int:
    return _load_state()["next_invoice_number"]


def _increment_invoice_number() -> None:
    state = _load_state()
    state["next_invoice_number"] += 1
    _save_state(state)


# ── Text invoice ───────────────────────────────────────────────────────────────

def _render_text(client_name: str, invoice_number: int,
                 entries: list[dict], generated: str) -> str:
    lines = [
        "=" * 64,
        "  Foothill Systems",
        f"  Invoice #{invoice_number}",
        "=" * 64,
        f"  Client:   {client_name}",
        f"  Date:     {generated}",
        "",
        f"  {'Date':<12}  {'Title':<28}  {'Hrs':>5}  {'Rate':>7}  {'Amount':>9}",
        "  " + "-" * 62,
    ]

    total_hours = 0.0
    total_amount = 0.0

    for e in sorted(entries, key=lambda x: x["date"]):
        d = e["date"]
        title = e["generated_title"][:28]
        hrs = e["duration_hours"]
        rate = e["billable_rate"]
        amount = e["billable_amount"]
        total_hours += hrs
        total_amount += amount
        lines.append(
            f"  {d:<12}  {title:<28}  {hrs:>5.2f}  ${rate:>6.2f}  ${amount:>8.2f}"
        )

    lines += [
        "  " + "-" * 62,
        f"  {'Total':<42}  {total_hours:>5.2f}           ${total_amount:>8.2f}",
        "",
    ]

    for e in sorted(entries, key=lambda x: x["date"]):
        title = e["generated_title"]
        summary = e.get("generated_summary", "").strip()
        if summary:
            lines.append(f"  [{e['date']}]  {title}")
            for para in summary.splitlines():
                lines.append(f"    {para}")
            lines.append("")

    lines.append("=" * 64)
    return "\n".join(lines) + "\n"


# ── CSV invoice ────────────────────────────────────────────────────────────────

def _write_csv(path: str, client_name: str, invoice_number: int,
               entries: list[dict]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "invoice_number", "client_name", "date", "title", "summary",
            "hours", "rate", "amount", "work_mode", "entry_id",
        ])
        for e in sorted(entries, key=lambda x: x["date"]):
            w.writerow([
                invoice_number,
                client_name,
                e["date"],
                e["generated_title"],
                e.get("generated_summary", ""),
                e["duration_hours"],
                e["billable_rate"],
                e["billable_amount"],
                e.get("work_mode", ""),
                e["entry_id"],
            ])


# ── Main export ────────────────────────────────────────────────────────────────

def export_unbilled() -> list[dict]:
    """
    Export all unbilled Foothill entries.

    Returns a list of export records:
        {"client_name", "invoice_number", "txt_path", "csv_path", "entry_count"}

    Raises on any I/O error before entries are marked invoiced.
    """
    all_entries = load_entries()
    unbilled = [e for e in all_entries if e.get("status") == "unbilled"]

    if not unbilled:
        logger.info("No unbilled Foothill entries found.")
        return []

    # Group by client_id, preserving the canonical client_name from first entry
    groups: dict[str, list[dict]] = defaultdict(list)
    client_names: dict[str, str] = {}
    for e in unbilled:
        cid = e["client_id"]
        groups[cid].append(e)
        client_names.setdefault(cid, e["client_name"])

    os.makedirs(_EXPORTS_DIR, exist_ok=True)
    generated = date.today().isoformat()

    exports = []
    # Write all files before touching entry status — collect (entry_ids, invoice_number) pairs
    pending_marks: list[tuple[list[str], int]] = []

    for cid, entries in groups.items():
        inv_num = _next_invoice_number()
        client_name = client_names[cid]
        prefix = f"invoice_{inv_num}_{cid}_{generated}"

        txt_path = os.path.join(_EXPORTS_DIR, f"{prefix}.txt")
        csv_path = os.path.join(_EXPORTS_DIR, f"{prefix}.csv")

        txt_content = _render_text(client_name, inv_num, entries, generated)

        # Write both files atomically before advancing state
        with open(txt_path, "w") as f:
            f.write(txt_content)
        _write_csv(csv_path, client_name, inv_num, entries)

        _increment_invoice_number()
        pending_marks.append(([e["entry_id"] for e in entries], inv_num))

        exports.append({
            "client_name": client_name,
            "invoice_number": inv_num,
            "txt_path": txt_path,
            "csv_path": csv_path,
            "entry_count": len(entries),
        })

    # All files written successfully — now mark entries as invoiced
    for entry_ids, inv_num in pending_marks:
        mark_invoiced(entry_ids, inv_num)

    return exports


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    results = export_unbilled()

    if not results:
        print("No unbilled entries to export.")
    else:
        for r in results:
            print(f"\nInvoice #{r['invoice_number']}  —  {r['client_name']}")
            print(f"  {r['entry_count']} entr{'y' if r['entry_count'] == 1 else 'ies'}")
            print(f"  TXT: {r['txt_path']}")
            print(f"  CSV: {r['csv_path']}")
        print(f"\n{len(results)} invoice(s) exported.")
