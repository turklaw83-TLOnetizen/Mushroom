"""Folder drag-and-drop Streamlit component.

Renders a drop zone that accepts entire folders from Windows Explorer.
Uses the browser FileSystem API (webkitGetAsEntry) to recursively read
folder contents and send METADATA ONLY (names, sizes, paths) back to
Python.  Python then locates the folder on disk and reads the actual
files — no browser memory limits, works for any folder size.
"""

import logging
from pathlib import Path
from typing import Optional

import streamlit.components.v1 as components

logger = logging.getLogger(__name__)

_FRONTEND_DIR = Path(__file__).parent / "folder_drop_frontend"

_folder_drop_func = components.declare_component(
    "folder_drop_zone",
    path=str(_FRONTEND_DIR),
)


def folder_drop_zone(
    supported_extensions: Optional[list] = None,
    height: int = 120,
    key: Optional[str] = None,
) -> Optional[dict]:
    """Render a folder drag-and-drop zone.

    Parameters
    ----------
    supported_extensions : list of str, optional
        File extensions to accept (e.g. [".pdf", ".docx"]).
    height : int
        Drop zone height in pixels.
    key : str, optional
        Streamlit widget key.

    Returns
    -------
    dict or None
        ``{"folder_name": str, "files": [{"name", "relative_path", "size"}], "total_bytes": int}``
        or None if nothing dropped yet.
    """
    result = _folder_drop_func(
        supported_extensions=supported_extensions or [],
        height=height,
        key=key,
        default=None,
    )
    return result


# Common locations to search for a dropped folder (Windows-centric)
_SEARCH_BASES = None


def _get_search_bases():
    """Build the list of directories to search, cached after first call."""
    global _SEARCH_BASES
    if _SEARCH_BASES is not None:
        return _SEARCH_BASES
    home = Path.home()
    bases = [
        home / "Desktop",
        home / "Downloads",
        home / "Documents",
        home / "OneDrive" / "Desktop",
        home / "OneDrive" / "Documents",
        home / "OneDrive" / "Downloads",
        home,
    ]
    # Also check drive roots for top-level folders
    for letter in ("C", "D", "E", "F"):
        p = Path(f"{letter}:/")
        if p.exists():
            bases.append(p)
    _SEARCH_BASES = [b for b in bases if b.exists()]
    return _SEARCH_BASES


def _search_dir_recursive(base: Path, target: str, depth: int) -> Optional[Path]:
    """DFS for *target* folder name starting at *base*, up to *depth* levels."""
    if depth <= 0:
        return None
    try:
        for child in base.iterdir():
            if not child.is_dir():
                continue
            if child.name == target:
                return child
            # Skip hidden / system folders
            if child.name.startswith(".") or child.name.startswith("$"):
                continue
            found = _search_dir_recursive(child, target, depth - 1)
            if found:
                return found
    except (PermissionError, OSError):
        pass
    return None


def find_folder_on_disk(folder_name: str) -> Optional[Path]:
    """Search common Windows locations for a folder by name.

    Strategy (fast → slow):
      1. Direct children of all search bases  (instant)
      2. Up to 3 levels deep in user dirs     (fast)
      3. Up to 2 levels deep in drive roots   (medium)

    Returns the first match found, or None.
    """
    if not folder_name:
        return None

    bases = _get_search_bases()

    # --- Pass 1: direct children (O(1) per base) ---
    for base in bases:
        candidate = base / folder_name
        if candidate.is_dir():
            logger.info("find_folder_on_disk: found %s at %s (direct)", folder_name, candidate)
            return candidate

    # --- Pass 2: deeper search in user directories (up to 3 levels) ---
    home = Path.home()
    user_dirs = [
        home / "Desktop",
        home / "Downloads",
        home / "Documents",
        home / "OneDrive" / "Desktop",
        home / "OneDrive" / "Documents",
        home / "OneDrive" / "Downloads",
        home,
    ]
    for base in user_dirs:
        if not base.exists():
            continue
        found = _search_dir_recursive(base, folder_name, depth=3)
        if found:
            logger.info("find_folder_on_disk: found %s at %s (deep search)", folder_name, found)
            return found

    # --- Pass 3: shallow search on drive roots (2 levels) ---
    for letter in ("C", "D", "E", "F"):
        root = Path(f"{letter}:/")
        if root.exists():
            found = _search_dir_recursive(root, folder_name, depth=2)
            if found:
                logger.info("find_folder_on_disk: found %s at %s (drive root)", folder_name, found)
                return found

    logger.warning("find_folder_on_disk: could not locate '%s'", folder_name)
    return None
