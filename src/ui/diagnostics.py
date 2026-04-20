"""
Diagnostics panel — Cmd+Shift+D from the entry form.
Shows version info, queue state, cache stats, and last API error.
"""
import tkinter as tk
from typing import TYPE_CHECKING

from src.ui.styles import (
    BG, CARD, ACCENT, FG, FG2, BORDER, DIVIDER,
    FONT_HDR, FONT_SM, FONT_BOLD, mac_btn
)

if TYPE_CHECKING:
    from src.ui.app import App


class DiagnosticsPanel(tk.Toplevel):
    def __init__(self, parent, app: "App"):
        super().__init__(parent)
        self.title("TimeSlip Diagnostics")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()
        self._app = app
        self._build()
        self.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        w, h = 520, 380
        self.geometry(f"{w}x{h}+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _build(self):
        hdr = tk.Frame(self, bg=ACCENT, pady=9)
        hdr.pack(fill="x")
        tk.Label(hdr, text="  Diagnostics",
                 font=FONT_HDR, bg=ACCENT, fg="white").pack(side="left")

        card = tk.Frame(self, bg=CARD,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="both", expand=True, padx=16, pady=12)

        from src.ui.app import VERSION
        from src.cache import CACHE_FILE
        from src.queue import QUEUE_FILE

        app = self._app
        github_ver = f"v{app._latest_github_version}" if app._latest_github_version else "not checked yet"
        company_count = str(len(app.autotask._all_companies)) if app.autotask._all_companies is not None else "not loaded"
        try:
            resource_id = str(app.cache.get_resource_id())
        except Exception:
            resource_id = "not loaded"

        rows = [
            ("App Version",       f"v{VERSION}"),
            ("Latest on GitHub",  github_ver),
            ("Queue",             f"{app.queue.count()} pending entr{'y' if app.queue.count() == 1 else 'ies'}"),
            ("Cached Companies",  company_count),
            ("Resource ID",       resource_id),
            ("Cache File",        str(CACHE_FILE)),
            ("Queue File",        str(QUEUE_FILE)),
            ("Last API Error",    app.autotask._last_error or "none"),
        ]

        for label, value in rows:
            row = tk.Frame(card, bg=CARD)
            row.pack(fill="x", padx=12, pady=4)
            tk.Label(row, text=label + ":", font=FONT_SM, bg=CARD, fg=FG2,
                     width=18, anchor="w").pack(side="left")
            color = "#cc0000" if label == "Last API Error" and value != "none" else FG
            tk.Label(row, text=value, font=FONT_SM, bg=CARD, fg=color,
                     anchor="w", wraplength=320, justify="left").pack(side="left", fill="x")

        tk.Frame(self, bg=DIVIDER, height=1).pack(fill="x")
        bf = tk.Frame(self, bg=BG)
        bf.pack(fill="x", padx=16, pady=8)
        mac_btn(bf, "Close", self.destroy).pack(side="right")
