"""Core utility: Chromium cookie-store inspection for session renewal decisions.

The saved session profile stores its credentials in a SQLite cookie jar at
``<profile>/Default/Cookies`` (Chromium layout). Two cookies gate chat.qwen.ai
access: ``auth-session`` (short-lived, host ``auth.qwen.ai``) and
``refresh_token`` (long-lived, host ``.qwen.ai``). When ``auth-session``
expires but ``refresh_token`` is still valid, the site's own JS can self-heal
the session on a page load; this utility tells the renewal capability whether
that is possible by reading expiry times directly from the cookie store.

AES201: utility layer imports taxonomy only (no contract, no capabilities).
All functions are stateless. Cookie values are never read or returned — only
names, expiry and presence — so this module cannot leak credentials.
"""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

#: Chromium cookie DB locations, newest layout first.
_COOKIE_DB_CANDIDATES: tuple[str, ...] = ("Network/Cookies", "Default/Cookies")

#: Qwen credentials in the cookie store.
AUTH_SESSION_COOKIE = "auth-session"
REFRESH_TOKEN_COOKIE = "refresh_token"

#: Chromium's cookie epoch offset (microseconds since 1601-01-01 -> UTC).
_CHROMIUM_EPOCH_OFFSET_SEC: float = 11644473600.0


def find_cookie_db(profile_dir: Path) -> Path | None:
    """Return the cookie DB path under *profile_dir*, or None when absent."""
    for candidate in _COOKIE_DB_CANDIDATES:
        db = Path(profile_dir) / candidate
        if db.is_file():
            return db
    return None


def _cookie_expires_at_utc(db: Path, cookie_name: str) -> float | None:
    """Return the UTC expiry (seconds since epoch) of *cookie_name*, or None.

    Returns None when the cookie is absent or is a session cookie
    (``expires_utc == 0`` / non-persistent). Read-only connection: the DB
    may be held by a running Chromium, so the open tolerates lock errors
    and falls back to a copy-into-memory read.
    """
    conn = None
    try:
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            cursor = conn.cursor()
        except sqlite3.OperationalError:
            # Profile locked by a running browser: copy the file (cheap,
            # ~1 MB) so the read never blocks on the writer's lock.
            with tempfile.TemporaryFile(suffix=".db") as tmp:
                with open(db, "rb") as src:
                    tmp.write(src.read())
                tmp.flush()
                conn = sqlite3.connect(tmp.name)
                cursor = conn.cursor()
        cursor.execute(
            "SELECT expires_utc, is_persistent FROM cookies WHERE name = ? AND host_key LIKE '%qwen.ai%' LIMIT 1",
            (cookie_name,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        expires_utc, is_persistent = row
        if not is_persistent or expires_utc == 0:
            return None
        return float(expires_utc) / 1_000_000 - _CHROMIUM_EPOCH_OFFSET_SEC
    except (sqlite3.Error, OSError):
        return None
    finally:
        if conn is not None:
            conn.close()


def is_refresh_token_valid(profile_dir: Path, *, now: datetime | None = None) -> bool:
    """True when a non-expired ``refresh_token`` cookie exists in the profile.

    The refresh token is the long-lived credential that Qwen's front end
    exchanges for a fresh ``auth-session``. When it is present and unexpired,
    a browser warm-up can renew the short-lived session without interactive
    login. Returns False for missing profiles, unreadable stores, absent
    cookies, and expired cookies alike — renewal must not run on doubt.
    """
    db = find_cookie_db(profile_dir)
    if db is None:
        return False
    expires_at = _cookie_expires_at_utc(db, REFRESH_TOKEN_COOKIE)
    if expires_at is None:
        return False
    if now is None:
        now = datetime.now(timezone.utc)
    return expires_at > now.timestamp()


def is_auth_session_expired(profile_dir: Path, *, now: datetime | None = None) -> bool:
    """True when the ``auth-session`` cookie is absent or already expired.

    A healthy session skips the renewal path entirely, so this is the cheap
    pre-check that decides whether the expensive browser warm-up is needed at
    all. An unreadable cookie store reports the session as expired: the
    caller then pays for the authoritative browser probe.
    """
    db = find_cookie_db(profile_dir)
    if db is None:
        return True
    expires_at = _cookie_expires_at_utc(db, AUTH_SESSION_COOKIE)
    if expires_at is None:
        return True
    if now is None:
        now = datetime.now(timezone.utc)
    return expires_at <= now.timestamp()


def renewal_is_possible(profile_dir: Path, *, now: datetime | None = None) -> bool:
    """True when the browser warm-up path can restore the session.

    Combines both cookie signals: renewal makes sense only when the short
    credential is dead and the long one still lives. A live auth session
    needs no work; a dead refresh token means only manual re-login works.
    """
    return is_auth_session_expired(profile_dir, now=now) and is_refresh_token_valid(profile_dir, now=now)


__all__ = [
    "AUTH_SESSION_COOKIE",
    "REFRESH_TOKEN_COOKIE",
    "find_cookie_db",
    "is_auth_session_expired",
    "is_refresh_token_valid",
    "renewal_is_possible",
]
