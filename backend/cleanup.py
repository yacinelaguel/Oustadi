# =============================================================================
#  OSTADI — أستاذي
#  Ephemeral File Deletion Background Task Engine
#  Architect: Yacine Laguel
#  File: backend/cleanup.py
#
#  Responsibilities:
#    1. Accept a list of file paths and a delay in seconds
#    2. Sleep asynchronously for exactly that delay (default: 1800s = 30 min)
#    3. Attempt deletion of every file in the list after the delay elapses
#    4. Log every deletion outcome — success, already gone, or OS error
#    5. Never raise an exception that could crash the FastAPI worker
#
#  This module is called exclusively via FastAPI BackgroundTasks in main.py.
#  It runs in the same process as the server but in a background coroutine,
#  meaning it does not block any incoming HTTP request.
#
#  Design guarantees:
#    - Files are ALWAYS deleted eventually, even if the client disconnects.
#    - If a file was already deleted (e.g. manually purged by admin),
#      the function logs a warning and continues — it never crashes.
#    - A startup purge in main.py handles files from crashed sessions.
# =============================================================================

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import List, Union

# ---------------------------------------------------------------------------
# MODULE LOGGER
# ---------------------------------------------------------------------------
log = logging.getLogger("ostadi.cleanup")


# =============================================================================
#  CORE DELETION WORKER
# =============================================================================

async def schedule_file_deletion(
    file_paths: List[Union[str, Path]],
    delay_seconds: int = 1800,
    session_id: str = "UNKNOWN",
) -> None:
    """
    Schedules the permanent deletion of a list of files after a fixed delay.

    This coroutine is designed to be registered with FastAPI's BackgroundTasks
    system. It sleeps for `delay_seconds` without blocking the event loop,
    then iterates through every file path and attempts hard deletion.

    Args:
        file_paths:     List of absolute file paths (str or Path) to delete.
        delay_seconds:  Number of seconds to wait before deleting.
                        Default is 1800 (30 minutes).
        session_id:     The generation session ID — used only for logging.

    Behaviour:
        - If a file does not exist at deletion time → logs WARNING, continues.
        - If a file exists but cannot be deleted (permissions) → logs ERROR,
          continues. Never raises.
        - After all deletions are attempted, logs a summary report.
    """

    # Normalise all paths to Path objects up front
    resolved_paths: List[Path] = [
        Path(p).resolve() for p in file_paths
    ]

    file_count = len(resolved_paths)

    log.info(
        f"[{session_id}] Ephemeral cleanup scheduled: "
        f"{file_count} file(s) will be deleted in "
        f"{delay_seconds // 60}m {delay_seconds % 60}s"
    )

    # Log each file that is scheduled for deletion
    for idx, path in enumerate(resolved_paths, start=1):
        log.debug(f"[{session_id}]   [{idx}/{file_count}] Scheduled → {path.name}")

    # ------------------------------------------------------------------
    # SLEEP PHASE
    # asyncio.sleep yields control back to the event loop — the server
    # continues handling requests normally during this wait period.
    # ------------------------------------------------------------------
    try:
        await asyncio.sleep(delay_seconds)
    except asyncio.CancelledError:
        # The server is shutting down mid-wait.
        # Attempt immediate deletion of all files before exiting.
        log.warning(
            f"[{session_id}] Cleanup task was cancelled (server shutdown). "
            f"Attempting immediate deletion of {file_count} file(s)..."
        )
        _delete_files_sync(resolved_paths, session_id, reason="shutdown")
        return

    # ------------------------------------------------------------------
    # DELETION PHASE
    # ------------------------------------------------------------------
    log.info(
        f"[{session_id}] Cleanup timer elapsed — "
        f"beginning deletion of {file_count} file(s)..."
    )

    _delete_files_sync(resolved_paths, session_id, reason="scheduled")


def _delete_files_sync(
    paths: List[Path],
    session_id: str,
    reason: str = "scheduled",
) -> None:
    """
    Synchronous inner deletion loop.
    Attempts to unlink every file in `paths`.
    Logs the outcome of each attempt individually.
    Never raises any exception.

    Args:
        paths:      List of resolved Path objects to delete.
        session_id: Session ID for log attribution.
        reason:     'scheduled' | 'shutdown' — appears in log messages.
    """

    deleted_count  = 0
    missing_count  = 0
    error_count    = 0

    for path in paths:
        try:
            if not path.exists():
                # File was already deleted (e.g. admin purge, previous crash recovery)
                log.warning(
                    f"[{session_id}] [{reason}] File already gone (skipped): "
                    f"{path.name}"
                )
                missing_count += 1
                continue

            if not path.is_file():
                # Safety guard: never attempt to delete a directory
                log.error(
                    f"[{session_id}] [{reason}] Path is not a regular file — "
                    f"SKIPPED for safety: {path}"
                )
                error_count += 1
                continue

            # Perform the actual deletion
            path.unlink()
            deleted_count += 1
            log.info(
                f"[{session_id}] [{reason}] ✔ Deleted: {path.name} "
                f"({_format_file_size(path)})"
            )

        except PermissionError as exc:
            error_count += 1
            log.error(
                f"[{session_id}] [{reason}] ✖ Permission denied — "
                f"could not delete {path.name}: {exc}"
            )

        except OSError as exc:
            error_count += 1
            log.error(
                f"[{session_id}] [{reason}] ✖ OS error — "
                f"could not delete {path.name}: {exc}"
            )

        except Exception as exc:
            # Catch-all: log and continue. Never crash the background worker.
            error_count += 1
            log.error(
                f"[{session_id}] [{reason}] ✖ Unexpected error — "
                f"could not delete {path.name}: {exc}",
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # SUMMARY REPORT
    # ------------------------------------------------------------------
    total = len(paths)
    log.info(
        f"[{session_id}] Cleanup complete ({reason}): "
        f"{deleted_count}/{total} deleted | "
        f"{missing_count} already gone | "
        f"{error_count} errors"
    )

    if error_count > 0:
        log.warning(
            f"[{session_id}] {error_count} file(s) could not be deleted. "
            f"Check permissions on the exports/ directory."
        )


# =============================================================================
#  UTILITY: STARTUP DIRECTORY SWEEP
#  Called by main.py lifespan on boot to purge any artefacts left
#  over from a previous server crash (files whose cleanup task never ran).
# =============================================================================

def purge_exports_directory(exports_dir: Path, session_id: str = "BOOT") -> int:
    """
    Synchronously deletes every regular file inside `exports_dir`.
    Called once at server startup to clean up crash remnants.

    Args:
        exports_dir: The Path to the exports/ directory.
        session_id:  Log attribution label (default: 'BOOT').

    Returns:
        The number of files successfully deleted.
    """

    if not exports_dir.exists():
        log.warning(
            f"[{session_id}] exports/ directory does not exist — "
            f"nothing to purge."
        )
        return 0

    if not exports_dir.is_dir():
        log.error(
            f"[{session_id}] exports/ path is not a directory: {exports_dir}"
        )
        return 0

    stale_files = [f for f in exports_dir.iterdir() if f.is_file()]

    if not stale_files:
        log.info(f"[{session_id}] exports/ directory is clean — no stale files.")
        return 0

    log.info(
        f"[{session_id}] Found {len(stale_files)} stale file(s) in exports/ — purging..."
    )

    _delete_files_sync(stale_files, session_id=session_id, reason="boot-purge")

    deleted = sum(1 for f in stale_files if not f.exists())
    return deleted


# =============================================================================
#  UTILITY: MANUAL ADMIN PURGE ENDPOINT HELPER
#  Can be wired to an admin-only FastAPI route in future versions
#  to allow manual cache clearing without restarting the server.
# =============================================================================

async def purge_session_files(
    session_id: str,
    exports_dir: Path,
) -> dict:
    """
    Searches the exports directory for all files belonging to a specific
    session ID and deletes them immediately.

    File naming convention: ostadi_*_{session_id}.pdf / .docx

    Args:
        session_id:  The 16-character uppercase session identifier.
        exports_dir: Path to the exports directory.

    Returns:
        A result dict: {"deleted": int, "not_found": int, "errors": int}
    """

    if not exports_dir.exists():
        return {"deleted": 0, "not_found": 0, "errors": 0}

    # Find all files matching this session
    matching_files = list(exports_dir.glob(f"*_{session_id}.*"))

    if not matching_files:
        log.info(
            f"[{session_id}] Manual purge: no files found for this session."
        )
        return {"deleted": 0, "not_found": 1, "errors": 0}

    log.info(
        f"[{session_id}] Manual purge: found {len(matching_files)} file(s) — deleting now."
    )

    deleted  = 0
    errors   = 0

    for file_path in matching_files:
        try:
            file_path.unlink()
            deleted += 1
            log.info(f"[{session_id}] Manual purge ✔ deleted: {file_path.name}")
        except Exception as exc:
            errors += 1
            log.error(
                f"[{session_id}] Manual purge ✖ failed on {file_path.name}: {exc}"
            )

    return {"deleted": deleted, "not_found": 0, "errors": errors}


# =============================================================================
#  UTILITY: HUMAN-READABLE FILE SIZE FORMATTER
# =============================================================================

def _format_file_size(path: Path) -> str:
    """
    Returns a human-readable file size string for a given Path.
    Used in deletion log messages.
    Falls back to '? bytes' if the file is already gone.
    """
    try:
        size_bytes = path.stat().st_size
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 ** 2):.2f} MB"
    except OSError:
        return "? bytes"