"""
Screen 1 - Entry Form. Smart time parsing, custom calendar + dropdown pickers.
"""
import threading
from datetime import date, datetime, timedelta
from tkinter import messagebox
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Optional

from src.ui.styles import (
    BG, CARD, ACCENT, ACCENT_LT, FG, FG2, FG3, BORDER,
    FONT_BODY, FONT_SM, FONT_BOLD,
    mac_btn, section_header, field_label, styled_entry
)
from src.ui.calendar_picker import CalendarPicker
from src.ui.dropdown_picker import DropdownPicker

if TYPE_CHECKING:
    from src.ui.app import App

# Time slots: 6:00 AM – 8:45 PM in 15-min increments
TIME_SLOTS = [
    f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
    for h in range(6, 21)
    for m in (0, 15, 30, 45)
]

DURATION_SLOTS = [
    "0.25", "0.5", "0.75", "1.0", "1.25", "1.5", "1.75",
    "2.0", "2.5", "3.0", "3.5", "4.0", "5.0", "6.0", "7.0", "8.0",
]

_PM = {"pm", "p", "pm.", "pn", "afternoon", "evening"}
_AM = {"am", "a", "am.", "an", "morning"}


def parse_time(raw):
    s = raw.strip().lower().replace(".", "").replace(",", "")
    if not s:
        return None
    is_pm = None
    for w in sorted(_PM, key=len, reverse=True):
        if s.endswith(w):
            is_pm = True
            s = s[:-len(w)].strip()
            break
    if is_pm is None:
        for w in sorted(_AM, key=len, reverse=True):
            if s.endswith(w):
                is_pm = False
                s = s[:-len(w)].strip()
                break
    s = s.replace(":", "").replace(" ", "")
    if not s.isdigit():
        return None
    n, ls = int(s), len(s)
    if ls <= 2:
        h, m = n, 0
    elif ls == 3:
        h, m = n // 100, n % 100
    elif ls == 4:
        h, m = n // 100, n % 100
    else:
        return None
    if not (0 <= m <= 59):
        return None
    if is_pm is True and h != 12:
        h += 12
    elif is_pm is False and h == 12:
        h = 0
    if not (0 <= h <= 23):
        return None
    return (h, m)


def fmt_time(h, m):
    return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


class EntryForm(tk.Frame):
    def __init__(self, parent, app: "App"):
        super().__init__(parent, bg=BG)
        self.app = app
        self._selected_date = date.today()
        self._update_banner = None
        self._queue_banner = None
        self._build()
        self._check_queue_banner()
        self._bind_shortcuts()

    def _check_queue_banner(self):
        n = self.app.queue.count()
        if n > 0 and not self._queue_banner:
            bar = tk.Frame(self, bg="#fde8d8", pady=4)
            bar.pack(fill=tk.X, before=self.winfo_children()[1])
            tk.Label(bar,
                     text=f"  \u23f3  {n} offline entr{'y' if n == 1 else 'ies'} pending \u2014 will submit when connected.",
                     font=FONT_SM, bg="#fde8d8", fg="#7a3a00").pack(side=tk.LEFT)
            self._queue_banner = bar

    def refresh_queue_banner(self):
        if self._queue_banner:
            self._queue_banner.destroy()
            self._queue_banner = None
        self._check_queue_banner()

    def show_update_banner(self, latest: str, url: str):
        if self._update_banner:
            return
        import webbrowser
        bar = tk.Frame(self, bg="#fff3cd", pady=4)
        bar.pack(fill=tk.X, before=self.winfo_children()[1])
        tk.Label(bar, text=f"  \u2b06  TimeSlip v{latest} is available.",
                 font=FONT_SM, bg="#fff3cd", fg="#856404").pack(side=tk.LEFT)
        lbl = tk.Label(bar, text="Download \u2192",
                       font=FONT_SM, bg="#fff3cd", fg=ACCENT, cursor="hand2")
        lbl.pack(side=tk.LEFT, padx=(4, 0))
        lbl.bind("<Button-1>", lambda _: webbrowser.open(url))
        tk.Label(bar, text="  ", bg="#fff3cd").pack(side=tk.LEFT)
        self._update_banner = bar

    def _build(self):
        from src.ui.app import HEADER_TITLE
        section_header(self, HEADER_TITLE)

        card = tk.Frame(self, bg=CARD,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)
        card.columnconfigure(1, weight=1)

        row = 0

        # ── Client ──
        field_label(card, "Client", row)
        self._client_var = tk.StringVar()
        last_client = self.app.cache.get_last_client()
        if last_client:
            self._client_var.set(last_client)
        ce = tk.Entry(card, textvariable=self._client_var,
                     font=FONT_BODY, bg=CARD, fg=FG,
                     insertbackground="#1a2a3a", insertwidth=2,
                     relief=tk.FLAT, borderwidth=0,
                     highlightthickness=1,
                     highlightbackground=BORDER,
                     highlightcolor=ACCENT)
        ce.grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(0, 14))
        self._client_entry = ce
        self.after(100, lambda: (ce.focus_set(), ce.select_range(0, tk.END)))
        row += 1

        # ── Date ──
        field_label(card, "Date", row)
        df = tk.Frame(card, bg=CARD)
        df.grid(row=row, column=1, sticky=tk.EW, pady=5)
        # Label as display — macOS won't override Label bg
        self._date_lbl = tk.Label(
            df, text=self._fmt_date(self._selected_date),
            font=FONT_BODY, width=14, anchor=tk.W,
            bg=CARD, fg=FG,
            relief=tk.FLAT, bd=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            padx=6, pady=4,
            cursor="hand2",
        )
        self._date_lbl.pack(side=tk.LEFT)
        cal_icon = tk.Label(df, text=" \U0001f4c5 ", font=FONT_SM,
                            bg=ACCENT_LT, fg=ACCENT, cursor="hand2",
                            padx=4, pady=5)
        cal_icon.pack(side=tk.LEFT, padx=(2, 0))
        for w in (self._date_lbl, cal_icon):
            w.bind("<Button-1>", self._open_calendar)
        self._date_hint = tk.Label(df, text="", font=FONT_SM,
                                   bg=CARD, fg="#2a7a2a")
        self._date_hint.pack(side=tk.LEFT, padx=(6, 0))
        self._qbtn(df, "Today", self._set_today)
        self._qbtn(df, "Yesterday", self._set_yesterday)
        row += 1

        # ── Start Time ──
        field_label(card, "Start Time", row)
        tf = tk.Frame(card, bg=CARD)
        tf.grid(row=row, column=1, sticky=tk.EW, pady=5)
        self._start_var = tk.StringVar(value="9:00 AM")
        self._time_entry = tk.Entry(
            tf, textvariable=self._start_var,
            font=FONT_BODY, width=11,
            bg=CARD, fg=FG,
            insertbackground="#1a2a3a", insertwidth=2,
            relief=tk.FLAT, borderwidth=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
        )
        self._time_entry.pack(side=tk.LEFT)
        time_arrow = tk.Label(tf, text="\u25be", font=("SF Pro Text", 10),
                              bg=ACCENT_LT, fg=ACCENT, cursor="hand2",
                              padx=5, pady=6)
        time_arrow.pack(side=tk.LEFT, padx=(1, 0))
        time_arrow.bind("<Button-1>", self._open_time_picker)
        self._time_hint = tk.Label(tf, text="  e.g. 9am  1:30pm  230pm",
                                   font=FONT_SM, bg=CARD, fg=FG3)
        self._time_hint.pack(side=tk.LEFT)
        self._start_var.trace_add("write", self._on_time_change)
        row += 1

        # ── Duration ──
        field_label(card, "Duration (hrs)", row)
        dur_frame = tk.Frame(card, bg=CARD)
        dur_frame.grid(row=row, column=1, sticky=tk.W, pady=5)
        self._duration_var = tk.StringVar(value="1.0")
        self._dur_entry = tk.Entry(
            dur_frame, textvariable=self._duration_var,
            font=FONT_BODY, width=7,
            bg=CARD, fg=FG,
            insertbackground="#1a2a3a", insertwidth=2,
            relief=tk.FLAT, borderwidth=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
        )
        self._dur_entry.pack(side=tk.LEFT)
        dur_arrow = tk.Label(dur_frame, text="\u25be", font=("SF Pro Text", 10),
                             bg=ACCENT_LT, fg=ACCENT, cursor="hand2",
                             padx=5, pady=6)
        dur_arrow.pack(side=tk.LEFT, padx=(1, 0))
        dur_arrow.bind("<Button-1>", self._open_dur_picker)
        tk.Label(dur_frame, text="  hours  (type or pick)",
                 font=FONT_SM, bg=CARD, fg=FG2).pack(side=tk.LEFT)
        row += 1

        # ── Work Mode ──
        field_label(card, "Work Mode", row)
        self._work_mode_var = tk.StringVar(value="auto")
        wf = tk.Frame(card, bg=CARD)
        wf.grid(row=row, column=1, sticky=tk.EW, pady=5)
        for val, txt in [("auto", "Auto-detect"),
                          ("onsite", "Onsite"),
                          ("offsite", "Offsite / Remote")]:
            ttk.Radiobutton(wf, text=txt, variable=self._work_mode_var,
                            value=val).pack(side=tk.LEFT, padx=(0, 16))
        row += 1

        # ── Notes ──
        field_label(card, "Raw Notes", row, top=True)
        nf = tk.Frame(card, bg=CARD)
        nf.grid(row=row, column=1, sticky=tk.NSEW, pady=5, padx=(0, 14))
        card.rowconfigure(row, weight=1)
        self._notes_text = tk.Text(
            nf, height=7, wrap=tk.WORD, font=FONT_BODY,
            relief=tk.FLAT, borderwidth=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            padx=8, pady=6, bg=CARD, fg=FG,
            insertbackground="#1a2a3a", insertwidth=2,
            selectbackground=ACCENT_LT, selectforeground=FG,
        )
        sb = ttk.Scrollbar(nf, orient=tk.VERTICAL,
                           command=self._notes_text.yview)
        self._notes_text.configure(yscrollcommand=sb.set)
        self._notes_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # Status + buttons
        self._status_var = tk.StringVar()
        tk.Label(self, textvariable=self._status_var,
                 font=FONT_BOLD, bg=BG, fg=ACCENT).pack(
            anchor=tk.W, padx=16, pady=(6, 0))
        tk.Frame(self, bg="#dde4ec", height=1).pack(fill=tk.X, pady=(8, 0))
        bf = tk.Frame(self, bg=BG)
        bf.pack(fill=tk.X, padx=16, pady=8)
        mac_btn(bf, "Clear", self._clear).pack(side=tk.LEFT)
        mac_btn(bf, "History", self._show_log).pack(side=tk.LEFT, padx=(8, 0))
        self._generate_btn = mac_btn(
            bf, "  Generate Draft  (Cmd+Enter)  ",
            self._generate, primary=True)
        self._generate_btn.pack(side=tk.RIGHT)

    def _qbtn(self, parent, text, cmd):
        mac_btn(parent, text, cmd, small=True).pack(side=tk.LEFT, padx=(6, 0))

    # ── Calendar ──────────────────────────────────────────────────────

    def _open_calendar(self, event=None):
        CalendarPicker(
            self.app.root,
            initial_date=self._selected_date,
            callback=self._on_date_selected,
            anchor_widget=self._date_lbl,
        )

    def _on_date_selected(self, d: date):
        self._selected_date = d
        self._date_lbl.configure(text=self._fmt_date(d))
        self._date_hint.configure(
            text=d.strftime("  \u2192 %A %B %d"), fg="#2a7a2a")

    @staticmethod
    def _fmt_date(d: date) -> str:
        return d.strftime("%b %d, %Y")

    def _set_today(self):
        self._on_date_selected(date.today())

    def _set_yesterday(self):
        self._on_date_selected(date.today() - timedelta(days=1))

    def _get_date(self):
        return self._selected_date

    # ── Time picker ───────────────────────────────────────────────────

    def _open_time_picker(self, event=None):
        current = self._start_var.get().strip()
        DropdownPicker(
            self.app.root,
            anchor_widget=self._time_entry,
            values=TIME_SLOTS,
            current_value=current if current in TIME_SLOTS else "9:00 AM",
            callback=self._on_time_selected,
            width=12,
        )

    def _on_time_selected(self, value):
        self._start_var.set(value)
        self.after(50, self._time_entry.focus_set)

    def _on_time_change(self, *_):
        p = parse_time(self._start_var.get())
        if p:
            self._time_hint.configure(
                text=f"  \u2192 {fmt_time(*p)}", fg="#2a7a2a")
        else:
            self._time_hint.configure(
                text="  e.g. 9am  1:30pm  230pm", fg=FG3)

    # ── Duration picker ───────────────────────────────────────────────

    def _open_dur_picker(self, event=None):
        current = self._duration_var.get().strip()
        DropdownPicker(
            self.app.root,
            anchor_widget=self._dur_entry,
            values=DURATION_SLOTS,
            current_value=current if current in DURATION_SLOTS else "1.0",
            callback=self._on_dur_selected,
            width=8,
        )

    def _on_dur_selected(self, value):
        self._duration_var.set(value)
        self.after(50, self._dur_entry.focus_set)

    # ── Actions ───────────────────────────────────────────────────────

    def _clear(self):
        self._client_var.set("")
        self._set_today()
        self._start_var.set("9:00 AM")
        self._duration_var.set("1.0")
        self._work_mode_var.set("auto")
        self._notes_text.delete("1.0", tk.END)
        self._status_var.set("")

    def _generate(self):
        data = self._validate()
        if data is None:
            return
        self._generate_btn.configure_btn(state="disabled")
        self._status_var.set("Generating AI draft\u2026")
        self.update_idletasks()

        def worker():
            try:
                ai = self.app.anthropic.transform_notes(
                    raw_notes=data["raw_notes"],
                    client_name=data["client"],
                    duration_hours=data["duration_hours"],
                )
                if data["work_mode_override"] != "auto":
                    ai.work_mode = data["work_mode_override"]
                self.after(0, lambda: self._on_success(data, ai))
            except Exception as exc:
                err = str(exc)
                self.after(0, lambda: self._on_error(err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_success(self, data, ai):
        self._animating = False
        self._generate_btn.configure_btn(state="normal")
        self._status_var.set("")
        self.app.show_review(form_data=data, ai_result=ai)

    def _on_error(self, msg):
        self._animating = False
        self._generate_btn.configure_btn(state="normal")
        self._status_var.set("")
        messagebox.showerror("AI Generation Failed",
                             f"Could not generate draft:\n\n{msg}")

    def _validate(self) -> Optional[dict]:
        client = self._client_var.get().strip()
        raw_notes = self._notes_text.get("1.0", tk.END).strip()
        work_mode_override = self._work_mode_var.get()
        errors = []

        if not client:
            errors.append("Client name is required.")

        entry_date = self._get_date()

        time_parsed = parse_time(self._start_var.get())
        if not time_parsed:
            errors.append(
                f"Can't read time '{self._start_var.get()}'. "
                "Try: 9am, 1:30pm, 230pm")
            start_dt = None
        else:
            h, m = time_parsed
            start_dt = datetime(entry_date.year, entry_date.month,
                                entry_date.day, h, m)

        try:
            duration_hours = float(self._duration_var.get())
            if duration_hours <= 0:
                raise ValueError
        except ValueError:
            errors.append("Enter a valid duration (e.g. 1.5).")
            duration_hours = None

        if not raw_notes:
            errors.append("Raw notes are required.")

        if errors:
            messagebox.showwarning(
                "Please fix the following",
                "\n".join(f"  \u2022 {e}" for e in errors))
            return None

        end_dt = start_dt + timedelta(hours=duration_hours)
        return {
            "client": client,
            "entry_date": entry_date,
            "start_dt": start_dt,
            "end_dt": end_dt,
            "duration_hours": duration_hours,
            "raw_notes": raw_notes,
            "work_mode_override": work_mode_override,
        }

    def _animate_dots(self, count):
        if not getattr(self, "_animating", True):
            return
        self._animating = True
        dots = "." * (count % 4)
        self._status_var.set(f"Generating AI draft{dots}")
        self.after(400, lambda: self._animate_dots(count + 1))

    def _show_log(self):
        from src.ui.log_viewer import LogViewer
        LogViewer(self.app.root, app=self.app)

    def _bind_shortcuts(self):
        self.app.root.bind("<Command-Return>", lambda _: self._generate())
        self.app.root.bind("<Control-Return>", lambda _: self._generate())
        self.bind("<Destroy>", self._unbind_shortcuts)
        # Tab navigation between fields
        try:
            self._client_entry.bind("<Tab>", lambda e: (self._date_lbl.focus_set(), "break"))
            self._time_entry.bind("<Tab>", lambda e: (self._dur_entry.focus_set(), "break"))
            self._dur_entry.bind("<Tab>", lambda e: (self._notes_text.focus_set(), "break"))
            self._notes_text.bind("<Tab>", lambda e: (self._generate(), "break"))
        except Exception:
            pass

    def _unbind_shortcuts(self, _=None):
        try:
            self.app.root.unbind("<Command-Return>")
            self.app.root.unbind("<Control-Return>")
        except Exception:
            pass
