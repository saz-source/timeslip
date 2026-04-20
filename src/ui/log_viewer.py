"""
Log Viewer — shows recent submission history.
"""
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from src.ui.styles import (
    BG, CARD, ACCENT, ACCENT_LT, FG, FG2, BORDER, DIVIDER,
    FONT_BODY, FONT_SM, FONT_BOLD, FONT_HDR,
    mac_btn
)

if TYPE_CHECKING:
    from src.ui.app import App


class LogViewer(tk.Toplevel):
    def __init__(self, parent, app: "App"):
        super().__init__(parent)
        self.title("Recent Submissions")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(700, 400)
        self.grab_set()

        self._app = app
        self._build()

        # Center on parent
        self.update_idletasks()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        w, h = 720, 460
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=ACCENT, pady=9)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="  Recent Submissions",
                 font=FONT_HDR, bg=ACCENT, fg="white").pack(side=tk.LEFT)

        history = self._app.cache.get_history()

        if not history:
            tk.Label(self, text="No submissions yet.",
                     font=FONT_BODY, bg=BG, fg=FG2).pack(pady=40)
            mac_btn(self, "Close", self.destroy).pack(pady=8)
            return

        # Table
        cols = ("Date", "Client", "Title", "Mode", "Duration", "Ticket #")
        frame = tk.Frame(self, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        tree = ttk.Treeview(frame, columns=cols, show="headings",
                             selectmode="browse")

        widths = [90, 160, 220, 70, 70, 100]
        for col, w in zip(cols, widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, minwidth=w)

        # Alternating row colors
        tree.tag_configure("odd", background=CARD)
        tree.tag_configure("even", background="#f7f9fc")

        for i, entry in enumerate(history):
            tag = "odd" if i % 2 == 0 else "even"
            date_str = entry.get("work_date", "")
            tree.insert("", tk.END, tags=(tag,), values=(
                date_str,
                entry.get("company_name", ""),
                entry.get("title", "")[:40],
                entry.get("work_mode", "").capitalize(),
                f"{entry.get('duration_hours', 0):.2f} hrs",
                entry.get("ticket_number", ""),
            ))

        sb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Buttons
        tk.Frame(self, bg=DIVIDER, height=1).pack(fill=tk.X)
        bf = tk.Frame(self, bg=BG)
        bf.pack(fill=tk.X, padx=16, pady=8)
        mac_btn(bf, "Close", self.destroy).pack(side=tk.RIGHT)
