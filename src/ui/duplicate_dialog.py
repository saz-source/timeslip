"""
Duplicate warning dialog — shown when a same-day same-company entry already exists.
Caller checks self.proceed after wait_window().
"""
import os
import tkinter as tk
from typing import TYPE_CHECKING

from src.ui.styles import (
    BG, CARD, ACCENT, FG, FG2, BORDER, DIVIDER,
    FONT_BODY, FONT_SM, FONT_BOLD, FONT_HDR,
    mac_btn,
)

if TYPE_CHECKING:
    pass


class DuplicateWarningDialog(tk.Toplevel):
    """
    Shows an existing ticket that matches company + date.
    Sets self.proceed = True if user clicks "Proceed Anyway".
    """
    def __init__(self, parent, existing: dict, company_name: str):
        super().__init__(parent)
        self.title("Possible Duplicate")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()
        self.proceed = False

        self._existing = existing
        self._company_name = company_name
        self._build()

        self.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        w, h = 480, 280
        self.geometry(f"{w}x{h}+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _build(self):
        # Warning header
        hdr = tk.Frame(self, bg="#d97706", pady=9)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="  \u26a0  Possible Duplicate Entry",
                 font=FONT_HDR, bg="#d97706", fg="white").pack(side=tk.LEFT)

        card = tk.Frame(self, bg=CARD,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        tk.Label(card,
                 text=f"You already submitted a ticket for {self._company_name} on this date:",
                 font=FONT_BODY, bg=CARD, fg=FG,
                 wraplength=420, justify="left").pack(anchor=tk.W, padx=14, pady=(12, 8))

        # Details
        details_frame = tk.Frame(card, bg="#f0f4f8",
                                  highlightbackground=BORDER, highlightthickness=1)
        details_frame.pack(fill=tk.X, padx=14, pady=(0, 8))

        ticket_num = self._existing.get("ticket_number", "")
        title = self._existing.get("title", "")
        start = self._existing.get("start_time", "")
        dur = self._existing.get("duration_hours", "")
        work_date = self._existing.get("work_date", "")

        rows = [
            ("Date",     work_date),
            ("Ticket",   ticket_num),
            ("Title",    title[:50] + ("…" if len(title) > 50 else "")),
            ("Time",     f"{start}  ({dur:.2f} hrs)" if isinstance(dur, float) else start),
        ]
        for label, val in rows:
            rf = tk.Frame(details_frame, bg="#f0f4f8")
            rf.pack(fill=tk.X, padx=10, pady=3)
            tk.Label(rf, text=label + ":", font=FONT_SM, bg="#f0f4f8",
                     fg=FG2, width=8, anchor=tk.W).pack(side=tk.LEFT)
            tk.Label(rf, text=val, font=FONT_SM, bg="#f0f4f8",
                     fg=FG, anchor=tk.W).pack(side=tk.LEFT)

        # Clickable ticket link (if we have ticket_id)
        ticket_id = self._existing.get("ticket_id")
        if ticket_id and ticket_num:
            link_frame = tk.Frame(card, bg=CARD)
            link_frame.pack(anchor=tk.W, padx=14, pady=(0, 4))
            lbl = tk.Label(link_frame,
                           text=f"Open Ticket #{ticket_num} in Autotask \u2192",
                           font=FONT_SM, bg=CARD, fg=ACCENT, cursor="hand2")
            lbl.pack(side=tk.LEFT)
            lbl.bind("<Button-1>", lambda _: self._open_ticket(ticket_id))

        # Buttons
        tk.Frame(self, bg=DIVIDER, height=1).pack(fill=tk.X)
        bf = tk.Frame(self, bg=BG)
        bf.pack(fill=tk.X, padx=16, pady=8)
        mac_btn(bf, "Cancel", self.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        mac_btn(bf, "Proceed Anyway", self._proceed, primary=True).pack(side=tk.RIGHT)

    def _proceed(self):
        self.proceed = True
        self.destroy()

    def _open_ticket(self, ticket_id: int):
        import webbrowser
        base = os.environ.get("AUTOTASK_BASE_URL", "")
        ui_base = base.replace("webservices", "ww").replace("/ATServicesRest/", "")
        if not ui_base:
            ui_base = "https://ww5.autotask.net"
        url = f"{ui_base}/AutotaskOnyx/HtmlEditor.aspx?PageId=1&TicketID={ticket_id}"
        webbrowser.open(url)
