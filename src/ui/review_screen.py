"""
Screen 2 — Review Screen (MANDATORY). Light theme, multi-company support.
Nothing submitted until user clicks Approve & Submit.
"""
import threading
from datetime import datetime
from tkinter import messagebox, simpledialog
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Optional

from src.autotask_client import Company, WorkType
from src.ui.styles import (
    BG, CARD, ACCENT, ACCENT_LT, FG, FG2, FG3, BORDER,
    DIVIDER, SUCCESS, WARN,
    FONT_BODY, FONT_SM, FONT_BOLD, FONT_HDR,
    mac_btn, section_header, divider, field_label, styled_entry, styled_text
)

if TYPE_CHECKING:
    from src.ui.app import App


class ReviewScreen(tk.Frame):
    def __init__(self, parent, app: "App"):
        super().__init__(parent, bg=BG)
        self.app = app
        self._company: Optional[Company] = None
        self._work_types: list = app.cache.get_work_types()
        # Multi-company state
        self._multi_mode = False
        self._checked_companies: dict = {}   # id -> {company, var}
        self._build()
        self._populate()
        self._lookup_company()

    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=ACCENT, pady=9)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="  Review Draft",
                 font=FONT_HDR, bg=ACCENT, fg="white").pack(side=tk.LEFT)
        tk.Label(hdr, text="  \u26a0  Nothing submitted until you click Approve",
                 font=FONT_SM, bg=ACCENT, fg="#ffd580").pack(side=tk.LEFT, padx=8)

        # Body — two columns
        body = tk.Frame(self, bg=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=10)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=CARD,
                        highlightbackground=BORDER, highlightthickness=1)
        left.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 8))
        left.columnconfigure(1, weight=1)

        right = tk.Frame(body, bg="#f7f9fc",
                         highlightbackground=BORDER, highlightthickness=1)
        right.grid(row=0, column=1, sticky=tk.NSEW)

        self._build_left(left)
        self._build_right(right)

        # Status
        self._status_var = tk.StringVar()
        tk.Label(self, textvariable=self._status_var,
                 font=FONT_BOLD, bg=BG, fg=ACCENT).pack(
            anchor=tk.W, padx=16, pady=(4, 0))

        # Buttons
        tk.Frame(self, bg=DIVIDER, height=1).pack(fill=tk.X, pady=(6, 0))
        bf = tk.Frame(self, bg=BG)
        bf.pack(fill=tk.X, padx=16, pady=8)
        mac_btn(bf, "\u2190 Back / Edit", self._go_back).pack(side=tk.LEFT)
        mac_btn(bf, "Regenerate AI", self._regenerate).pack(side=tk.LEFT, padx=8)
        mac_btn(bf, "Cancel", self._cancel).pack(side=tk.LEFT)
        self._submit_btn = mac_btn(
            bf, "  \u2713  Approve & Submit  ",
            self._submit, primary=True)
        self._submit_btn.pack(side=tk.RIGHT)

    def _build_left(self, parent):
        row = 0

        # ── Company section ──────────────────────────────────────────
        field_label(parent, "Client", row)
        cf = tk.Frame(parent, bg=CARD)
        cf.grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(0, 10))
        self._company_var = tk.StringVar()
        tk.Label(cf, textvariable=self._company_var,
                 font=FONT_BODY, bg=CARD, fg=FG).pack(side=tk.LEFT)
        mac_btn(cf, "Change\u2026", self._pick_company, small=True).pack(
            side=tk.LEFT, padx=8)
        # Multi-company toggle
        self._multi_toggle = mac_btn(
            cf, "+ Multi-company", self._toggle_multi, small=True)
        self._multi_toggle.pack(side=tk.LEFT)
        row += 1

        # Multi-company panel (hidden by default)
        self._multi_panel = tk.Frame(parent, bg=CARD)
        self._multi_panel.grid(row=row, column=0, columnspan=2,
                               sticky=tk.EW, padx=10, pady=0)
        self._multi_panel.grid_remove()   # hidden initially
        self._build_multi_panel(self._multi_panel)
        row += 1

        # ── Standard fields ──────────────────────────────────────────
        field_label(parent, "Date & Time", row)
        self._datetime_var = tk.StringVar()
        tk.Label(parent, textvariable=self._datetime_var,
                 font=FONT_BODY, bg=CARD, fg=FG).grid(
            row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        field_label(parent, "Ticket Title", row)
        self._title_var = tk.StringVar()
        styled_entry(parent, self._title_var).grid(
            row=row, column=1, sticky=tk.EW, pady=5, padx=(0, 10))
        row += 1

        field_label(parent, "Work Mode", row)
        self._work_mode_var = tk.StringVar()
        wf = tk.Frame(parent, bg=CARD)
        wf.grid(row=row, column=1, sticky=tk.EW, pady=5)
        for val, txt in [("onsite", "Onsite"),
                          ("offsite", "Offsite / Remote"),
                          ("unknown", "Unknown")]:
            ttk.Radiobutton(wf, text=txt,
                            variable=self._work_mode_var, value=val,
                            command=self._on_work_mode_change).pack(
                side=tk.LEFT, padx=(0, 12))
        row += 1

        # Travel time row (shown only for onsite)
        self._travel_row = tk.Frame(parent, bg=CARD)
        self._travel_row.grid(row=row, column=0, columnspan=2,
                              sticky=tk.EW, padx=14, pady=2)
        self._travel_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self._travel_row, text="Add travel time entry",
            variable=self._travel_var,
            font=FONT_BODY, bg=CARD, fg=FG,
            activebackground=CARD, selectcolor=CARD,
        ).pack(side=tk.LEFT)
        self._travel_hrs_var = tk.StringVar(value="1.0")
        tk.Entry(
            self._travel_row,
            textvariable=self._travel_hrs_var,
            font=FONT_BODY, width=5,
            bg=CARD, fg=FG,
            relief=tk.FLAT, bd=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
        ).pack(side=tk.LEFT, padx=(8, 4))
        tk.Label(self._travel_row,
                 text="hrs before ticket start",
                 font=FONT_SM, bg=CARD, fg=FG2).pack(side=tk.LEFT)
        self._travel_row.grid_remove()  # hidden by default
        row += 1

        field_label(parent, "Work Type", row)
        self._work_type_var = tk.StringVar()
        wt_names = [wt.name for wt in self._work_types] if self._work_types else ["(none)"]
        self._wt_combo = ttk.Combobox(
            parent, textvariable=self._work_type_var,
            values=wt_names, font=FONT_BODY, state="readonly")
        self._wt_combo.grid(row=row, column=1, sticky=tk.EW,
                            pady=5, padx=(0, 10))
        row += 1

        field_label(parent, "Queue", row)
        tk.Label(parent,
                 text=f"Level 1 Support (ID {self.app.config.queue_id})",
                 font=FONT_BODY, bg=CARD, fg=FG2).grid(
            row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        field_label(parent, "Priority", row)
        tk.Label(parent, text="Medium",
                 font=FONT_BODY, bg=CARD, fg=FG2).grid(
            row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        field_label(parent, "Summary", row, top=True)
        parent.rowconfigure(row, weight=1)
        sf = tk.Frame(parent, bg=CARD)
        sf.grid(row=row, column=1, sticky=tk.NSEW, pady=5, padx=(0, 10))
        self._summary_text = tk.Text(
            sf, height=6, wrap=tk.WORD, font=FONT_BODY,
            relief=tk.FLAT, borderwidth=0,
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=ACCENT,
            padx=8, pady=6, bg=CARD, fg=FG,
            insertbackground=ACCENT,
            selectbackground=ACCENT_LT)
        sb = ttk.Scrollbar(sf, orient=tk.VERTICAL,
                           command=self._summary_text.yview)
        self._summary_text.configure(yscrollcommand=sb.set)
        self._summary_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_multi_panel(self, parent):
        """Checkbox panel for multi-company submission."""
        tk.Frame(parent, bg=BORDER, height=1).pack(fill=tk.X, pady=(4, 6))

        hdr = tk.Frame(parent, bg=CARD)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="Submit to additional companies:",
                 font=FONT_BOLD, bg=CARD, fg=FG).pack(side=tk.LEFT)
        mac_btn(hdr, "Search\u2026", self._search_multi_company,
                small=True).pack(side=tk.LEFT, padx=8)

        # Scrollable checkbox list
        list_frame = tk.Frame(parent, bg=CARD,
                              highlightbackground=BORDER, highlightthickness=1)
        list_frame.pack(fill=tk.X, pady=(4, 6))

        canvas = tk.Canvas(list_frame, bg=CARD, height=120,
                           highlightthickness=0)
        sb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                           command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._multi_inner = tk.Frame(canvas, bg=CARD)
        self._multi_window = canvas.create_window(
            (0, 0), window=self._multi_inner, anchor=tk.NW)

        def on_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(self._multi_window, width=canvas.winfo_width())

        self._multi_inner.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", on_configure)
        self._multi_canvas = canvas

        tk.Frame(parent, bg=BORDER, height=1).pack(fill=tk.X, pady=(0, 4))
        self._populate_recent_companies()

    def _populate_recent_companies(self):
        """Fill multi-panel with recent companies from cache."""
        for w in self._multi_inner.winfo_children():
            w.destroy()
        self._checked_companies.clear()

        recent = self.app.cache.get_recent_companies()
        if not recent:
            tk.Label(self._multi_inner,
                     text="  No recent companies yet. Use Search to add.",
                     font=FONT_SM, bg=CARD, fg=FG2).pack(anchor=tk.W, pady=4)
            return

        for co in recent:
            var = tk.BooleanVar(value=False)
            row = tk.Frame(self._multi_inner, bg=CARD)
            row.pack(fill=tk.X, padx=8, pady=2)
            tk.Checkbutton(
                row, text=co["name"], variable=var,
                font=FONT_BODY, bg=CARD, fg=FG,
                activebackground=CARD,
                selectcolor=CARD,
            ).pack(side=tk.LEFT)
            self._checked_companies[co["id"]] = {
                "company": Company(id=co["id"], name=co["name"]),
                "var": var,
            }

    def _toggle_multi(self):
        self._multi_mode = not self._multi_mode
        if self._multi_mode:
            self._multi_panel.grid()
            self._multi_toggle.configure_btn = lambda **kw: None  # no-op
        else:
            self._multi_panel.grid_remove()

    def _search_multi_company(self):
        q = simpledialog.askstring("Add Company",
                                   "Search company name:", parent=self.app.root)
        if not q:
            return
        self._status_var.set("Searching\u2026")

        def worker():
            try:
                cos = self.app.autotask.search_companies(q)
                self.after(0, lambda: self._add_multi_results(cos))
                self.after(0, lambda: self._status_var.set(""))
            except Exception as exc:
                err = str(exc)
                self.after(0, lambda: self._status_var.set(f"Search failed: {err[:60]}"))

        threading.Thread(target=worker, daemon=True).start()

    def _add_multi_results(self, companies):
        """Add search results to multi-panel as pre-checked items."""
        existing_ids = set(self._checked_companies.keys())
        for co in companies:
            if co.id not in existing_ids:
                var = tk.BooleanVar(value=True)
                row = tk.Frame(self._multi_inner, bg=CARD)
                row.pack(fill=tk.X, padx=8, pady=2)
                tk.Checkbutton(
                    row, text=co.name, variable=var,
                    font=FONT_BODY, bg=CARD, fg=FG,
                    activebackground=CARD, selectcolor=CARD,
                ).pack(side=tk.LEFT)
                self._checked_companies[co.id] = {"company": co, "var": var}
        self._multi_canvas.update_idletasks()

    def _build_right(self, parent):
        tk.Label(parent, text="Original Notes",
                 font=FONT_BOLD, bg="#f7f9fc", fg=FG2).pack(
            anchor=tk.W, padx=12, pady=(10, 4))
        tk.Frame(parent, bg=BORDER, height=1).pack(fill=tk.X, padx=12)
        self._raw_notes_text = tk.Text(
            parent, wrap=tk.WORD, font=FONT_BODY,
            relief=tk.FLAT, bg="#f7f9fc", fg=FG2,
            padx=12, pady=8, state=tk.DISABLED,
            selectbackground=ACCENT_LT)
        self._raw_notes_text.pack(fill=tk.BOTH, expand=True)

    def _populate(self):
        fd = self.app.form_data
        ai = self.app.ai_result
        start = fd["start_dt"]
        end = fd["end_dt"]
        self._datetime_var.set(
            f"{start.strftime('%a %b %d, %Y')}   "
            f"{start.strftime('%I:%M %p').lstrip('0')} \u2013 "
            f"{end.strftime('%I:%M %p').lstrip('0')}   "
            f"({fd['duration_hours']:.2f} hrs)"
        )
        self._title_var.set(ai.title)
        mode = ai.work_mode if ai.work_mode in ("onsite", "offsite") else "unknown"
        self._work_mode_var.set(mode)
        self._summary_text.delete("1.0", tk.END)
        self._summary_text.insert("1.0", ai.summary)
        self._raw_notes_text.configure(state=tk.NORMAL)
        self._raw_notes_text.insert("1.0", fd["raw_notes"])
        self._raw_notes_text.configure(state=tk.DISABLED)
        self._set_work_type_from_mode(mode)
        self._company_var.set(f"{fd['client']}  (looking up\u2026)")

    def _set_work_type_from_mode(self, mode):
        if not self._work_types:
            return
        wt_id = (self.app.cache.get_onsite_work_type_id() if mode == "onsite"
                 else self.app.cache.get_offsite_work_type_id() if mode == "offsite"
                 else None)
        if wt_id:
            for wt in self._work_types:
                if wt.id == wt_id:
                    self._work_type_var.set(wt.name)
                    return
        if self._work_types:
            self._work_type_var.set(self._work_types[0].name)

    def _on_work_mode_change(self):
        mode = self._work_mode_var.get()
        self._set_work_type_from_mode(mode)
        if mode == "onsite":
            self._travel_row.grid()
            self._travel_var.set(True)
        else:
            self._travel_row.grid_remove()
            self._travel_var.set(False)

    def _lookup_company(self):
        name = self.app.form_data["client"]
        def worker():
            try:
                cos = self.app.autotask.search_companies(name)
                self.after(0, lambda: self._on_company_results(cos, name))
            except Exception as exc:
                err = str(exc)
                self.after(0, lambda: self._on_company_error(err))
        threading.Thread(target=worker, daemon=True).start()

    def _on_company_results(self, companies, name):
        if not companies:
            self._company_var.set(f"\u26a0 No match for '{name}'")
            messagebox.showwarning("Company Not Found",
                f"No active company matched '{name}'.\n\nClick Change\u2026 to search manually.")
            return
        if len(companies) == 1:
            self._company = companies[0]
            self._company_var.set(f"\u2713  {companies[0].name}")
            self._check_duplicate(companies[0])
        else:
            self._pick_from_list(companies)

    def _on_company_error(self, msg):
        self._company_var.set("\u26a0 Lookup failed")
        messagebox.showwarning("Company Lookup Error", f"Could not search:\n{msg}")

    def _check_duplicate(self, company):
        fd = self.app.form_data
        work_date = fd["start_dt"].strftime("%Y-%m-%d")
        existing = self.app.cache.check_duplicate(company.id, work_date)
        if existing:
            from tkinter import messagebox
            messagebox.showwarning(
                "Possible Duplicate",
                f"You already submitted a ticket for {company.name} on {work_date}:\n\n"
                f"  Ticket: {existing.get('ticket_number')}\n"
                f"  Title: {existing.get('title', '')}\n\n"
                "Continue anyway if this is a separate visit."
            )

    def _pick_company(self):
        q = simpledialog.askstring("Search Company",
                                   "Enter company name:", parent=self.app.root)
        if not q:
            return
        self._status_var.set("Searching\u2026")
        def worker():
            try:
                cos = self.app.autotask.search_companies(q)
                self.after(0, lambda: self._on_company_results(cos, q))
                self.after(0, lambda: self._status_var.set(""))
            except Exception as exc:
                err = str(exc)
                self.after(0, lambda: self._on_company_error(err))
                self.after(0, lambda: self._status_var.set(""))
        threading.Thread(target=worker, daemon=True).start()

    def _pick_from_list(self, companies):
        d = CompanyPickerDialog(self.app.root, companies)
        self.app.root.wait_window(d)
        if d.selected:
            self._company = d.selected
            self._company_var.set(f"\u2713  {d.selected.name}")

    def _unbind_review_shortcuts(self, _=None):
        try:
            self.app.root.unbind("<Command-Return>")
            self.app.root.unbind("<Control-Return>")
        except Exception:
            pass

    def _go_back(self):
        self.app.show_entry_form()

    def _cancel(self):
        if messagebox.askyesno("Cancel", "Discard this draft?"):
            self.app.show_entry_form()

    def _regenerate(self):
        self._submit_btn.configure_btn(state="disabled")
        self._status_var.set("\u23f3  Regenerating AI draft\u2026")
        fd = self.app.form_data
        def worker():
            try:
                ai = self.app.anthropic.transform_notes(
                    raw_notes=fd["raw_notes"],
                    client_name=fd["client"],
                    duration_hours=fd["duration_hours"],
                )
                self.after(0, lambda: self._on_regen_done(ai))
            except Exception as exc:
                err = str(exc)
                self.after(0, lambda: self._on_regen_error(err))
        threading.Thread(target=worker, daemon=True).start()

    def _on_regen_done(self, ai):
        self._submit_btn.configure_btn(state="normal")
        self._status_var.set("\u2713  Regenerated.")
        self.app.ai_result = ai
        self._title_var.set(ai.title)
        self._summary_text.delete("1.0", tk.END)
        self._summary_text.insert("1.0", ai.summary)
        if self.app.form_data.get("work_mode_override", "auto") == "auto":
            mode = ai.work_mode if ai.work_mode in ("onsite", "offsite") else "unknown"
            self._work_mode_var.set(mode)
            self._set_work_type_from_mode(mode)

    def _on_regen_error(self, msg):
        self._submit_btn.configure_btn(state="normal")
        self._status_var.set("")
        messagebox.showerror("Regeneration Failed", msg)

    def _submit(self):
        errors = self._validate()
        if errors:
            messagebox.showwarning("Fix before submitting",
                                   "\n".join(f"  \u2022 {e}" for e in errors))
            return

        # Collect all companies to submit to
        companies_to_submit = [self._company]
        if self._multi_mode:
            for entry in self._checked_companies.values():
                if entry["var"].get():
                    companies_to_submit.append(entry["company"])

        n = len(companies_to_submit)
        msg = (f"Create Ticket + Time Entry for {n} company"
               f"{'s' if n > 1 else ''}?\n\n"
               + "\n".join(f"  \u2022 {c.name}" for c in companies_to_submit)
               + "\n\nThis cannot be undone.")

        if not messagebox.askyesno("Confirm Submission", msg):
            return

        self._submit_btn.configure_btn(state="disabled")
        self._status_var.set(f"\u23f3  Submitting to {n} company"
                              f"{'s' if n > 1 else ''}\u2026")

        fd = self.app.form_data
        title = self._title_var.get().strip()
        summary = self._summary_text.get("1.0", tk.END).strip()
        wt_id = self._get_wt_id()
        resource_id = self.app.cache.get_resource_id()
        priority_id = self.app.cache.get_priority_medium_id()

        def worker():
            results = []
            errors_list = []
            for co in companies_to_submit:
                try:
                    try:
                        travel_hours = float(self._travel_hrs_var.get()) if self._travel_var.get() else 0.0
                    except ValueError:
                        travel_hours = 0.0
                    result = self.app.autotask.create_ticket_and_time_entry(
                        company_id=co.id,
                        title=title,
                        description=summary,
                        start_dt=fd["start_dt"],
                        end_dt=fd["end_dt"],
                        billing_code_id=wt_id,
                        resource_id=resource_id,
                        priority_id=priority_id,
                        queue_id=self.app.config.queue_id,
                        travel_hours=travel_hours,
                    )
                    # Save to recent companies
                    self.app.cache.add_recent_company(co.id, co.name)
                    results.append((co.name, result))
                except Exception as exc:
                    errors_list.append((co.name, str(exc)))

            self.after(0, lambda: self._on_submit_done(results, errors_list))

        threading.Thread(target=worker, daemon=True).start()

    def _on_submit_done(self, results, errors_list):
        self._submit_btn.configure_btn(state="normal")
        self._status_var.set("")
        if errors_list and not results:
            msgs = "\n".join(f"{n}: {e[:80]}" for n, e in errors_list)
            messagebox.showerror("All submissions failed", msgs)
            return
        if errors_list:
            msgs = "\n".join(f"\u26a0 {n}: {e[:80]}" for n, e in errors_list)
            messagebox.showwarning("Some submissions failed", msgs)

        # Log to history + update last client
        fd = self.app.form_data
        ai = self.app.ai_result
        for co_name, r in results:
            # Find company_id from name
            co_id = self._company.id if self._company and self._company.name == co_name else 0
            self.app.cache.add_history_entry(
                company_id=co_id,
                company_name=co_name,
                ticket_id=r.ticket_id,
                ticket_number=r.ticket_number,
                time_entry_id=r.time_entry_id,
                title=ai.title,
                work_date=fd["start_dt"].strftime("%Y-%m-%d"),
                start_time=fd["start_dt"].strftime("%I:%M %p"),
                duration_hours=fd["duration_hours"],
                work_mode=self._work_mode_var.get(),
            )
        if self._company:
            self.app.cache.set_last_client(self._company.name)

        self.app._multi_results = [(name, r) for name, r in results]
        self.app.show_confirmation(results[0][1])

    def _on_submit_error(self, msg):
        self._submit_btn.configure_btn(state="normal")
        self._status_var.set("")
        messagebox.showerror("Submission Failed", f"Autotask API error:\n\n{msg}")

    def _validate(self):
        errors = []
        if not self._company:
            errors.append("Select a valid company before submitting.")
        if not self._title_var.get().strip():
            errors.append("Ticket title cannot be empty.")
        if not self._summary_text.get("1.0", tk.END).strip():
            errors.append("Summary cannot be empty.")
        if not self._get_wt_id():
            errors.append("Select a Work Type.")
        return errors

    def _get_wt_id(self):
        name = self._work_type_var.get()
        for wt in self._work_types:
            if wt.name == name:
                return wt.id
        return None


class CompanyPickerDialog(tk.Toplevel):
    def __init__(self, parent, companies):
        super().__init__(parent)
        self.title("Select Company")
        self.resizable(False, False)
        self.grab_set()
        self.configure(bg=CARD)
        self.selected = None

        tk.Label(self, text="Multiple matches \u2014 select the correct company:",
                 font=FONT_BODY, bg=CARD, fg=FG).pack(padx=16, pady=(14, 8))

        lf = tk.Frame(self, bg=CARD)
        lf.pack(fill=tk.BOTH, expand=True, padx=16)
        sb = ttk.Scrollbar(lf)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._lb = tk.Listbox(lf, yscrollcommand=sb.set,
                              selectmode=tk.SINGLE, height=10,
                              font=FONT_BODY, bg=CARD, fg=FG,
                              selectbackground=ACCENT_LT,
                              selectforeground=FG,
                              relief=tk.SOLID, bd=1)
        self._lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=self._lb.yview)

        self._companies = companies
        for c in companies:
            self._lb.insert(tk.END, c.name)
        if companies:
            self._lb.selection_set(0)

        bf = tk.Frame(self, bg=CARD)
        bf.pack(fill=tk.X, padx=16, pady=(8, 14))
        mac_btn(bf, "Cancel", self.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        mac_btn(bf, "Select", self._select, primary=True).pack(side=tk.RIGHT)
        self._lb.bind("<Double-Button-1>", lambda _: self._select())

    def _select(self):
        sel = self._lb.curselection()
        if sel:
            self.selected = self._companies[sel[0]]
        self.destroy()
