"""
Shared style constants and helpers. Autotask-matched palette.
mac_btn uses Label-based buttons to avoid macOS Tk color overrides.
"""
import tkinter as tk
from tkinter import ttk

BG        = "#f0f4f8"
CARD      = "#ffffff"
ACCENT    = "#1B5EA6"
ACCENT_DK = "#154d8a"
ACCENT_LT = "#e8f0fb"
FG        = "#1a2a3a"
FG2       = "#5a6a7a"
FG3       = "#8a9aaa"
BORDER    = "#c8d4e0"
SUCCESS   = "#1a7f37"
WARN      = "#cc6600"
ERR       = "#cc0000"
DIVIDER   = "#dde4ec"

FONT_HDR  = ("SF Pro Display", 15, "bold")
FONT_BODY = ("SF Pro Text", 13)
FONT_SM   = ("SF Pro Text", 11)
FONT_BOLD = ("SF Pro Text", 13, "bold")
FONT_MONO = ("Menlo", 12)


def _set_bg(widget, color):
    """Set widget background using raw Tk call — avoids recursion."""
    try:
        widget.tk.call(str(widget), "configure", "-bg", color)
    except Exception:
        pass


def mac_btn(parent, text, cmd, primary=False, small=False, danger=False):
    """
    Label-based button. macOS Tk cannot override Label bg,
    so color always shows correctly regardless of window focus.
    Uses raw tk.call for frame bg to avoid overriding tkinter's configure.
    """
    if primary:
        bg, fg, hover = ACCENT, "white", ACCENT_DK
    elif danger:
        bg, fg, hover = "#cc0000", "white", "#aa0000"
    else:
        bg, fg, hover = "#e0e6ed", FG, "#c8d4e0"

    font = FONT_SM if small else FONT_BOLD if primary else FONT_BODY
    px, py = (10, 4) if small else (18, 8)

    frame = tk.Frame(parent, bg=bg, cursor="hand2")
    lbl = tk.Label(frame, text=text, font=font,
                   bg=bg, fg=fg, padx=px, pady=py, cursor="hand2")
    lbl.pack()

    _s = {"disabled": False, "bg": bg, "hover": hover, "fg": fg}

    def on_enter(_):
        if not _s["disabled"]:
            lbl.configure(bg=_s["hover"])
            _set_bg(frame, _s["hover"])

    def on_leave(_):
        if not _s["disabled"]:
            lbl.configure(bg=_s["bg"])
            _set_bg(frame, _s["bg"])

    def on_click(_):
        if not _s["disabled"]:
            cmd()

    for w in (frame, lbl):
        w.bind("<Enter>", on_enter)
        w.bind("<Leave>", on_leave)
        w.bind("<Button-1>", on_click)

    def configure_btn(state=None, bg=None, **kw):
        if state == "disabled":
            _s["disabled"] = True
            dbg = "#8aaac8" if primary else "#d0d8e0"
            dfg = "white" if primary else "#999"
            lbl.configure(bg=dbg, fg=dfg)
            _set_bg(frame, dbg)
        elif state == "normal":
            _s["disabled"] = False
            lbl.configure(bg=_s["bg"], fg=_s["fg"])
            _set_bg(frame, _s["bg"])
        if bg is not None:
            _s["bg"] = bg
            if not _s["disabled"]:
                lbl.configure(bg=bg)
                _set_bg(frame, bg)

    frame.configure_btn = configure_btn
    return frame


def section_header(parent, text, bg=ACCENT):
    bar = tk.Frame(parent, bg=bg, pady=9)
    bar.pack(fill="x")
    tk.Label(bar, text=f"  {text}",
             font=FONT_HDR, bg=bg, fg="white").pack(side="left")
    return bar


def divider(parent, bg=DIVIDER):
    tk.Frame(parent, bg=bg, height=1).pack(fill="x")


def field_label(parent, text, row, bg=CARD, top=False):
    anchor = "nw" if top else "w"
    pady = (10, 4) if top else 5
    tk.Label(parent, text=text + ":",
             font=("SF Pro Text", 12), bg=bg, fg=FG2).grid(
        row=row, column=0, sticky=anchor, padx=(14, 10), pady=pady)


def styled_entry(parent, var, width=None):
    kw = dict(textvariable=var, font=FONT_BODY,
              bg=CARD, fg=FG, insertbackground=ACCENT,
              relief="flat", bd=0,
              highlightthickness=1,
              highlightcolor=ACCENT,
              highlightbackground=BORDER)
    if width:
        kw["width"] = width
    return tk.Entry(parent, **kw)


def styled_text(parent, height=8, readonly=False, mono=False):
    font = FONT_MONO if mono else FONT_BODY
    bg = "#f7f9fc" if readonly else CARD
    fg = FG2 if readonly else FG
    t = tk.Text(parent, height=height, wrap="word",
                font=font, relief="flat", borderwidth=0,
                highlightthickness=1,
                highlightbackground=BORDER,
                highlightcolor=ACCENT,
                padx=8, pady=6, bg=bg, fg=fg,
                insertbackground=ACCENT,
                selectbackground=ACCENT_LT,
                selectforeground=FG)
    if readonly:
        t.configure(state="disabled")
    return t
