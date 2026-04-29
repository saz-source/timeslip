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
from html import escape as _esc

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


# ── HTML invoice ──────────────────────────────────────────────────────────────

_HTML_CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: 14px;
    color: #1a1a2e;
    background: #fff;
  }
  .invoice {
    max-width: 760px;
    margin: 40px auto;
    padding: 40px 48px;
    border: 1px solid #dde4ec;
    border-radius: 4px;
  }
  .header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 32px;
  }
  .company {
    font-size: 22px;
    font-weight: 700;
    color: #1a2a3a;
    letter-spacing: -0.3px;
  }
  .company-sub {
    font-size: 12px;
    color: #6b7a8d;
    margin-top: 4px;
  }
  .inv-meta { text-align: right; }
  .inv-number {
    font-size: 18px;
    font-weight: 600;
    color: #2c5f8a;
  }
  .inv-date {
    display: block;
    font-size: 12px;
    color: #6b7a8d;
    margin-top: 4px;
  }
  .inv-contact {
    display: block;
    font-size: 12px;
    color: #6b7a8d;
    margin-top: 2px;
  }
  .bill-to {
    background: #f7f9fc;
    border-left: 3px solid #2c5f8a;
    padding: 12px 16px;
    margin-bottom: 28px;
    border-radius: 0 4px 4px 0;
  }
  .bill-to-label {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #6b7a8d;
    margin-bottom: 4px;
  }
  .bill-to-name { font-size: 15px; font-weight: 600; }
  table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 28px;
  }
  thead th {
    background: #1a2a3a;
    color: #fff;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    padding: 9px 10px;
    text-align: left;
  }
  thead th.num { text-align: right; }
  tbody tr:nth-child(even) { background: #f7f9fc; }
  tbody td {
    padding: 9px 10px;
    border-bottom: 1px solid #eaeef3;
    vertical-align: top;
    line-height: 1.5;
  }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }
  tfoot td {
    padding: 12px 10px;
    font-weight: 700;
    font-size: 15px;
    border-top: 2px solid #1a2a3a;
    background: #e4ecf5;
  }
  tfoot td.num { text-align: right; }
  .payment {
    background: #f7f9fc;
    border: 1px solid #dde4ec;
    border-radius: 4px;
    padding: 16px 20px;
    margin-bottom: 28px;
  }
  .payment-title {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.7px;
    color: #6b7a8d;
    margin-bottom: 10px;
  }
  .payment-grid {
    display: grid;
    grid-template-columns: 140px 1fr;
    row-gap: 5px;
    font-size: 13px;
  }
  .payment-label { color: #6b7a8d; }
  .payment-value { color: #1a2a3a; font-weight: 500; }
  .payment-value.due { color: #2c5f8a; font-weight: 600; }
  .notes { margin-top: 8px; }
  .notes h3 {
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.7px;
    color: #6b7a8d;
    margin-bottom: 14px;
    border-bottom: 1px solid #eaeef3;
    padding-bottom: 6px;
  }
  .note-block { margin-bottom: 16px; }
  .note-date {
    font-weight: 600;
    font-size: 12px;
    color: #2c5f8a;
    margin-bottom: 4px;
  }
  .note-block p { color: #3a4a5a; line-height: 1.65; margin-top: 4px; }
  .footer {
    margin-top: 36px;
    padding-top: 14px;
    border-top: 1px solid #eaeef3;
    font-size: 11px;
    color: #9aabb8;
    text-align: center;
  }
"""


def _render_html(client_name: str, invoice_number: int,
                 entries: list[dict], generated: str) -> str:
    from datetime import date as _date, timedelta
    due_date = (_date.fromisoformat(generated) + timedelta(days=15)).isoformat()

    sorted_entries = sorted(entries, key=lambda x: x["date"])
    total_hours = sum(e["duration_hours"] for e in entries)
    total_amount = sum(e["billable_amount"] for e in entries)

    row_html = ""
    for e in sorted_entries:
        row_html += (
            f"<tr>"
            f"<td>{_esc(e['date'])}</td>"
            f"<td>{_esc(e['generated_title'])}</td>"
            f"<td class='num'>{e['duration_hours']:.2f}</td>"
            f"<td class='num'>${e['billable_rate']:.2f}</td>"
            f"<td class='num'>${e['billable_amount']:.2f}</td>"
            f"</tr>\n"
        )

    notes_html = ""
    note_blocks = []
    for e in sorted_entries:
        summary = e.get("generated_summary", "").strip()
        if summary:
            paras = "".join(
                f"<p>{_esc(line)}</p>"
                for line in summary.splitlines()
                if line.strip()
            )
            note_blocks.append(
                f"<div class='note-block'>"
                f"<div class='note-date'>{_esc(e['date'])} — {_esc(e['generated_title'])}</div>"
                f"{paras}"
                f"</div>"
            )
    if note_blocks:
        notes_html = (
            "<div class='notes'><h3>Work Details</h3>"
            + "".join(note_blocks)
            + "</div>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Invoice #{invoice_number} — {_esc(client_name)}</title>
<style>{_HTML_CSS}</style>
</head>
<body>
<div class="invoice">
  <div class="header">
    <div>
      <div class="company">Foothill Systems</div>
      <div class="company-sub">Secure by Design</div>
    </div>
    <div class="inv-meta">
      <div class="inv-number">Invoice #{invoice_number}</div>
      <span class="inv-date">Date: {_esc(generated)}</span>
      <span class="inv-contact">mike@foothill.systems</span>
      <span class="inv-contact">(323) 372-6644</span>
    </div>
  </div>

  <div class="bill-to">
    <div class="bill-to-label">Bill To</div>
    <div class="bill-to-name">{_esc(client_name)}</div>
  </div>

  <table>
    <thead>
      <tr>
        <th>Date</th>
        <th>Description</th>
        <th class="num">Hours</th>
        <th class="num">Rate</th>
        <th class="num">Amount</th>
      </tr>
    </thead>
    <tbody>
      {row_html}
    </tbody>
    <tfoot>
      <tr>
        <td colspan="2">Total</td>
        <td class="num">{total_hours:.2f}</td>
        <td></td>
        <td class="num">${total_amount:.2f}</td>
      </tr>
    </tfoot>
  </table>

  <div class="payment">
    <div class="payment-title">Payment Information</div>
    <div class="payment-grid">
      <span class="payment-label">Payment Terms</span>
      <span class="payment-value">Net 15</span>
      <span class="payment-label">Payment Due</span>
      <span class="payment-value due">{_esc(due_date)}</span>
      <span class="payment-label">Payment Methods</span>
      <span class="payment-value">Zelle / ACH / Check</span>
      <span class="payment-label">Contact</span>
      <span class="payment-value">mike@foothill.systems</span>
    </div>
  </div>

  {notes_html}

  <div class="footer">Foothill Systems — Thank you for your business.</div>
</div>
</body>
</html>
"""


# ── Email draft ───────────────────────────────────────────────────────────────

def _render_email_draft(client_name: str, invoice_number: int,
                        entries: list[dict], generated: str,
                        pdf_path: str | None, html_path: str,
                        csv_path: str) -> str:
    from datetime import date as _date, timedelta
    due_date = (_date.fromisoformat(generated) + timedelta(days=15)).isoformat()
    total_amount = sum(e["billable_amount"] for e in entries)

    # Primary attachment: PDF if available, otherwise fall back to HTML
    primary_attachment = os.path.basename(pdf_path if pdf_path else html_path)

    return (
        f"Subject: Foothill Systems Invoice #{invoice_number}\n"
        f"\n"
        f"Hi {client_name},\n"
        f"\n"
        f"Please find attached invoice #{invoice_number} for recent Foothill Systems support work.\n"
        f"\n"
        f"Total: ${total_amount:.2f}\n"
        f"Payment Terms: Net 15\n"
        f"Payment Due: {due_date}\n"
        f"\n"
        f"Please let me know if you have any questions.\n"
        f"\n"
        f"Thanks,\n"
        f"Mike\n"
        f"Foothill Systems\n"
        f"Secure by Design\n"
        f"mike@foothill.systems\n"
        f"(323) 372-6644\n"
        f"\n"
        f"Attachments to send:\n"
        f"- {primary_attachment}\n"
        f"\n"
        f"Internal reference:\n"
        f"- HTML: {html_path}\n"
        f"- CSV:  {csv_path}\n"
    )


# ── PDF export ─────────────────────────────────────────────────────────────────

def _find_chromium() -> str | None:
    """Return the path to the ms-playwright Chromium binary, or None."""
    import glob
    pattern = os.path.expanduser(
        "~/Library/Caches/ms-playwright/chromium-*/chrome-mac"
        "/Chromium.app/Contents/MacOS/Chromium"
    )
    matches = sorted(glob.glob(pattern))  # sort so highest version is last
    return matches[-1] if matches else None


def _write_pdf(html_path: str, pdf_path: str) -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning(
            "Playwright not installed — skipping PDF.\n"
            "  pip install playwright\n"
            "  python -m playwright install chromium"
        )
        return False
    try:
        chromium_path = _find_chromium()
        if chromium_path:
            logger.info("Using Chromium at: %s", chromium_path)
        else:
            logger.info("Chromium not found in ms-playwright cache — using Playwright default")

        file_url = "file://" + os.path.abspath(html_path)
        launch_kwargs = {"executable_path": chromium_path} if chromium_path else {}
        with sync_playwright() as pw:
            browser = pw.chromium.launch(**launch_kwargs)
            page = browser.new_page()
            page.goto(file_url, wait_until="networkidle")
            page.pdf(path=pdf_path, format="A4", print_background=True)
            browser.close()
        logger.info("PDF generated: %s", pdf_path)
        return True
    except Exception as exc:
        msg = str(exc)
        if "Executable doesn't exist" in msg or "playwright install" in msg.lower():
            logger.warning(
                "Playwright browser binaries missing — skipping PDF.\n"
                "  python -m playwright install chromium"
            )
        else:
            logger.warning("PDF generation failed: %s", exc)
        return False


# ── Main export ────────────────────────────────────────────────────────────────

def export_unbilled() -> list[dict]:
    """
    Export all unbilled Foothill entries.

    Returns a list of export records:
        {"client_name", "invoice_number", "txt_path", "csv_path",
         "html_path", "pdf_path", "email_path", "entry_count"}
        pdf_path is None if PDF generation was skipped or failed.

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

        txt_path   = os.path.join(_EXPORTS_DIR, f"{prefix}.txt")
        csv_path   = os.path.join(_EXPORTS_DIR, f"{prefix}.csv")
        html_path  = os.path.join(_EXPORTS_DIR, f"{prefix}.html")
        pdf_path   = os.path.join(_EXPORTS_DIR, f"{prefix}.pdf")
        email_path = os.path.join(_EXPORTS_DIR, f"{prefix}_email.txt")

        # Write TXT, CSV, HTML before advancing invoice state
        with open(txt_path, "w") as f:
            f.write(_render_text(client_name, inv_num, entries, generated))
        _write_csv(csv_path, client_name, inv_num, entries)
        with open(html_path, "w") as f:
            f.write(_render_html(client_name, inv_num, entries, generated))

        # PDF is best-effort — HTML is already written so it's never lost
        pdf_ok = _write_pdf(html_path, pdf_path)

        # Email draft written after PDF so it can reference the pdf_path correctly
        with open(email_path, "w") as f:
            f.write(_render_email_draft(
                client_name, inv_num, entries, generated,
                pdf_path if pdf_ok else None, html_path, csv_path,
            ))

        _increment_invoice_number()
        pending_marks.append(([e["entry_id"] for e in entries], inv_num))

        exports.append({
            "client_name": client_name,
            "invoice_number": inv_num,
            "txt_path": txt_path,
            "csv_path": csv_path,
            "html_path": html_path,
            "pdf_path": pdf_path if pdf_ok else None,
            "email_path": email_path,
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
            print(f"  TXT:  {r['txt_path']}")
            print(f"  CSV:  {r['csv_path']}")
            print(f"  HTML:  {r['html_path']}")
            if r["pdf_path"]:
                print(f"  PDF:   {r['pdf_path']}")
            else:
                print("  PDF:   (skipped — see log for details)")
            print(f"  EMAIL: {r['email_path']}")
        print(f"\n{len(results)} invoice(s) exported.")
