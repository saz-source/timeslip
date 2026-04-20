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

        self._history = self._app.cache.get_history()

        if not self._history:
            tk.Label(self, text="No submissions yet.",
                     font=FONT_BODY, bg=BG, fg=FG2).pack(pady=40)
            mac_btn(self, "Close", self.destroy).pack(pady=8)
            return

        # Table
        cols = ("Date", "Client", "Title", "Mode", "Duration", "Ticket #")
        frame = tk.Frame(self, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        self._tree = ttk.Treeview(frame, columns=cols, show="headings",
                                   selectmode="browse")

        widths = [90, 160, 220, 70, 70, 100]
        for col, w in zip(cols, widths):
            self._tree.heading(col, text=col)
            self._tree.column(col, width=w, minwidth=w)

        self._tree.tag_configure("odd", background=CARD)
        self._tree.tag_configure("even", background="#f7f9fc")

        for i, entry in enumerate(self._history):
            tag = "odd" if i % 2 == 0 else "even"
            self._tree.insert("", tk.END, iid=str(i), tags=(tag,), values=(
                entry.get("work_date", ""),
                entry.get("company_name", ""),
                entry.get("title", "")[:40],
                entry.get("work_mode", "").capitalize(),
                f"{entry.get('duration_hours', 0):.2f} hrs",
                entry.get("ticket_number", ""),
            ))

        sb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Buttons
        tk.Frame(self, bg=DIVIDER, height=1).pack(fill=tk.X)
        bf = tk.Frame(self, bg=BG)
        bf.pack(fill=tk.X, padx=16, pady=8)
        mac_btn(bf, "Close", self.destroy).pack(side=tk.RIGHT)
        self._resubmit_btn = mac_btn(bf, "Resubmit Selected", self._resubmit)
        self._resubmit_btn.pack(side=tk.RIGHT, padx=(0, 8))
        self._resubmit_btn.configure_btn(state="disabled")
        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Double-Button-1>", lambda _: self._resubmit())

    def _on_select(self, _=None):
        self._resubmit_btn.configure_btn(state="normal" if self._tree.selection() else "disabled")

    def _resubmit(self):
        sel = self._tree.selection()
        if not sel:
            return
        entry = self._history[int(sel[0])]
        prefill = {
            "client":         entry.get("company_name", ""),
            "work_date":      entry.get("work_date", ""),
            "start_time":     entry.get("start_time", ""),
            "duration_hours": entry.get("duration_hours", 1.0),
            "work_mode":      entry.get("work_mode", "auto"),
        }
        self.destroy()
        self._app.show_entry_form(prefill=prefill)
