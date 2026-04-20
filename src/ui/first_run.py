"""
First-run setup screen.
Fetches shared company config from GitHub Gist, reads a .lic file
for sensitive credentials, collects personal email. Writes ~/.autotask_time_entry/.env.
"""
import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

from src.ui.styles import (
    BG, CARD, ACCENT, ACCENT_LT, FG, FG2, BORDER, DIVIDER,
    FONT_BODY, FONT_BOLD, FONT_HDR, FONT_SM,
    mac_btn,
)

ENV_PATH = Path.home() / ".autotask_time_entry" / ".env"

SHARED_CONFIG_URL = "https://gist.githubusercontent.com/saz-source/366835bb3c0a47585d86c11e18a60d94/raw/94432dc1118d456fc4cedc4164c49e2cbcda5601/timeslip_config.json"

LIC_REQUIRED_KEYS = {"ANTHROPIC_API_KEY", "AUTOTASK_USERNAME", "AUTOTASK_SECRET"}


def needs_setup() -> bool:
    if not ENV_PATH.exists():
        return True
    env = ENV_PATH.read_text()
    return not all(k in env for k in LIC_REQUIRED_KEYS)


class FirstRunSetup(tk.Tk):
    """
    Standalone setup wizard shown on first launch. Runs its own mainloop.
    Call mainloop() to block until done, then check .completed.
    """
    def __init__(self):
        super().__init__()
        self.title("TimeSlip — First Time Setup")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self._shared_config: Optional[dict] = None
        self._lic_data: Optional[dict] = None
        self._success = False
        self._fetch_result = None  # None=pending, dict=ok, "ERROR:..."|str=fail

        self._build()
        self._center()
        self.lift()
        self.focus_force()

        self.after(300, self._start_fetch)

    def _build(self):
        hdr = tk.Frame(self, bg=ACCENT, pady=9)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="  TimeSlip — First Time Setup",
                 font=FONT_HDR, bg=ACCENT, fg="white").pack(side=tk.LEFT)

        card = tk.Frame(self, bg=CARD,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        tk.Label(card, text="Welcome to TimeSlip!",
                 font=FONT_BOLD, bg=CARD, fg=FG).pack(pady=(16, 2))
        tk.Label(card,
                 text="You'll need your TimeSlip license file (.lic) and your JDK email.",
                 font=FONT_SM, bg=CARD, fg=FG2, wraplength=380).pack(pady=(0, 16))

        tk.Frame(card, bg=DIVIDER, height=1).pack(fill=tk.X, padx=20, pady=(0, 14))

        # ── License file ──
        tk.Label(card, text="TimeSlip License File (.lic):",
                 font=FONT_BODY, bg=CARD, fg=FG2).pack(anchor=tk.W, padx=20)

        lic_row = tk.Frame(card, bg=CARD)
        lic_row.pack(fill=tk.X, padx=20, pady=(4, 2))

        self._lic_path_var = tk.StringVar(value="No file selected")
        self._lic_lbl = tk.Label(lic_row, textvariable=self._lic_path_var,
                                  font=FONT_SM, bg=ACCENT_LT, fg=FG2,
                                  anchor=tk.W, padx=8, pady=6,
                                  relief=tk.FLAT, width=32)
        self._lic_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        mac_btn(lic_row, "Browse…", self._browse_lic).pack(side=tk.LEFT, padx=(6, 0))

        self._lic_status = tk.Label(card, text="",
                                     font=FONT_SM, bg=CARD, fg=FG2)
        self._lic_status.pack(anchor=tk.W, padx=20, pady=(2, 4))

        tk.Label(card,
                 text="Your .lic file was sent to you by your admin via email or Dropbox.",
                 font=FONT_SM, bg=CARD, fg=FG2, wraplength=380).pack(
            anchor=tk.W, padx=20, pady=(0, 14))

        tk.Frame(card, bg=DIVIDER, height=1).pack(fill=tk.X, padx=20, pady=(0, 14))

        # ── Email ──
        tk.Label(card, text="Your JDK Email Address:",
                 font=FONT_BODY, bg=CARD, fg=FG2).pack(anchor=tk.W, padx=20)
        self._email_var = tk.StringVar()
        tk.Entry(card, textvariable=self._email_var,
                 font=FONT_BODY, width=36,
                 bg=CARD, fg=FG, insertbackground=ACCENT,
                 relief=tk.FLAT, highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACCENT).pack(
            padx=20, pady=(4, 4), fill=tk.X)
        tk.Label(card,
                 text="e.g. mike.saz@jdkconsulting.com  —  used so time entries appear under your name.",
                 font=FONT_SM, bg=CARD, fg=FG2, wraplength=380, justify=tk.LEFT).pack(
            anchor=tk.W, padx=20, pady=(0, 14))

        # ── Status ──
        self._status_var = tk.StringVar(value="Fetching company config…")
        tk.Label(card, textvariable=self._status_var,
                 font=FONT_BOLD, bg=CARD, fg=ACCENT).pack(pady=(0, 8))

        # ── Buttons ──
        tk.Frame(self, bg=DIVIDER, height=1).pack(fill=tk.X)
        bf = tk.Frame(self, bg=BG)
        bf.pack(fill=tk.X, padx=20, pady=10)
        mac_btn(bf, "Cancel", self._on_cancel).pack(side=tk.LEFT)
        self._setup_btn = mac_btn(bf, "  Set Up TimeSlip  ",
                                   self._do_setup, primary=True)
        self._setup_btn.pack(side=tk.RIGHT)

    def _center(self):
        self.update_idletasks()
        w = 460
        h = self.winfo_reqheight()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    # ── Config fetch (thread + poll) ──

    def _start_fetch(self):
        self._status_var.set("Fetching company config…")
        self._fetch_result = None

        def worker():
            try:
                import requests as req
                r = req.get(SHARED_CONFIG_URL, timeout=10)
                r.raise_for_status()
                self._fetch_result = r.json()
            except Exception as exc:
                self._fetch_result = f"ERROR:{exc}"

        threading.Thread(target=worker, daemon=True).start()
        self.after(100, self._poll_fetch)

    def _poll_fetch(self):
        if self._fetch_result is None:
            self.after(100, self._poll_fetch)
            return
        if isinstance(self._fetch_result, dict):
            self._shared_config = self._fetch_result
            self._status_var.set("✓  Company config loaded")
        else:
            self._status_var.set("⚠  Could not fetch company config — check internet")

    # ── License file ──

    def _browse_lic(self):
        path = filedialog.askopenfilename(
            title="Select your TimeSlip license file",
            filetypes=[("License file", "*.lic"), ("All files", "*.*")],
        )
        if not path:
            return
        self._load_lic(Path(path))

    def _load_lic(self, path: Path):
        try:
            data = json.loads(path.read_text())
        except Exception as exc:
            self._lic_status.configure(text=f"⚠  Could not read file: {exc}", fg="#cc0000")
            self._lic_data = None
            return

        missing = LIC_REQUIRED_KEYS - data.keys()
        if missing:
            self._lic_status.configure(
                text=f"⚠  Missing keys: {', '.join(sorted(missing))}", fg="#cc0000")
            self._lic_data = None
            return

        self._lic_data = data
        self._lic_path_var.set(path.name)
        self._lic_lbl.configure(fg=FG)
        self._lic_status.configure(text="✓  License file loaded", fg="#1a7f37")

    # ── Submit ──

    def _do_setup(self):
        email = self._email_var.get().strip()
        errors = []

        if not self._lic_data:
            errors.append("Please select your TimeSlip license file (.lic).")
        if not email or "@" not in email:
            errors.append("Your JDK email address is required.")
        if not self._shared_config:
            errors.append("Company config not loaded yet — please wait a moment and try again.")

        if errors:
            messagebox.showwarning("Missing Info", "\n".join(f"  • {e}" for e in errors))
            return

        ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for key in ["AUTOTASK_BASE_URL", "AUTOTASK_INTEGRATION_CODE",
                    "AUTOTASK_ROLE_ID", "COMPANY_NAME"]:
            if key in self._shared_config:
                lines.append(f"{key}={self._shared_config[key]}")
        for key in sorted(LIC_REQUIRED_KEYS):
            lines.append(f"{key}={self._lic_data[key]}")
        lines.append(f"AUTOTASK_RESOURCE_EMAIL={email}")
        ENV_PATH.write_text("\n".join(lines) + "\n")

        self._success = True
        self.destroy()

    def _on_cancel(self):
        self._success = False
        self.destroy()

    @property
    def completed(self) -> bool:
        return self._success
