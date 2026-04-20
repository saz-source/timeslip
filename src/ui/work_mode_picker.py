"""
First-run dialog to let the user map their Autotask work types
to "Onsite" and "Offsite / Remote" billing codes.
"""
import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Optional

from src.autotask_client import WorkType

if TYPE_CHECKING:
    from src.ui.app import App


class WorkModePicker(tk.Toplevel):
    def __init__(self, parent: tk.Misc, work_types: list[WorkType], app: "App") -> None:
        super().__init__(parent)
        self.title("First-Run Setup — Work Type Mapping")
        self.resizable(False, False)
        self.grab_set()
        self.app = app
        self._work_types = work_types
        self._build()

    def _build(self) -> None:
        pad = {"padx": 20, "pady": 6}

        ttk.Label(
            self,
            text="Map Work Types",
            font=("SF Pro Display", 16, "bold"),
        ).pack(pady=(20, 4))

        ttk.Label(
            self,
            text=(
                "Select which Autotask billing codes correspond to\n"
                "Onsite and Offsite work. This is cached and only asked once."
            ),
            justify=tk.CENTER,
        ).pack(**pad)

        names = [wt.name for wt in self._work_types] if self._work_types else ["(none available)"]

        # Onsite
        ttk.Label(self, text="Onsite / On-site work type:").pack(anchor=tk.W, **pad)
        self._onsite_var = tk.StringVar()
        ttk.Combobox(self, textvariable=self._onsite_var, values=names, state="readonly", width=40).pack(
            padx=20
        )
        if names:
            self._onsite_var.set(names[0])

        # Offsite
        ttk.Label(self, text="Offsite / Remote work type:").pack(anchor=tk.W, **pad)
        self._offsite_var = tk.StringVar()
        ttk.Combobox(self, textvariable=self._offsite_var, values=names, state="readonly", width=40).pack(
            padx=20
        )
        if len(names) > 1:
            self._offsite_var.set(names[1])
        elif names:
            self._offsite_var.set(names[0])

        # Buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=(16, 20))
        ttk.Button(btn_frame, text="Skip", command=self.destroy).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="Save", command=self._save, style="Primary.TButton").pack(side=tk.LEFT)

    def _save(self) -> None:
        onsite_name = self._onsite_var.get()
        offsite_name = self._offsite_var.get()

        onsite_id = next((wt.id for wt in self._work_types if wt.name == onsite_name), None)
        offsite_id = next((wt.id for wt in self._work_types if wt.name == offsite_name), None)

        if onsite_id:
            self.app.cache.set_onsite_work_type_id(onsite_id)
        if offsite_id:
            self.app.cache.set_offsite_work_type_id(offsite_id)

        self.destroy()
