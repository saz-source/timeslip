"""
Main application window. Manages screen transitions and bootstrap loading screen.
"""
import logging
import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from src.autotask_client import AutotaskClient
from src.anthropic_client import AnthropicClient
from src.cache import Cache
from src.config import Config
from src.queue import OfflineQueue
from src.ui.styles import BG, ACCENT, ACCENT_LT, CARD, FG, FG2, BORDER, DIVIDER, SUCCESS, FONT_BODY, FONT_BOLD, FONT_HDR, FONT_SM

logger = logging.getLogger(__name__)

VERSION = "1.41"
_company = os.environ.get("COMPANY_NAME", "")
APP_TITLE = f"TimeSlip  v{VERSION}"
HEADER_TITLE = f"{_company} \u2014 Autotask Time Entry" if _company else "Autotask Time Entry"

MIN_WIDTH = 760
MIN_HEIGHT = 600


class App:
    def __init__(self, config: Config, autotask: AutotaskClient,
                 anthropic: AnthropicClient, cache: Cache):
        self.config = config
        self.autotask = autotask
        self.anthropic = anthropic
        self.cache = cache
        self.queue = OfflineQueue()

        self.root = tk.Tk()
        self.root.withdraw()  # hide until geometry is set
        self.root.title(APP_TITLE)
        self.root.minsize(MIN_WIDTH, MIN_HEIGHT)
        self.root.resizable(True, True)
        self.root.configure(bg=BG)

        self._apply_style()
        self._current_frame: Optional[tk.Frame] = None
        self.form_data: dict = {}
        self.ai_result = None
        self._latest_github_version: str | None = None

    def run(self):
        # Center window on screen
        self.root.update_idletasks()
        w, h = MIN_WIDTH, MIN_HEIGHT
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        # Restore saved geometry or center on screen
        saved = self.cache.get_window_geometry()
        if saved:
            try:
                self.root.geometry(saved)
            except Exception:
                self._center_window()
        else:
            self._center_window()

        # Save geometry on close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.root.deiconify()  # show now that geometry is ready
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(200, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()
        self.root.after(0, self._bootstrap)
        self.root.mainloop()

    def show_entry_form(self, prefill: dict | None = None):
        from src.ui.entry_form import EntryForm
        self._switch_frame(EntryForm(self.root, app=self, prefill=prefill))

    def show_review(self, form_data: dict, ai_result):
        from src.ui.review_screen import ReviewScreen
        self.form_data = form_data
        self.ai_result = ai_result
        self._switch_frame(ReviewScreen(self.root, app=self))

    def show_confirmation(self, result):
        from src.ui.confirmation_screen import ConfirmationScreen
        self._switch_frame(ConfirmationScreen(self.root, app=self, result=result))

    def _switch_frame(self, new_frame: tk.Frame):
        if self._current_frame:
            self._current_frame.destroy()
        self._current_frame = new_frame
        new_frame.pack(fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------
    # Bootstrap with animated loading screen
    # ------------------------------------------------------------------

    def _center_window(self):
        w, h = MIN_WIDTH, MIN_HEIGHT
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _on_close(self):
        try:
            self.cache.set_window_geometry(self.root.geometry())
            self.cache.set_last_client("")
        except Exception:
            pass
        self.root.destroy()

    def _bootstrap(self):
        if self.cache.is_populated:
            self.show_entry_form()
            self._check_for_update()
            self._flush_queue()
            return
        self._loading_screen = LoadingScreen(self.root, app=self)
        self._switch_frame(self._loading_screen)

        def worker():
            try:
                self.cache.populate(
                    self.autotask,
                    on_status=self._on_status,
                )
                self.root.after(600, self._bootstrap_done)
            except Exception as exc:
                e = str(exc)
                self.root.after(0, lambda: self._bootstrap_error(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_status(self, msg: str, done: bool):
        """Called from worker thread — schedule UI update on main thread."""
        self.root.after(0, lambda: self._loading_screen.update_status(msg, done))

    def _bootstrap_done(self):
        wt = self.cache.get_work_types()
        onsite_id = self.cache.get_onsite_work_type_id()
        offsite_id = self.cache.get_offsite_work_type_id()
        if not onsite_id or not offsite_id:
            self._prompt_work_mode_mapping(wt)
        else:
            self.show_entry_form()
        self._check_for_update()
        self._flush_queue()

    def _check_for_update(self):
        from src.updater import check_for_update
        def on_update(latest, url):
            self._latest_github_version = latest
            self.root.after(0, lambda: self._show_update_banner(latest, url))
        def on_up_to_date(latest):
            self._latest_github_version = latest
        check_for_update(VERSION, on_update, on_up_to_date)

    def _show_update_banner(self, latest: str, url: str):
        if self._current_frame and hasattr(self._current_frame, "show_update_banner"):
            self._current_frame.show_update_banner(latest, url)

    def _flush_queue(self):
        if self.queue.count() == 0:
            return

        def worker():
            from datetime import datetime as _dt
            flushed = []
            for item in self.queue.pending():
                try:
                    start = _dt.fromisoformat(item["start_dt"])
                    end   = _dt.fromisoformat(item["end_dt"])
                    if item.get("ticket_id"):
                        # Partial failure recovery — ticket exists, only create time entries
                        te_id = self.autotask.create_time_entries(
                            ticket_id=item["ticket_id"],
                            ticket_number=item.get("ticket_number", ""),
                            title=item["title"],
                            description=item["description"],
                            start_dt=start,
                            end_dt=end,
                            billing_code_id=item["billing_code_id"],
                            resource_id=item["resource_id"],
                            travel_hours=item.get("travel_hours", 0.0),
                        )
                        t_id, t_num, te_id = item["ticket_id"], item.get("ticket_number", ""), te_id
                    else:
                        result = self.autotask.create_ticket_and_time_entry(
                            company_id=item["company_id"],
                            title=item["title"],
                            description=item["description"],
                            start_dt=start,
                            end_dt=end,
                            billing_code_id=item["billing_code_id"],
                            resource_id=item["resource_id"],
                            priority_id=item["priority_id"],
                            queue_id=item["queue_id"],
                            travel_hours=item.get("travel_hours", 0.0),
                        )
                        t_id, t_num, te_id = result.ticket_id, result.ticket_number, result.time_entry_id
                    self.queue.remove(item["id"])
                    self.cache.add_history_entry(
                        company_id=item["company_id"],
                        company_name=item["company_name"],
                        ticket_id=t_id,
                        ticket_number=t_num,
                        time_entry_id=te_id,
                        title=item["title"],
                        work_date=item["start_dt"][:10],
                        start_time=start.strftime("%I:%M %p").lstrip("0"),
                        duration_hours=item.get("duration_hours", 0.0),
                        work_mode=item.get("work_mode", "unknown"),
                    )
                    flushed.append(item)
                except Exception:
                    break  # still offline or unrecoverable — try again next launch
            if flushed:
                self.root.after(0, lambda: self._on_queue_flushed(flushed))

        threading.Thread(target=worker, daemon=True).start()

    def _on_queue_flushed(self, flushed):
        n = len(flushed)
        names = ", ".join(i["company_name"] for i in flushed[:3])
        if n > 3:
            names += f" +{n - 3} more"
        messagebox.showinfo(
            "Offline Entries Submitted",
            f"{n} queued entr{'y' if n == 1 else 'ies'} submitted:\n{names}"
        )
        if self._current_frame and hasattr(self._current_frame, "refresh_queue_banner"):
            self._current_frame.refresh_queue_banner()

    def _bootstrap_error(self, msg: str):
        if self._current_frame:
            self._current_frame.destroy()
            self._current_frame = None
        messagebox.showerror(
            "Connection Failed",
            f"Could not connect to Autotask:\n\n{msg}\n\n"
            "Check your .env credentials and try again.")
        self.root.destroy()

    def _prompt_work_mode_mapping(self, work_types):
        from src.ui.work_mode_picker import WorkModePicker
        picker = WorkModePicker(self.root, work_types=work_types, app=self)
        self.root.wait_window(picker)
        self.show_entry_form()

    @staticmethod
    def _apply_style():
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TLabel", font=FONT_BODY, background=CARD)
        style.configure("TButton", font=FONT_BODY)
        style.configure("TEntry", font=FONT_BODY)
        style.configure("TCombobox", font=FONT_BODY)
        style.configure("TRadiobutton", font=FONT_BODY, background=CARD)
        style.configure("TCheckbutton", font=FONT_BODY, background=CARD)
        style.configure("Vertical.TScrollbar",
                        gripcount=0, relief="flat",
                        troughcolor="#e8ecf0",
                        background="#b0bcc8",
                        arrowsize=12)
        style.map("Vertical.TScrollbar",
                  background=[("active", ACCENT)])


# ------------------------------------------------------------------
# Loading screen with animated status lights
# ------------------------------------------------------------------

DOT_GREY   = "#c8d4e0"
DOT_SPIN   = ACCENT
DOT_GREEN  = SUCCESS


class LoadingScreen(tk.Frame):
    """
    Animated loading screen shown on first run while cache populates.
    Each step gets a status row with a dot that spins → turns green.
    """
    def __init__(self, parent, app: "App"):
        super().__init__(parent, bg=BG)
        self._app = app
        self._rows: list[dict] = []   # {label, dot_canvas, state}
        self._spin_angle = 0
        self._spinning: set = set()
        self._build()
        self._start_idle_spin()

    def _build(self):
        # Blue header
        hdr = tk.Frame(self, bg=ACCENT, pady=9)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text=f"  {HEADER_TITLE}",
                 font=FONT_HDR, bg=ACCENT, fg="white").pack(side=tk.LEFT)

        # Centre card
        self._card = tk.Frame(self, bg=CARD,
                              highlightbackground=BORDER, highlightthickness=1)
        self._card.pack(expand=True, padx=80, pady=40, fill=tk.BOTH)

        tk.Label(self._card,
                 text="Starting up\u2026",
                 font=FONT_BOLD, bg=CARD, fg=FG).pack(pady=(24, 4))
        tk.Label(self._card,
                 text="Connecting to Autotask and loading your settings.",
                 font=FONT_SM, bg=CARD, fg=FG2).pack(pady=(0, 20))

        # Status rows container
        self._rows_frame = tk.Frame(self._card, bg=CARD)
        self._rows_frame.pack(fill=tk.X, padx=40, pady=(0, 16))

        # Progress bar
        self._progress = ttk.Progressbar(
            self._card, mode="indeterminate", length=300)
        self._progress.pack(pady=(0, 24))
        self._progress.start(10)

    def _add_row(self, msg: str) -> dict:
        row_frame = tk.Frame(self._rows_frame, bg=CARD)
        row_frame.pack(fill=tk.X, pady=3)

        # Dot canvas (16x16)
        canvas = tk.Canvas(row_frame, width=16, height=16,
                           bg=CARD, highlightthickness=0)
        canvas.pack(side=tk.LEFT, padx=(0, 10))
        dot_id = canvas.create_oval(2, 2, 14, 14,
                                    fill=DOT_GREY, outline="")

        lbl = tk.Label(row_frame, text=msg,
                       font=FONT_BODY, bg=CARD, fg=FG2, anchor=tk.W)
        lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        row = {"canvas": canvas, "dot_id": dot_id, "label": lbl,
               "state": "pending", "msg": msg}
        self._rows.append(row)
        return row

    def update_status(self, msg: str, done: bool):
        """Called from main thread via root.after()."""
        is_done = msg.startswith("\u2713") or done

        # Find last non-done row and update it, or add new pending row
        if is_done:
            # Mark last spinning/pending row as done
            for row in reversed(self._rows):
                if row["state"] in ("spinning", "pending"):
                    row["state"] = "done"
                    row["label"].configure(text=msg, fg=FG)
                    row["canvas"].itemconfig(row["dot_id"], fill=DOT_GREEN)
                    self._spinning.discard(id(row))
                    break
            else:
                # No pending row — add a done row directly
                row = self._add_row(msg)
                row["state"] = "done"
                row["canvas"].itemconfig(row["dot_id"], fill=DOT_GREEN)
                row["label"].configure(fg=FG)
        else:
            # Add new spinning row for in-progress step
            row = self._add_row(msg)
            row["state"] = "spinning"
            row["canvas"].itemconfig(row["dot_id"], fill=DOT_SPIN)
            self._spinning.add(id(row))

        self._card.update_idletasks()

    def _start_idle_spin(self):
        """Pulse the spinning dots with a simple colour cycle."""
        self._pulse()

    def _pulse(self):
        if not self.winfo_exists():
            return
        self._spin_angle = (self._spin_angle + 1) % 12
        # Cycle through shades for spinning dots
        shades = [
            "#1B5EA6", "#2470bb", "#3080cc", "#4090d8",
            "#5aa0e0", "#70b0e8", "#88bef0", "#a0caf4",
            "#b8d8f8", "#c8e0f8", "#d8eafc", "#1B5EA6",
        ]
        shade = shades[self._spin_angle]
        for row in self._rows:
            if row["state"] == "spinning":
                try:
                    row["canvas"].itemconfig(row["dot_id"], fill=shade)
                except Exception:
                    pass
        self.after(80, self._pulse)
