"""
Screen 3 - Confirmation. Polished success screen.
"""
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from src.autotask_client import CreationResult
from src.ui.styles import (
    BG, CARD, ACCENT, ACCENT_LT, FG, FG2, BORDER, DIVIDER,
    SUCCESS, FONT_BODY, FONT_SM, FONT_BOLD, FONT_HDR, FONT_MONO,
    mac_btn, section_header
)

if TYPE_CHECKING:
    from src.ui.app import App


class ConfirmationScreen(tk.Frame):
    def __init__(self, parent, app: "App", result: CreationResult):
        super().__init__(parent, bg=BG)
        self.app = app
        self.result = result
        self._build()

    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=SUCCESS, pady=9)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="  \u2705  Submitted Successfully",
                 font=FONT_HDR, bg=SUCCESS, fg="white").pack(side=tk.LEFT)

        # Subtitle
        tk.Label(self,
                 text="Ticket and Time Entry created in Autotask. "
                      "Remember to approve the time entry in the Autotask UI.",
                 font=FONT_BODY, bg=BG, fg=FG2,
                 wraplength=580, justify=tk.CENTER).pack(pady=(14, 8))

        # IDs card
        ids = tk.Frame(self, bg=ACCENT_LT,
                       highlightbackground=ACCENT, highlightthickness=1)
        ids.pack(fill=tk.X, padx=40, pady=(0, 8))

        multi = getattr(self.app, "_multi_results", None)
        if multi and len(multi) > 1:
            for name, r in multi:
                tk.Label(ids, text=name, font=FONT_BOLD,
                         bg=ACCENT_LT, fg=FG).pack(anchor=tk.W, padx=16, pady=(8,0))
                self._id_row(ids, "Ticket", f"{r.ticket_number} (ID {r.ticket_id})")
                self._id_row(ids, "Time Entry", str(r.time_entry_id))
                tk.Frame(ids, bg=BORDER, height=1).pack(fill=tk.X, padx=12)
        else:
            self._id_row(ids, "Ticket Number", self.result.ticket_number)
            tk.Frame(ids, bg=BORDER, height=1).pack(fill=tk.X, padx=12)
            self._id_row(ids, "Ticket ID", str(self.result.ticket_id))
            tk.Frame(ids, bg=BORDER, height=1).pack(fill=tk.X, padx=12)
            self._id_row(ids, "Time Entry ID", str(self.result.time_entry_id))

        # Confirmation text
        tk.Label(self, text="Confirmation text \u2014 click box to copy:",
                 font=FONT_BOLD, bg=BG, fg=FG).pack(
            anchor=tk.W, padx=40, pady=(10, 4))

        fd = self.app.form_data
        ai = self.app.ai_result
        self._conf_text = self._build_conf(fd, ai)

        cf = tk.Frame(self, bg=CARD,
                      highlightbackground=BORDER, highlightthickness=1)
        cf.pack(fill=tk.BOTH, expand=True, padx=40)

        self._textbox = tk.Text(
            cf, wrap=tk.WORD, font=FONT_MONO,
            relief=tk.FLAT, padx=12, pady=10,
            bg="#f7f9fc", fg=FG,
            cursor="hand2",
        )
        self._textbox.insert("1.0", self._conf_text)
        self._textbox.configure(state=tk.DISABLED)
        self._textbox.pack(fill=tk.BOTH, expand=True)
        self._textbox.bind("<Button-1>", lambda _: self._copy())

        self._copy_hint = tk.Label(self, text="Click the box above to copy to clipboard",
                                   font=FONT_SM, bg=BG, fg=FG2)
        self._copy_hint.pack(pady=(4, 0))

        # Buttons
        tk.Frame(self, bg=DIVIDER, height=1).pack(fill=tk.X, pady=(10, 0))
        bf = tk.Frame(self, bg=BG)
        bf.pack(fill=tk.X, padx=16, pady=10)
        mac_btn(bf, "Quit", self.app.root.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        mac_btn(bf, "  Create Another Entry  ",
                self.app.show_entry_form, primary=True).pack(side=tk.RIGHT, padx=(8, 0))
        mac_btn(bf, "  Same Entry, New Client  ",
                self._repeat_new_client).pack(side=tk.RIGHT, padx=(8, 0))
        mac_btn(bf, "Open in Autotask",
                self._open_in_autotask).pack(side=tk.LEFT)

    def _id_row(self, parent, label, value):
        row = tk.Frame(parent, bg=ACCENT_LT)
        row.pack(fill=tk.X)
        tk.Label(row, text=label + ":",
                 font=FONT_BODY, bg=ACCENT_LT, fg=FG2,
                 width=18, anchor=tk.W).pack(
            side=tk.LEFT, padx=(16, 0), pady=10)
        tk.Label(row, text=value,
                 font=(FONT_MONO[0], 14, "bold"),
                 bg=ACCENT_LT, fg=ACCENT).pack(side=tk.LEFT)

    def _open_in_autotask(self):
        import webbrowser
        import os
        # Construct Autotask ticket URL from base URL
        base = os.environ.get("AUTOTASK_BASE_URL", "")
        # Convert API URL to UI URL: webservices5 -> ww5
        ui_base = base.replace("webservices", "ww").replace("/ATServicesRest/", "")
        if not ui_base:
            ui_base = "https://ww5.autotask.net"
        url = f"{ui_base}/AutotaskOnyx/HtmlEditor.aspx?PageId=1&TicketID={self.result.ticket_id}"
        webbrowser.open(url)

    def _repeat_new_client(self):
        """Re-open the review screen with same draft but fresh company lookup."""
        from src.ui.review_screen import ReviewScreen
        # Keep all form_data and ai_result — just clear the company
        # The review screen will auto-lookup based on client name,
        # but user can Change... to pick a different company
        self.app._switch_frame(ReviewScreen(self.app.root, app=self.app))

    def _build_conf(self, fd, ai):
        s = fd["start_dt"]
        e = fd["end_dt"]
        lines = [
            f"Autotask Time Entry \u2014 {s.strftime('%Y-%m-%d')}",
            f"Ticket:      {self.result.ticket_number} (ID {self.result.ticket_id})",
            f"Time Entry:  {self.result.time_entry_id}",
            f"Client:      {fd['client']}",
            f"Time:        {s.strftime('%I:%M %p').lstrip('0')} \u2013 "
            f"{e.strftime('%I:%M %p').lstrip('0')} ({fd['duration_hours']:.2f} hrs)",
            f"Title:       {ai.title}",
            "",
            "\u26a0 Remember to approve/post the time entry in the Autotask UI.",
        ]
        return "\n".join(lines)

    def _copy(self):
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(self._conf_text)
        self._textbox.configure(bg="#d4edda")
        self._copy_hint.configure(text="\u2713 Copied to clipboard!", fg=SUCCESS)
        self.after(1500, lambda: (
            self._textbox.configure(bg="#f7f9fc"),
            self._copy_hint.configure(
                text="Click the box above to copy to clipboard", fg=FG2)
        ))
