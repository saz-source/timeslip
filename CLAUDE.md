# TimeSlip — JDK Consulting Time Entry App

## What this is
macOS desktop app (Python/tkinter) that converts raw technician notes into 
Autotask tickets + time entries using Claude AI. ~3000 lines of Python.

## Key facts
- Current version is defined in src/ui/app.py as VERSION.
- .env lives at ~/.autotask_time_entry/.env
- Autotask base: webservices5.autotask.net
- Role ID: 29682834, Queue ID: 29682833
- Travel time billing code: 29700414 (Trip Charge)
- Onsite billing: 29682800, Remote: 29682801
- Source: 6=onsite, 2=remote
- workTypeID required on ticket creation

## Known issues / watch out for
- styles.py mac_btn: use _set_bg() NOT frame.configure() — causes recursion
- calendar_picker: overrideredirect(False) — True causes focus lock
- Autotask POST 500s sometimes succeed — don't retry POSTs
- entry_form: use self.app not app in _build()
- Always bump VERSION in src/ui/app.py when making changes

## Architecture
main.py → src/ui/app.py → entry_form → review_screen → confirmation_screen
src/autotask_client.py — all API calls
src/cache.py — local JSON cache + history
src/anthropic_client.py — AI note transformation
