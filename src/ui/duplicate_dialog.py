"""
Duplicate warning dialog — shown when a same-day same-company entry already exists.
Caller checks self.proceed after wait_window().
"""
import tkinter as tk

from src.ui.styles import (
    BG, CARD, ACCENT, FG, FG2, BORDER, DIVIDER,
    FONT_BODY, FONT_SM, FONT_BOLD, FONT_HDR,
    mac_btn,
)


class DuplicateWarningDialog(tk.Toplevel):
    def __init__(self, parent, existing, company_name):
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
        w, h = 460, 260
        self.geometry(f"{w}x{h}+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _build(self):
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
                 wraplength=400, justify="left").pack(anchor=tk.W, padx=14, pady=(12, 8))

        details = tk.Frame(card, bg="#f0f4f8",
                           highlightbackground=BORDER, highlightthickness=1)
        details.pack(fill=tk.X, padx=14, pady=(0, 12))

        ticket_num = self._existing.get("ticket_number", "")
        title = self._existing.get("title", "")
        start = self._existing.get("start_time", "")
        dur = self._existing.get("duration_hours", "")
        work_date = self._existing.get("work_date", "")
        dur_str = f"{dur:.2f} hrs" if isinstance(dur, float) else ""

        rows = [
            ("Date",   work_date),
            ("Ticket", ticket_num),
            ("Title",  title[:50] + ("\u2026" if len(title) > 50 else "")),
            ("Time",   f"{start}  {dur_str}".strip()),
        ]
        for label, val in rows:
            rf = tk.Frame(details, bg="#f0f4f8")
            rf.pack(fill=tk.X, padx=10, pady=3)
            tk.Label(rf, text=label + ":", font=FONT_SM, bg="#f0f4f8",
                     fg=FG2, width=8, anchor=tk.W).pack(side=tk.LEFT)
            tk.Label(rf, text=val, font=FONT_SM, bg="#f0f4f8",
                     fg=FG, anchor=tk.W).pack(side=tk.LEFT)

        tk.Frame(self, bg=DIVIDER, height=1).pack(fill=tk.X)
        bf = tk.Frame(self, bg=BG)
        bf.pack(fill=tk.X, padx=16, pady=8)
        mac_btn(bf, "Cancel", self.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        mac_btn(bf, "Proceed Anyway", self._proceed, primary=True).pack(side=tk.RIGHT)

    def _proceed(self):
        self.proceed = True
        self.destroy()
