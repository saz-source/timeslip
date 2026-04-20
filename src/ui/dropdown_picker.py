"""
Custom dropdown popup — pure tkinter, works correctly on macOS.
Replaces ttk.Combobox which has focus/dismiss issues on macOS.
"""
import tkinter as tk
from src.ui.styles import ACCENT, ACCENT_LT, CARD, FG, FG2, BORDER, FONT_BODY, FONT_SM


class DropdownPicker(tk.Toplevel):
    """
    Popup list that appears below an anchor widget.
    Closes cleanly when clicking outside or selecting an item.
    callback(value) is called with the selected string.
    """
    def __init__(self, parent, anchor_widget, values, current_value,
                 callback, width=None):
        super().__init__(parent)
        self.overrideredirect(True)
        self.configure(bg=BORDER)
        self.resizable(False, False)

        self._callback = callback
        self._closing = False

        # Build listbox
        outer = tk.Frame(self, bg=BORDER, padx=1, pady=1)
        outer.pack(fill=tk.BOTH, expand=True)

        frame = tk.Frame(outer, bg=CARD)
        frame.pack(fill=tk.BOTH, expand=True)

        # Scrollbar + Listbox
        sb = tk.Scrollbar(frame, orient=tk.VERTICAL)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        lb_width = width or max((len(v) for v in values), default=10) + 2
        visible = min(len(values), 12)

        self._lb = tk.Listbox(
            frame,
            font=FONT_BODY,
            bg=CARD, fg=FG,
            selectbackground=ACCENT,
            selectforeground="white",
            activestyle="none",
            relief=tk.FLAT,
            bd=0,
            width=lb_width,
            height=visible,
            yscrollcommand=sb.set,
            cursor="hand2",
            exportselection=False,
        )
        sb.config(command=self._lb.yview)
        self._lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        for v in values:
            self._lb.insert(tk.END, v)

        # Highlight and scroll to current value
        if current_value in values:
            idx = values.index(current_value)
            self._lb.selection_set(idx)
            self._lb.see(idx)
        elif values:
            self._lb.selection_set(0)
            self._lb.see(0)

        self._lb.bind("<Button-1>", self._on_click)
        self._lb.bind("<Return>", self._on_enter)
        self._lb.bind("<Double-Button-1>", self._on_click)

        # Position below anchor
        self.update_idletasks()
        x = anchor_widget.winfo_rootx()
        y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + 1
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        if x + w > sw:
            x = sw - w - 4
        if y + h > sh:
            y = anchor_widget.winfo_rooty() - h - 1

        self.geometry(f"+{x}+{y}")
        self.lift()
        self._lb.focus_set()

        # Close on focus loss
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<Escape>", lambda _: self.destroy())

    def _on_click(self, event):
        idx = self._lb.nearest(event.y)
        if idx >= 0:
            self._lb.selection_clear(0, tk.END)
            self._lb.selection_set(idx)
            self._select(self._lb.get(idx))

    def _on_enter(self, event):
        sel = self._lb.curselection()
        if sel:
            self._select(self._lb.get(sel[0]))

    def _select(self, value):
        self._closing = True
        self._callback(value)
        self.destroy()

    def _on_focus_out(self, event):
        if self._closing:
            return
        try:
            focused = self.focus_get()
            if focused and str(focused).startswith(str(self)):
                return
        except Exception:
            pass
        self.after(150, self._maybe_close)

    def _maybe_close(self):
        if self._closing or not self.winfo_exists():
            return
        try:
            focused = self.focus_get()
            if focused and str(focused).startswith(str(self)):
                return
        except Exception:
            pass
        self.destroy()
