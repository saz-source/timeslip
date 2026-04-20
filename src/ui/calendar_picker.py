"""
Lightweight calendar popup — pure tkinter, Sunday-first US convention.
"""
import calendar
import tkinter as tk
from datetime import date
from src.ui.styles import ACCENT, ACCENT_DK, ACCENT_LT, CARD, FG, FG2, BORDER, FONT_SM, FONT_BOLD

# Sunday-first week order
DAY_NAMES = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]
WEEKEND_COLS = {0, 6}   # Su=0, Sa=6


def _month_calendar_sun_first(year, month):
    """Return 6-week grid (list of 7-element lists) with Sunday as first day."""
    calendar.setfirstweekday(6)   # 6 = Sunday
    weeks = calendar.monthcalendar(year, month)
    calendar.setfirstweekday(0)   # reset to Monday default
    # Reorder each week: monthcalendar with firstweekday=6 gives Sun..Sat
    return weeks


class CalendarPicker(tk.Toplevel):
    def __init__(self, parent, initial_date: date, callback, anchor_widget=None):
        super().__init__(parent)
        self.overrideredirect(False)
        self.configure(bg=BORDER)
        self.resizable(False, False)

        self._callback = callback
        self._viewing = initial_date.replace(day=1)
        self._selected = initial_date
        self._closing = False

        self._build()
        self._render()

        self.update_idletasks()
        if anchor_widget:
            x = anchor_widget.winfo_rootx()
            y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + 2
        else:
            x = parent.winfo_pointerx()
            y = parent.winfo_pointery() + 4

        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        if x + w > sw:
            x = sw - w - 4
        if y + h > sh:
            y = (anchor_widget.winfo_rooty() - h - 2
                 if anchor_widget else sh - h - 4)

        self.geometry(f"+{x}+{y}")
        self.lift()
        self.focus_force()
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<Escape>", lambda _: self.destroy())

    def _build(self):
        outer = tk.Frame(self, bg=BORDER, padx=1, pady=1)
        outer.pack(fill=tk.BOTH, expand=True)
        inner = tk.Frame(outer, bg=CARD)
        inner.pack(fill=tk.BOTH, expand=True)

        # Nav bar
        nav = tk.Frame(inner, bg=ACCENT)
        nav.pack(fill=tk.X)

        self._prev_lbl = tk.Label(nav, text="  \u2039  ", font=FONT_BOLD,
                                  bg=ACCENT, fg="white", cursor="hand2",
                                  padx=6, pady=6)
        self._prev_lbl.pack(side=tk.LEFT)
        self._prev_lbl.bind("<Button-1>", lambda _: self._prev_month())
        self._prev_lbl.bind("<Enter>", lambda _: self._prev_lbl.configure(bg=ACCENT_DK))
        self._prev_lbl.bind("<Leave>", lambda _: self._prev_lbl.configure(bg=ACCENT))

        self._month_lbl = tk.Label(nav, text="", font=FONT_BOLD,
                                   bg=ACCENT, fg="white", padx=8, pady=6)
        self._month_lbl.pack(side=tk.LEFT, expand=True)

        self._next_lbl = tk.Label(nav, text="  \u203a  ", font=FONT_BOLD,
                                  bg=ACCENT, fg="white", cursor="hand2",
                                  padx=6, pady=6)
        self._next_lbl.pack(side=tk.RIGHT)
        self._next_lbl.bind("<Button-1>", lambda _: self._next_month())
        self._next_lbl.bind("<Enter>", lambda _: self._next_lbl.configure(bg=ACCENT_DK))
        self._next_lbl.bind("<Leave>", lambda _: self._next_lbl.configure(bg=ACCENT))

        # Day-name header — Su Mo Tu We Th Fr Sa
        hdr = tk.Frame(inner, bg=ACCENT_LT)
        hdr.pack(fill=tk.X)
        for i, d in enumerate(DAY_NAMES):
            fg = "#cc3333" if i in WEEKEND_COLS else FG2
            tk.Label(hdr, text=d, font=FONT_SM, bg=ACCENT_LT,
                     fg=fg, width=3, anchor=tk.CENTER,
                     pady=3).pack(side=tk.LEFT)

        # Day grid
        self._grid_frame = tk.Frame(inner, bg=CARD)
        self._grid_frame.pack(padx=4, pady=(2, 2))
        self._day_btns = []
        for r in range(6):
            row_btns = []
            for c in range(7):
                lbl = tk.Label(self._grid_frame, text="", width=3,
                               font=FONT_SM, cursor="hand2",
                               bg=CARD, fg=FG, anchor=tk.CENTER,
                               padx=2, pady=4)
                lbl.grid(row=r, column=c, padx=1, pady=1)
                row_btns.append(lbl)
            self._day_btns.append(row_btns)

        # Today button
        foot = tk.Frame(inner, bg=CARD)
        foot.pack(fill=tk.X, pady=(2, 6))
        today_lbl = tk.Label(foot, text="Today", font=FONT_SM,
                             bg=ACCENT_LT, fg=ACCENT, cursor="hand2",
                             padx=12, pady=4)
        today_lbl.pack()
        today_lbl.bind("<Button-1>", lambda _: self._select(date.today()))
        today_lbl.bind("<Enter>", lambda _: today_lbl.configure(bg=ACCENT, fg="white"))
        today_lbl.bind("<Leave>", lambda _: today_lbl.configure(bg=ACCENT_LT, fg=ACCENT))

    def _render(self):
        today = date.today()
        d = self._viewing
        self._month_lbl.configure(text=d.strftime("%B %Y"))

        weeks = _month_calendar_sun_first(d.year, d.month)
        while len(weeks) < 6:
            weeks.append([0] * 7)

        for r, week in enumerate(weeks):
            for c, day in enumerate(week):
                lbl = self._day_btns[r][c]
                if day == 0:
                    lbl.configure(text="", bg=CARD, cursor="")
                    for ev in ("<Button-1>", "<Enter>", "<Leave>"):
                        lbl.unbind(ev)
                else:
                    this_date = date(d.year, d.month, day)
                    is_selected = (this_date == self._selected)
                    is_today = (this_date == today)
                    is_weekend = (c in WEEKEND_COLS)

                    if is_selected:
                        bg, fg = ACCENT, "white"
                    elif is_today:
                        bg, fg = ACCENT_LT, ACCENT
                    else:
                        bg = CARD
                        fg = "#cc3333" if is_weekend else FG

                    lbl.configure(text=str(day), bg=bg, fg=fg, cursor="hand2")

                    def make(td=this_date, lb=lbl, sel=is_selected,
                             nbg=bg, nfg=fg):
                        def enter(_):
                            if not sel:
                                lb.configure(bg=ACCENT_LT, fg=ACCENT)
                        def leave(_):
                            if not sel:
                                lb.configure(bg=nbg, fg=nfg)
                        def click(_):
                            self._select(td)
                        return enter, leave, click

                    en, le, cl = make()
                    lbl.bind("<Enter>", en)
                    lbl.bind("<Leave>", le)
                    lbl.bind("<Button-1>", cl)

    def _select(self, d: date):
        self._closing = True
        self._callback(d)
        self.destroy()

    def _prev_month(self):
        y, m = self._viewing.year, self._viewing.month
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        self._viewing = date(y, m, 1)
        self._render()

    def _next_month(self):
        y, m = self._viewing.year, self._viewing.month
        m += 1
        if m == 13:
            y, m = y + 1, 1
        self._viewing = date(y, m, 1)
        self._render()

    def _on_focus_out(self, event):
        if self._closing:
            return
        try:
            focused = self.focus_get()
            if focused and str(focused).startswith(str(self)):
                return
        except Exception:
            pass
        self.after(200, self._maybe_close)

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
