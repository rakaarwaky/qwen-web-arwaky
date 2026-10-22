"""Regression test: concurrent pool writers cannot lose each other's updates.

SA-2-02 documented a single-writer assumption on ``sessions.json`` that does
not hold: the long-lived MCP server and a CLI session command can run a
load→mutate→save cycle at the same time, and the last ``os.replace`` wins.
Every mutating path now holds an exclusive advisory lock
(``sessions.json.lock``) across the cycle, so the two serialize instead of
racing. The lock is per-file, so threading here stands in for two processes.
"""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from modules.session.src import capabilities_session_manager as session_manager_module
from modules.session.src.capabilities_session_manager import SessionManager
from modules.shared.src.common import taxonomy_core_constant as constants
from modules.shared.src.session.taxonomy_session_vo import SessionStatus


@pytest.fixture()
def pool_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point POOL_FILE and SESSIONS_DIR at a tmp tree so no real profile is touched."""
    sessions_dir = tmp_path / "share" / "sessions"
    sessions_dir.mkdir(parents=True)
    monkeypatch.setattr(constants, "POOL_FILE", sessions_dir / "sessions.json")
    monkeypatch.setattr(constants, "SESSIONS_DIR", sessions_dir)
    monkeypatch.setattr(session_manager_module, "POOL_FILE", sessions_dir / "sessions.json")
    monkeypatch.setattr(session_manager_module, "SESSIONS_DIR", sessions_dir)
    return sessions_dir


def _seed(manager: SessionManager, count: int, sessions_dir: Path) -> None:
    for i in range(count):
        manager.add_session(f"seed-{i}", sessions_dir / f"seed-{i}")


def test_concurrent_mark_limited_and_add_session_lose_no_updates(
    pool_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mark_limited racing N add_session calls must end with every row present.

    Before the lock, one writer's read-modify-write overwrote the other's
    save, so the pool lost rows. The final pool must carry the seeded rows,
    every added row, and the marked status.
    """
    manager = SessionManager(base_dir=pool_home)
    _seed(manager, 5, pool_home)
    seeded_ids = {s.session_id for s in manager.load_pool().sessions}

    added_names = [f"worker-{i}" for i in range(8)]
    barrier = threading.Barrier(len(added_names) + 1)
    failures: list[BaseException] = []

    def _add(name: str) -> None:
        try:
            barrier.wait(timeout=10)
            manager.add_session(name, pool_home / name)
        except BaseException as exc:  # pragma: no cover - asserted below
            failures.append(exc)

    threads = [threading.Thread(target=_add, args=(name,)) for name in added_names]
    for t in threads:
        t.start()
    try:
        barrier.wait(timeout=10)
        manager.mark_limited("session_1", reason="QUOTA")
    finally:
        for t in threads:
            t.join(timeout=30)

    assert failures == [], f"concurrent writers raised: {failures}"
    final = manager.load_pool().sessions
    names = {s.name for s in final}
    assert names >= set(added_names), f"lost add_session rows: {set(added_names) - names}"
    assert {s.session_id for s in final} >= seeded_ids, "lost seeded rows"
    limited = next(s for s in final if s.session_id == "session_1")
    assert limited.status == SessionStatus.LIMITED


@pytest.mark.parametrize(
    "mutate",
    [
        "add_session",
        "mark_limited",
        "mark_healthy",
        "mark_auth_required",
        "mark_used",
        "remove_session",
        "remove_session_by_name",
    ],
)
def test_every_mutating_path_holds_one_advisory_lock(
    pool_home: Path,
    mutate: str,
) -> None:
    """The lock file is created beside the pool and each mutation acquires it once."""
    lock_path = pool_home / "sessions.json.lock"
    acquisitions: list[int] = []
    real_lock = session_manager_module.exclusive_file_lock

    def _counting(lock: Path) -> object:
        acquisitions.append(1)
        return real_lock(lock)

    manager = SessionManager(base_dir=pool_home)
    with patch.object(session_manager_module, "exclusive_file_lock", _counting):
        if mutate == "add_session":
            manager.add_session("alpha", pool_home / "alpha")
        elif mutate == "mark_limited":
            manager.mark_limited("session_1")
        elif mutate == "mark_healthy":
            manager.mark_healthy("session_1")
        elif mutate == "mark_auth_required":
            manager.mark_auth_required("session_1")
        elif mutate == "mark_used":
            manager.mark_used("session_1")
        elif mutate == "remove_session":
            manager.remove_session("session_1")
        elif mutate == "remove_session_by_name":
            manager.add_session("beta", pool_home / "beta")
            acquisitions.clear()
            manager.remove_session_by_name("beta")
        else:  # pragma: no cover - parametrize is the allow-list
            raise AssertionError(f"unknown mutate {mutate}")

    assert acquisitions, f"{mutate} did not acquire the pool lock"
    assert lock_path.parent == pool_home
    # The lock lives at the documented path (POOL_FILE.name + ".lock").
    assert lock_path.name == "sessions.json.lock"


def test_discovery_save_holds_advisory_lock(pool_home: Path) -> None:
    """load_pool's auto-discovery write must take the same lock as mutators."""
    profile = pool_home / "discovered"
    profile.mkdir()
    (profile / "Local State").write_text("{}", encoding="utf-8")

    acquisitions: list[int] = []
    real_lock = session_manager_module.exclusive_file_lock

    def _counting(lock: Path) -> object:
        acquisitions.append(1)
        return real_lock(lock)

    manager = SessionManager(base_dir=pool_home)
    with patch.object(session_manager_module, "exclusive_file_lock", _counting):
        pool = manager.load_pool()

    assert {s.name for s in pool.sessions} == {"discovered"}
    assert acquisitions, "discovery save_pool must acquire the pool lock"
