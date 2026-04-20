"""
Background update checker. Hits GitHub Releases API on launch,
compares tag with current VERSION, returns result via callback.
Never blocks the UI.
"""
import threading
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

RELEASES_API = "https://api.github.com/repos/saz-source/timeslip/releases/latest"
RELEASES_PAGE = "https://github.com/saz-source/timeslip/releases/latest"


def _parse_version(tag: str) -> tuple:
    """'v1.32' or '1.32' → (1, 32)"""
    return tuple(int(x) for x in tag.lstrip("v").split(".") if x.isdigit())


def check_for_update(
    current_version: str,
    on_update_available: Callable[[str, str], None],
    on_up_to_date: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Spawn a background thread to check for updates.
    Calls on_update_available(latest_version, download_url) if newer release exists.
    Calls on_up_to_date(latest_version) if already current.
    """
    def worker():
        try:
            import requests
            r = requests.get(RELEASES_API, timeout=8,
                             headers={"Accept": "application/vnd.github+json"})
            if r.status_code == 404:
                return  # no releases yet
            r.raise_for_status()
            data = r.json()
            tag = data.get("tag_name", "")
            if not tag:
                return
            if _parse_version(tag) > _parse_version(current_version):
                assets = data.get("assets", [])
                dmg = next((a["browser_download_url"] for a in assets
                            if a.get("name", "").endswith(".dmg")), None)
                url = dmg or data.get("html_url", RELEASES_PAGE)
                on_update_available(tag.lstrip("v"), url)
            elif on_up_to_date:
                on_up_to_date(tag.lstrip("v"))
        except Exception as exc:
            logger.debug("Update check failed (non-critical): %s", exc)

    threading.Thread(target=worker, daemon=True).start()
