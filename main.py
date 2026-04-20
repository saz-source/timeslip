#!/usr/bin/env python3
"""
Autotask Time Entry App
"""
import sys
import logging
from pathlib import Path

# Ensure src is importable whether run from source or as a bundled app
if getattr(sys, "frozen", False):
    # Running as PyInstaller bundle
    BASE_DIR = Path(sys._MEIPASS)
    sys.path.insert(0, str(BASE_DIR))
else:
    BASE_DIR = Path(__file__).parent
    sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv

ENV_LOCATIONS = [
    Path(__file__).parent / ".env",
    Path.home() / ".autotask_time_entry" / ".env",
    Path.home() / "Library" / "Application Support" / "AutotaskTimeEntry" / ".env",
]


def _load_env():
    for env_path in ENV_LOCATIONS:
        if env_path.exists():
            load_dotenv(env_path, override=True)
            return


def _setup_logging() -> None:
    log_dir = Path.home() / ".autotask_time_entry"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "app.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main() -> None:
    _setup_logging()
    _load_env()

    from src.ui.first_run import needs_setup, FirstRunSetup

    if needs_setup():
        wizard = FirstRunSetup()
        wizard.mainloop()
        if not wizard.completed:
            sys.exit(0)
        _load_env()
        # Clear stale cache so new user starts fresh
        for stale in [
            Path.home() / ".autotask_time_entry" / "cache.json",
            Path.home() / ".autotask_time_entry" / "history.json",
        ]:
            stale.unlink(missing_ok=True)

    from src.config import load_config
    from src.autotask_client import AutotaskClient
    from src.anthropic_client import AnthropicClient
    from src.cache import Cache
    from src.ui.app import App

    try:
        config = load_config()
    except EnvironmentError as e:
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Configuration Error",
                f"{e}\n\nPlace your .env file at:\n"
                f"{Path.home() / '.autotask_time_entry' / '.env'}"
            )
            root.destroy()
        except Exception:
            print(f"\n[CONFIG ERROR] {e}")
        sys.exit(1)

    cache = Cache()
    autotask = AutotaskClient(config)
    anthropic_client = AnthropicClient(config)
    app = App(config=config, autotask=autotask,
              anthropic=anthropic_client, cache=cache)
    app.run()


if __name__ == "__main__":
    main()
