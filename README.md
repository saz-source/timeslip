# Autotask Time Entry App

A local macOS desktop app that converts raw work notes into professional Autotask Ticket + Time Entry drafts using Claude AI — with a mandatory review step before anything is submitted.

---

## Workflow

```
Raw notes → [AI Draft] → Review & Edit → [Approve] → Autotask Ticket + Time Entry
```

Nothing is created in Autotask until you click **Approve & Submit**.

> **API limitation:** Time entries are created in **New** status. You must approve/post them manually in the Autotask web UI.

---

## Prerequisites

- macOS 13+ (tested on 15.3.1)
- Python 3.11 or 3.12
- An Autotask account with API access + Integration Code
- An Anthropic API key

---

## Setup

### 1. Clone / download the project

```bash
cd ~/Developer   # or wherever you keep projects
# place the autotask_time_entry/ folder here
cd autotask_time_entry
```

### 2. Create a Python virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure credentials

```bash
cp .env.example .env
open -e .env    # or: nano .env
```

Fill in all five values:

| Variable | Where to find it |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `AUTOTASK_BASE_URL` | Your zone URL, e.g. `https://webservices5.autotask.net/ATServicesRest/` |
| `AUTOTASK_USERNAME` | Your Autotask login email |
| `AUTOTASK_SECRET` | Autotask → Admin → Resources → your user → API Access → Secret |
| `AUTOTASK_INTEGRATION_CODE` | Autotask → Admin → API Tracking Identifier → Integration Code |

> **Security:** `.env` is gitignored by default. Never commit it.

---

## Running the App

```bash
source .venv/bin/activate   # if not already active
python main.py
```

**First run** will:
1. Test your Autotask connection
2. Fetch all active work types (billing codes)
3. Auto-map onsite/offsite work types (or prompt you to pick)
4. Validate the Level 1 queue ID
5. Cache everything to `~/.autotask_time_entry/cache.json`

Subsequent runs skip the bootstrap and open the entry form directly.

---

## Usage

1. **Enter:** client name, date, start time, duration, raw notes
2. **Generate Draft:** AI converts your notes into title + summary + work mode
3. **Review:** edit title, summary, work type, work mode, verify client
4. **Approve & Submit:** creates Ticket and Time Entry in Autotask
5. **Confirmation:** see Ticket number and Time Entry ID, copy to clipboard

**Keyboard shortcuts:**
- `⌘↵` (or `Ctrl+Enter`) — Generate Draft from entry form

---

## Resetting the Cache

If you need to re-run first-run setup (e.g., work types changed):

```bash
rm ~/.autotask_time_entry/cache.json
python main.py
```

---

## Packaging as a macOS .app (Optional)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "AutotaskTimeEntry" main.py
# Output: dist/AutotaskTimeEntry.app
```

> Note: .env must exist in the same directory as the binary, or you can pre-export env vars in a launcher shell script.

---

## Architecture

```
autotask_time_entry/
├── main.py                     # Entry point
├── requirements.txt
├── .env.example
├── README.md
└── src/
    ├── config.py               # Env var loading, no secrets in code
    ├── anthropic_client.py     # AI note transformation
    ├── autotask_client.py      # Autotask REST API (Tickets, TimeEntries, etc.)
    ├── cache.py                # Local JSON cache for lookup data
    └── ui/
        ├── app.py              # Main window + screen manager
        ├── entry_form.py       # Screen 1: input form
        ├── review_screen.py    # Screen 2: mandatory review/edit
        ├── confirmation_screen.py  # Screen 3: success + IDs
        └── work_mode_picker.py # First-run work type mapping dialog
```

---

## Autotask Field Notes

| Field | Value |
|---|---|
| Ticket status | New (1) |
| Ticket priority | Medium (fetched dynamically from picklist) |
| Queue ID | 29682833 (Level 1 Support — hardcoded per spec) |
| Time entry status | New — **must be approved manually in Autotask UI** |
| Time entry type | Regular (1) |
| Task type link | 2 (Ticket) |
| Billing code | Fetched from AllocationCodes at startup |

If `taskTypeLink=2` is rejected by your Autotask instance, try `8` (TicketService). This varies by Autotask zone configuration. See comments in `autotask_client.py`.

---

## Testing Checklist

- [ ] `python main.py` starts without config errors
- [ ] First run: connection test passes, work types load
- [ ] Entry form validates all required fields
- [ ] AI generates valid title + summary + work mode
- [ ] Review screen shows original notes alongside generated content
- [ ] Cancel/Back does NOT create anything in Autotask
- [ ] Company search returns correct match
- [ ] Multi-match company picker appears when needed
- [ ] Title and summary are editable on review screen
- [ ] Work mode radio buttons update work type dropdown
- [ ] Regenerate re-runs AI without submitting
- [ ] Approve & Submit creates ticket in Autotask
- [ ] Ticket appears with correct title, company, queue, priority
- [ ] Time entry linked to ticket with correct date/times
- [ ] Confirmation screen shows Ticket number + Time Entry ID
- [ ] Copy confirmation text works
- [ ] "Create Another" returns to blank entry form

---

## Optional Enhancements (Post-MVP)

- Service Call creation/linking
- Client name autocomplete from recent entries
- Local history/log of submitted entries
- Dark mode support
- Direct link to Autotask ticket in browser on confirmation
