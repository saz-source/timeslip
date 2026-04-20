#!/usr/bin/env python3
"""
Autotask Time Entry App — Pre-flight Connection Test
=====================================================
Run this before launching the app for the first time, or after changing credentials.

Usage:
    python test_connection.py               # full test suite
    python test_connection.py --autotask    # Autotask checks only
    python test_connection.py --anthropic   # Anthropic check only
    python test_connection.py --company "Acme Corp"  # also test a company search
"""
import argparse
import json
import os
import sys
import textwrap
from datetime import datetime
from pathlib import Path

# ── Make src importable ──────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

import requests

# ── Colours (fall back gracefully if terminal doesn't support ANSI) ──────────
USE_COLOR = sys.stdout.isatty()

def green(s):  return f"\033[32m{s}\033[0m" if USE_COLOR else s
def red(s):    return f"\033[31m{s}\033[0m" if USE_COLOR else s
def yellow(s): return f"\033[33m{s}\033[0m" if USE_COLOR else s
def bold(s):   return f"\033[1m{s}\033[0m"  if USE_COLOR else s
def dim(s):    return f"\033[2m{s}\033[0m"  if USE_COLOR else s

PASS = green("  ✓ PASS")
FAIL = red("  ✗ FAIL")
WARN = yellow("  ⚠ WARN")
INFO = dim("  · INFO")


# ── Result collector ─────────────────────────────────────────────────────────
results: list[tuple[str, str, str]] = []   # (status, check_name, detail)

def record(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))
    label = {"PASS": PASS, "FAIL": FAIL, "WARN": WARN, "INFO": INFO}.get(status, INFO)
    print(f"{label}  {name}")
    if detail:
        for line in textwrap.wrap(detail, width=90):
            print(f"         {dim(line)}")


# ── Env var checks ───────────────────────────────────────────────────────────
def check_env_vars() -> bool:
    print(bold("\n── Environment Variables ──────────────────────────────────────────"))
    required = {
        "ANTHROPIC_API_KEY":        ("Anthropic", lambda v: v.startswith("sk-ant-")),
        "AUTOTASK_BASE_URL":        ("Autotask",  lambda v: v.startswith("https://")),
        "AUTOTASK_USERNAME":        ("Autotask",  lambda v: "@" in v),
        "AUTOTASK_SECRET":          ("Autotask",  lambda v: len(v) > 4),
        "AUTOTASK_INTEGRATION_CODE":("Autotask",  lambda v: len(v) > 4),
    }
    all_ok = True
    for var, (group, validator) in required.items():
        val = os.getenv(var, "")
        masked = f"{val[:4]}…{val[-4:]}" if len(val) > 10 else ("(set)" if val else "(empty)")
        if not val:
            record("FAIL", f"{var}", "Not set — check your .env file")
            all_ok = False
        elif not validator(val):
            record("WARN", f"{var}", f"Set but looks unusual: {masked}")
        else:
            record("PASS", f"{var}", f"Set  [{masked}]")
    return all_ok


# ── Autotask helpers ─────────────────────────────────────────────────────────
def _at_headers() -> dict:
    return {
        "APIIntegrationcode": os.environ["AUTOTASK_INTEGRATION_CODE"],
        "Username":           os.environ["AUTOTASK_USERNAME"],
        "Secret":             os.environ["AUTOTASK_SECRET"],
        "Content-Type":       "application/json",
    }

def _at_base() -> str:
    return os.environ["AUTOTASK_BASE_URL"].rstrip("/") + "/v1.0"

def _at_query(entity: str, filters: list, max_records: int = 10) -> dict:
    url = f"{_at_base()}/{entity}/query"
    r = requests.post(
        url,
        headers=_at_headers(),
        json={"filter": filters, "MaxRecords": max_records},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()

def _at_get(path: str) -> dict:
    url = f"{_at_base()}/{path}"
    r = requests.get(url, headers=_at_headers(), timeout=20)
    r.raise_for_status()
    return r.json()


# ── Autotask test suite ──────────────────────────────────────────────────────
def check_autotask(company_search=None) -> None:
    print(bold("\n── Autotask API ───────────────────────────────────────────────────"))

    # 1. Authentication — fetch my resource record
    try:
        username = os.environ.get("AUTOTASK_RESOURCE_EMAIL", os.environ["AUTOTASK_USERNAME"])
        resp = _at_query("Resources", [{"field": "email", "op": "eq", "value": username}])
        items = resp.get("items", [])
        if not items:
            record("FAIL", "Authentication / Resource lookup",
                   f"No Resource record found for '{username}'. "
                   "Check AUTOTASK_USERNAME — it must exactly match the Autotask login email.")
        else:
            r = items[0]
            resource_id = r["id"]
            name = f"{r.get('firstName', '')} {r.get('lastName', '')}".strip() or username
            record("PASS", "Authentication + Resource lookup",
                   f"Authenticated as: {name}  (Resource ID: {resource_id})")
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        record("FAIL", "Authentication",
               _http_hint(code, e))
        return   # no point continuing if auth fails
    except Exception as e:
        record("FAIL", "Authentication", str(e))
        return

    # 2. Queue ID validation
    try:
        queue_id = 29682833
        resp = _at_query("Queues", [{"field": "id", "op": "eq", "value": queue_id}])
        items = resp.get("items", [])
        if items:
            q = items[0]
            record("PASS", f"Queue ID {queue_id} exists",
                   f"Name: {q.get('name', '(unknown)')}")
        else:
            record("FAIL", f"Queue ID {queue_id} not found",
                   "The Level 1 Support queue ID may differ in your instance. "
                   "Check Admin → Queues in Autotask and update QUEUE_ID in src/config.py.")
    except Exception as e:
        record("WARN", "Queue validation failed", str(e))

    # 3. Work types (BillingCodes)
    try:
        resp = _at_query(
            "BillingCodes",
            [{"field": "isActive", "op": "eq", "value": True},
             {"field": "useType", "op": "eq", "value": 1}],
            max_records=50,
        )
        items = resp.get("items", [])
        if items:
            names = [i.get("name", str(i["id"])) for i in items[:8]]
            record("PASS", f"Work types (BillingCodes) — {len(items)} found",
                   "First 8: " + ", ".join(names))
            _check_work_mode_mapping(items)
        else:
            # Fallback: try without useType filter
            resp2 = _at_query(
                "BillingCodes",
                [{"field": "isActive", "op": "eq", "value": True}],
                max_records=50,
            )
            items2 = resp2.get("items", [])
            if items2:
                names = [i.get("name", str(i["id"])) for i in items2[:8]]
                record("WARN", f"Work types — useType=1 returned 0; fallback found {len(items2)}",
                       "The app will use the fallback. First 8: " + ", ".join(names))
                _check_work_mode_mapping(items2)
            else:
                record("FAIL", "Work types — no BillingCodes found",
                       "Check that billing codes exist and are active in Autotask.")
    except Exception as e:
        record("FAIL", "Work types lookup", str(e))

    # 4. Priority picklist
    try:
        resp = _at_get("Tickets/entityInformation/fields")
        fields = resp.get("fields", [])
        priority_field = next(
            (f for f in fields if f.get("name", "").lower() == "priority"), None
        )
        if priority_field:
            pv = priority_field.get("picklistValues", [])
            medium = next((p for p in pv if p.get("label", "").lower() == "medium"), None)
            if medium:
                record("PASS", f"Priority picklist — 'Medium' = {medium['value']}",
                       "All values: " + ", ".join(
                           f"{p['label']}={p['value']}" for p in pv if p.get("label")
                       ))
            else:
                labels = [p.get("label", "?") for p in pv]
                record("WARN", "Priority picklist — 'Medium' label not found",
                       f"Available labels: {labels}. The app will fall back to value 2. "
                       "Update get_priority_medium_id() if the label differs in your instance.")
        else:
            record("WARN", "Priority field not found in ticket entity info",
                   "The app will use priority value 2 as fallback.")
    except Exception as e:
        record("WARN", "Priority picklist fetch failed", f"{e}. App will use fallback value 2.")

    # 5. Ticket entity — confirm required fields exist
    try:
        resp = _at_get("Tickets/entityInformation/fields")
        fields = {f["name"].lower() for f in resp.get("fields", [])}
        wanted = {"title", "companyid", "status", "priority", "queueid", "description"}
        missing = wanted - fields
        if not missing:
            record("PASS", "Ticket entity fields — all required fields present")
        else:
            record("WARN", "Ticket entity fields — some expected fields missing",
                   f"Missing: {missing}. Field names may differ; check Autotask entity docs.")
    except Exception as e:
        record("WARN", "Ticket entity info unavailable", str(e))

    # 6. TimeEntry entity — check taskTypeLink values
    try:
        resp = _at_get("TimeEntries/entityInformation/fields")
        fields = resp.get("fields", [])
        ttl_field = next(
            (f for f in fields if f.get("name", "").lower() == "tasktypelink"), None
        )
        if ttl_field:
            pv = ttl_field.get("picklistValues", [])
            ticket_val = next(
                (p["value"] for p in pv
                 if "ticket" in p.get("label", "").lower()), None
            )
            all_vals = ", ".join(
                f"{p.get('label','?')}={p['value']}" for p in pv if p.get("label")
            )
            if ticket_val is not None:
                record(
                    "PASS" if str(ticket_val) == "2" else "WARN",
                    f"TimeEntry taskTypeLink — 'Ticket' = {ticket_val}",
                    f"All values: {all_vals}"
                    + ("" if str(ticket_val) == "2"
                       else f"\n  ⚠ App uses hardcoded 2 — update taskTypeLink in "
                            f"autotask_client.py to {ticket_val}"),
                )
            else:
                record("WARN", "TimeEntry taskTypeLink — no 'Ticket' label found",
                       f"All values: {all_vals}\n"
                       "Find the correct value and update taskTypeLink in autotask_client.py.")
        else:
            record("INFO", "TimeEntry taskTypeLink field not in entity info",
                   "App will use value 2. If time entry creation fails, check this field.")
    except Exception as e:
        record("WARN", "TimeEntry entity info unavailable", str(e))

    # 7. Optional: company search
    if company_search:
        print(bold(f"\n── Company Search: '{company_search}' ─────────────────────────────"))
        try:
            resp = _at_query(
                "Companies",
                [{"field": "companyName", "op": "contains", "value": company_search},
                 {"field": "isActive", "op": "eq", "value": True}],
                max_records=10,
            )
            items = resp.get("items", [])
            if items:
                record("PASS", f"Company search — {len(items)} match(es) found")
                for c in items:
                    record("INFO", f"  ID {c['id']}: {c.get('companyName', '?')}")
            else:
                record("WARN", f"No active companies matched '{company_search}'",
                       "Try a shorter search term. Company names must match exactly as in Autotask.")
        except Exception as e:
            record("FAIL", "Company search", str(e))


def _check_work_mode_mapping(items: list) -> None:
    """Hint which work types look like onsite vs offsite."""
    onsite_kw  = {"onsite", "on-site", "on site"}
    offsite_kw = {"remote", "offsite", "off-site", "off site"}

    onsite_matches  = [i.get("name", "") for i in items
                       if any(kw in i.get("name", "").lower() for kw in onsite_kw)]
    offsite_matches = [i.get("name", "") for i in items
                       if any(kw in i.get("name", "").lower() for kw in offsite_kw)]

    if onsite_matches:
        record("INFO", f"  Likely onsite work type(s): {onsite_matches}")
    else:
        record("WARN", "  No work type name contains 'onsite'/'on-site'",
               "The app will prompt you to map work types manually on first run.")

    if offsite_matches:
        record("INFO", f"  Likely offsite work type(s): {offsite_matches}")
    else:
        record("WARN", "  No work type name contains 'remote'/'offsite'",
               "The app will prompt you to map work types manually on first run.")


def _http_hint(code, exc):
    hints = {
        401: "Invalid credentials — check AUTOTASK_USERNAME, AUTOTASK_SECRET, AUTOTASK_INTEGRATION_CODE.",
        403: "Forbidden — your API user may lack permission for this entity.",
        404: "Endpoint not found — check AUTOTASK_BASE_URL (should end in /ATServicesRest/).",
        429: "Rate limited — wait a moment and try again.",
        500: "Autotask server error — may be a transient issue, try again.",
    }
    base = str(exc)[:200]
    hint = hints.get(int(code) if str(code).isdigit() else 0, "")
    return f"HTTP {code}: {base}" + (f"\n  Hint: {hint}" if hint else "")


# ── Anthropic test ───────────────────────────────────────────────────────────
def check_anthropic() -> None:
    print(bold("\n── Anthropic API ──────────────────────────────────────────────────"))
    try:
        import anthropic
    except ImportError:
        record("FAIL", "anthropic package not installed",
               "Run: pip install anthropic")
        return

    try:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        msg = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=300,
            system=(
                "You transform IT technician notes into professional Autotask entries. "
                "Respond ONLY with valid JSON — no markdown, no preamble.\n"
                '{"title":"...","summary":"...","work_mode":"onsite|offsite|unknown","confidence":0.0}'
            ),
            messages=[{
                "role": "user",
                "content": (
                    "Client: Acme Corp\nDuration: 1.0 hours\n\n"
                    "Raw notes:\nReplaced faulty keyboard on reception PC. Tested all keys. "
                    "Drove to site, in and out in 45 min."
                )
            }],
        )
        raw = msg.content[0].text.strip()

        # Validate JSON structure
        try:
            data = json.loads(raw)
            required_keys = {"title", "summary", "work_mode", "confidence"}
            missing = required_keys - set(data.keys())
            if missing:
                record("WARN", "Anthropic API reachable but JSON missing keys",
                       f"Missing: {missing}\nRaw response: {raw[:300]}")
            else:
                wm = data.get("work_mode", "?")
                wm_ok = wm in {"onsite", "offsite", "unknown"}
                record("PASS", "Anthropic API + JSON structure valid",
                       f"work_mode={wm} {'✓' if wm_ok else '⚠ unexpected value'}, "
                       f"confidence={data.get('confidence', '?')}")
                record("INFO", f"  Generated title: {data.get('title', '?')}")
        except json.JSONDecodeError:
            record("WARN", "Anthropic reachable but response was not JSON",
                   f"Raw: {raw[:300]}\nThe system prompt may need adjustment.")

    except Exception as e:
        msg = str(e)
        if "401" in msg or "authentication" in msg.lower():
            record("FAIL", "Anthropic authentication failed",
                   "Check ANTHROPIC_API_KEY — get one at console.anthropic.com")
        elif "insufficient_quota" in msg.lower() or "credit" in msg.lower():
            record("FAIL", "Anthropic account has no credits", str(e))
        else:
            record("FAIL", "Anthropic API error", str(e)[:300])


# ── Summary ──────────────────────────────────────────────────────────────────
def print_summary() -> None:
    print(bold("\n── Summary ────────────────────────────────────────────────────────"))
    counts = {"PASS": 0, "FAIL": 0, "WARN": 0, "INFO": 0}
    for status, name, _ in results:
        counts[status] = counts.get(status, 0) + 1

    total_checks = counts["PASS"] + counts["FAIL"] + counts["WARN"]
    passed = counts["PASS"]
    warned = counts["WARN"]
    failed = counts["FAIL"]
    print(f"  {green(f'{passed} passed')}   "
          f"{yellow(f'{warned} warnings')}   "
          f"{red(f'{failed} failed')}   "
          f"({total_checks} checks total)\n")

    fails = [(n, d) for s, n, d in results if s == "FAIL"]
    warns = [(n, d) for s, n, d in results if s == "WARN"]

    if fails:
        print(red("  Failures — must fix before running the app:"))
        for name, detail in fails:
            print(f"    • {name}")
            if detail:
                print(f"      {dim(detail[:120])}")
        print()

    if warns:
        print(yellow("  Warnings — review before first use:"))
        for name, detail in warns:
            print(f"    • {name}")
        print()

    if not fails:
        print(green("  ✓ Ready to run:  python main.py\n"))
    else:
        print(red("  ✗ Fix the failures above, then re-run this script.\n"))


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pre-flight connection test for the Autotask Time Entry app.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              python test_connection.py
              python test_connection.py --autotask
              python test_connection.py --anthropic
              python test_connection.py --company "JDK Consulting"
        """),
    )
    parser.add_argument("--autotask",  action="store_true", help="Autotask checks only")
    parser.add_argument("--anthropic", action="store_true", help="Anthropic check only")
    parser.add_argument("--company", metavar="NAME", help="Also run a company name search")
    args = parser.parse_args()

    run_all = not args.autotask and not args.anthropic

    print(bold(f"\nAutotask Time Entry — Connection Test  [{datetime.now():%Y-%m-%d %H:%M:%S}]"))
    print(dim("=" * 68))

    env_ok = check_env_vars()

    if not env_ok:
        print(red("\n  Missing env vars — fill in .env before continuing.\n"))
        sys.exit(1)

    if run_all or args.autotask:
        check_autotask(company_search=args.company)

    if run_all or args.anthropic:
        check_anthropic()

    print_summary()


if __name__ == "__main__":
    main()
