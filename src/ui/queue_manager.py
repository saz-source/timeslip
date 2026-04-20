"""
Queue Manager — view/retry/edit/delete offline-queued entries.
Opened by clicking the orange queue banner on the entry form.
"""
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Optional

from src.ui.styles import (
    BG, CARD, ACCENT, FG, FG2, BORDER, DIVIDER,
    FONT_BODY, FONT_SM, FONT_BOLD, FONT_HDR,
    mac_btn,
)

if TYPE_CHECKING:
    from src.ui.app import App


class QueueManager(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.title("Offline Queue")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(720, 400)
        self.grab_set()

        self._app = app
        self._items = []
        self._build()
        self._refresh_table()

        self.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        w, h = 760, 460
        self.geometry(f"{w}x{h}+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _build(self):
        hdr = tk.Frame(self, bg="#c05000", pady=9)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="  \u23f3  Offline Queue",
                 font=FONT_HDR, bg="#c05000", fg="white").pack(side=tk.LEFT)

        cols = ("Company", "Date", "Title", "Queued At", "Status")
        frame = tk.Frame(self, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(12, 4))

        self._tree = ttk.Treeview(frame, columns=cols, show="headings",
                                   selectmode="browse")
        widths = [160, 90, 220, 130, 80]
        for col, w in zip(cols, widths):
            self._tree.heading(col, text=col)
            self._tree.column(col, width=w, minwidth=w)

        self._tree.tag_configure("pending",  foreground=FG)
        self._tree.tag_configure("retrying", foreground="#1B5EA6")
        self._tree.tag_configure("failed",   foreground="#cc0000")
        self._tree.tag_configure("odd",  background=CARD)
        self._tree.tag_configure("even", background="#f7f9fc")

        sb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        self._error_var = tk.StringVar()
        tk.Label(self, textvariable=self._error_var,
                 font=FONT_SM, bg=BG, fg="#cc0000",
                 anchor=tk.W, wraplength=720, justify="left").pack(
            fill=tk.X, padx=18, pady=(0, 4))

        tk.Frame(self, bg=DIVIDER, height=1).pack(fill=tk.X)
        bf = tk.Frame(self, bg=BG)
        bf.pack(fill=tk.X, padx=16, pady=8)

        mac_btn(bf, "Close", self.destroy).pack(side=tk.RIGHT)

        self._delete_btn = mac_btn(bf, "Delete", self._delete_selected)
        self._delete_btn.pack(side=tk.RIGHT, padx=(0, 8))
        self._delete_btn.configure_btn(state="disabled")

        self._edit_btn = mac_btn(bf, "Edit & Resubmit", self._edit_selected)
        self._edit_btn.pack(side=tk.RIGHT, padx=(0, 8))
        self._edit_btn.configure_btn(state="disabled")

        self._retry_btn = mac_btn(bf, "  Retry Now  ", self._retry_selected, primary=True)
        self._retry_btn.pack(side=tk.RIGHT, padx=(0, 8))
        self._retry_btn.configure_btn(state="disabled")

    def _refresh_table(self):
        self._tree.delete(*self._tree.get_children())
        self._items = self._app.queue.pending()
        for i, item in enumerate(self._items):
            status = item.get("status", "pending")
            date = item.get("start_dt", "")[:10]
            queued_raw = item.get("queued_at", "")
            try:
                from datetime import datetime as _dt
                queued_fmt = _dt.fromisoformat(queued_raw).strftime("%b %d %I:%M %p")
            except Exception:
                queued_fmt = queued_raw[:16]
            row_tag = "odd" if i % 2 == 0 else "even"
            self._tree.insert("", tk.END, iid=str(i), tags=(status, row_tag), values=(
                item.get("company_name", ""),
                date,
                item.get("title", "")[:40],
                queued_fmt,
                status.capitalize(),
            ))
        self._update_buttons()

    def _on_select(self, _=None):
        self._update_buttons()
        sel = self._tree.selection()
        if sel:
            item = self._items[int(sel[0])]
            err = item.get("last_error", "")
            self._error_var.set(f"Error: {err}" if err else "")
        else:
            self._error_var.set("")

    def _update_buttons(self):
        sel = self._tree.selection()
        state = "normal" if sel else "disabled"
        self._retry_btn.configure_btn(state=state)
        self._edit_btn.configure_btn(state=state)
        self._delete_btn.configure_btn(state=state)

    def _selected_item(self):
        sel = self._tree.selection()
        if not sel:
            return None
        return self._items[int(sel[0])]

    def _retry_selected(self):
        item = self._selected_item()
        if not item:
            return
        item_id = item["id"]
        self._app.queue.update_status(item_id, "retrying")
        self._refresh_table()
        self._retry_btn.configure_btn(state="disabled")

        def worker():
            try:
                from datetime import datetime as _dt
                start = _dt.fromisoformat(item["start_dt"])
                end   = _dt.fromisoformat(item["end_dt"])
                if item.get("ticket_id"):
                    te_id = self._app.autotask.create_time_entries(
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
                    result = self._app.autotask.create_ticket_and_time_entry(
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
                self._app.queue.remove(item_id)
                self._app.cache.add_history_entry(
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
                self.after(0, lambda: self._on_retry_success(item["company_name"]))
            except Exception as exc:
                err = str(exc)
                self.after(0, lambda: self._on_retry_fail(item_id, err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_retry_success(self, company_name):
        self._refresh_table()
        self._refresh_banner()
        messagebox.showinfo("Submitted", f"Entry for {company_name} submitted successfully.")

    def _on_retry_fail(self, item_id, error):
        self._app.queue.update_status(item_id, "failed", error)
        self._refresh_table()

    def _edit_selected(self):
        item = self._selected_item()
        if not item:
            return
        if not messagebox.askyesno(
            "Edit & Resubmit",
            f"Remove this entry from the queue and open it for editing?\n\n"
            f"Company: {item['company_name']}\nTitle: {item['title']}",
            parent=self,
        ):
            return
        import types
        from datetime import datetime as _dt
        self._app.queue.remove(item["id"])
        start = _dt.fromisoformat(item["start_dt"])
        end   = _dt.fromisoformat(item["end_dt"])
        form_data = {
            "client":             item.get("company_name", item.get("client", "")),
            "entry_date":         start.date(),
            "start_dt":           start,
            "end_dt":             end,
            "duration_hours":     item.get("duration_hours", 1.0),
            "raw_notes":          item.get("description", ""),
            "work_mode_override": item.get("work_mode", "auto"),
        }
        ai_result = types.SimpleNamespace(
            title=item["title"],
            summary=item.get("description", ""),
            work_mode=item.get("work_mode", "unknown"),
        )
        self._app.form_data = form_data
        self._app.ai_result = ai_result
        self.destroy()
        self._refresh_banner()
        from src.ui.review_screen import ReviewScreen
        self._app._switch_frame(ReviewScreen(self._app.root, app=self._app))

    def _delete_selected(self):
        item = self._selected_item()
        if not item:
            return
        if not messagebox.askyesno(
            "Delete Entry",
            f"Permanently delete this queued entry?\n\n"
            f"Company: {item['company_name']}\nTitle: {item['title']}\n\n"
            "This cannot be undone.",
            parent=self,
        ):
            return
        self._app.queue.remove(item["id"])
        self._refresh_table()
        self._refresh_banner()

    def _refresh_banner(self):
        if (self._app._current_frame and
                hasattr(self._app._current_frame, "refresh_queue_banner")):
            self._app._current_frame.refresh_queue_banner()
