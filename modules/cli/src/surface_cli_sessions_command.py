"""Session management CLI commands."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING, Any

from modules.session.src.capabilities_session_manager import SessionManager
from modules.shared.src.taxonomy_session_vo import SessionStatus

if TYPE_CHECKING:
    pass


def register_sessions_subparser(subparsers: Any) -> None:
    """Register sessions subcommand."""
    sessions_parser = subparsers.add_parser(
        "sessions",
        help="Manage Qwen login sessions",
    )
    sessions_sub = sessions_parser.add_subparsers(dest="session_command")

    # List command
    sessions_sub.add_parser("list", help="List all sessions")

    # Login command
    login_parser = sessions_sub.add_parser("login", help="Add a new session")
    login_parser.add_argument(
        "--name",
        required=True,
        help="Session name (e.g., personal, work)",
    )

    # Health check command
    sessions_sub.add_parser("health-check", help="Check health of all sessions")

    # Remove command
    remove_parser = sessions_sub.add_parser("remove", help="Remove a session")
    remove_parser.add_argument(
        "session_id",
        help="Session ID (e.g., session_1) or name (e.g., personal)",
    )
    remove_parser.add_argument(
        "--force",
        action="store_true",
        help="Delete the profile even without a retained backup generation",
    )
    remove_parser.add_argument(
        "--keep-profile",
        action="store_true",
        help="Drop the pool entry only; leave the Chromium profile directory on disk",
    )

    # Status command
    sessions_sub.add_parser("status", help="Show detailed session status")


def handle_sessions(args: argparse.Namespace) -> int:
    """Handle sessions subcommand."""
    manager = SessionManager()

    if args.session_command == "list":
        return cmd_list(manager)
    if args.session_command == "login":
        return cmd_login(manager, args)
    if args.session_command == "health-check":
        return cmd_health_check(manager)
    if args.session_command == "remove":
        return cmd_remove(manager, args)
    if args.session_command == "status":
        return cmd_status(manager)

    print("Use 'qwen-web-arwaky sessions --help' for usage")
    return 1


def cmd_list(manager: SessionManager) -> int:
    """List all sessions."""
    sessions = manager.list_sessions()

    if not sessions:
        print("No sessions found. Use 'sessions login --name <name>' to add one.")
        return 0

    print("\n📊 Session Pool")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"{'ID':<12} {'Name':<15} {'Status':<10} {'Last Used':<20}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    for s in sessions:
        status_icon = _status_icon(s.status)
        last_used = s.last_used.strftime("%Y-%m-%d %H:%M") if s.last_used else "Never"
        print(f"{s.session_id:<12} {s.name:<15} {status_icon} {s.status.value:<8} {last_used}")

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"Total: {len(sessions)} sessions")
    print(f"Healthy: {sum(1 for s in sessions if s.is_healthy)}")
    print(f"Limited: {sum(1 for s in sessions if s.is_limited)}")
    print()

    return 0


def cmd_login(manager: SessionManager, args: argparse.Namespace) -> int:
    """Add a new session by launching a headed browser for manual login.

    Uses ``SessionOrchestrator`` in-process so the validation loop (the
    headless auth check that runs after the visible browser closes) is
    executed, and the new profile is registered in the session pool via
    ``SessionManager.add_session``.
    """
    from modules.root_core_container import SharedContainer
    from modules.session.src.agent_session_orchestrator import SessionOrchestrator
    from modules.shared.src.taxonomy_core_constant import SESSIONS_DIR
    from modules.shared.src.taxonomy_setup_vo import SetupRequest

    profile_path = SESSIONS_DIR / args.name
    profile_path.mkdir(parents=True, exist_ok=True)

    print(f"\n🔐 Login to Qwen ({args.name})")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("Creating isolated browser profile...")
    print(f"Path: {profile_path}")
    print()
    print("⏳ Launching browser for manual login...")
    print("   Login at chat.qwen.ai, then close the browser window when done.")
    print()
    print("💡 Tip: Close the browser window to continue.")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    container = SharedContainer()
    orchestrator = SessionOrchestrator(
        browser=container.browser,
        observability=container.observability,
        sessions=manager,
    )

    response = orchestrator.execute(
        SetupRequest(profile_path=profile_path, name=args.name, browser_headless=False)
    )

    if not response.success:
        print(f"\n❌ {response.error or 'Login failed'}")
        return 1

    print(f"\n✅ Session '{args.name}' saved!")
    print(f"   Path: {profile_path}")
    print()

    again = input("Add another session? [y/N]: ").strip().lower()
    if again in ("y", "yes"):
        name = input("Session name: ").strip()
        if not name:
            name = f"session_{len(manager.load_pool().sessions) + 1}"
        args.name = name
        return cmd_login(manager, args)

    return 0


def cmd_health_check(manager: SessionManager) -> int:
    """Health check all sessions using real ping test."""
    import asyncio

    from modules.session.src.capabilities_session_health_checker import SessionHealthChecker
    from modules.shared.src.taxonomy_session_vo import SessionInfo

    sessions = manager.list_sessions()

    if not sessions:
        print("No sessions to check.")
        return 0

    print("\n🏥 Running health checks...")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    checker = SessionHealthChecker(timeout_seconds=10)

    async def _run_checks() -> list[tuple[SessionInfo, bool]]:
        results: list[tuple[SessionInfo, bool]] = []
        for s in sessions:
            healthy = await checker.check_session(s)
            results.append((s, healthy))
        return results

    try:
        results = asyncio.run(_run_checks())
    except Exception as exc:
        print(f"❌ Health check failed: {exc}")
        return 1

    for s, healthy in results:
        status = "✅ Healthy" if healthy else "❌ Limited"
        print(f"  {s.session_id:<12} {status}")
        if healthy:
            manager.mark_healthy(s.session_id)
        else:
            manager.mark_limited(s.session_id)

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    healthy_count: int = sum(1 for _, h in results if h)
    print(f"Result: {healthy_count}/{len(results)} sessions healthy")
    print()

    return 0


def cmd_remove(manager: SessionManager, args: argparse.Namespace) -> int:
    """Remove a session entry and, unless --keep-profile, its Chromium profile."""
    token = args.session_id
    info = manager.get_session(token) or manager.get_session_by_name(token)
    if info is None:
        print(f"❌ Session '{token}' not found")
        return 1

    if not manager.remove_session(info.session_id):
        print(f"❌ Could not remove '{info.session_id}' from the pool")
        return 1
    print(f"✅ Removed {info.name} ({info.session_id}) from the pool")

    if getattr(args, "keep_profile", False):
        print(f"   Profile kept at {info.path}")
        return 0

    try:
        manager.delete_session_profile(info.path, force=getattr(args, "force", False))
    except Exception as exc:
        print(f"❌ Pool entry removed, but the profile was kept: {exc}")
        print(f"   Path: {info.path} (retry with --force to delete anyway)")
        return 1
    print(f"   Profile deleted: {info.path}")
    return 0


def cmd_status(manager: SessionManager) -> int:
    """Show detailed session status."""
    sessions = manager.list_sessions()

    if not sessions:
        print("No sessions configured.")
        return 0

    print("\n📊 Session Pool Status")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"{'ID':<12} {'Name':<15} {'Status':<10} {'Requests':<12} {'Failed':<10}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    for s in sessions:
        status_icon = _status_icon(s.status)
        print(
            f"{s.session_id:<12} "
            f"{s.name:<15} "
            f"{status_icon} {s.status.value:<8} "
            f"{s.total_requests:<12} "
            f"{s.failed_requests:<10}"
        )

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"Healthy: {sum(1 for s in sessions if s.is_healthy)}")
    print(f"Limited: {sum(1 for s in sessions if s.is_limited)}")
    print(f"Unknown: {sum(1 for s in sessions if s.status == SessionStatus.UNKNOWN)}")
    print()

    return 0


def _status_icon(status: SessionStatus) -> str:
    """Get status icon."""
    icons = {
        SessionStatus.ACTIVE: "🟢",
        SessionStatus.LIMITED: "🟡",
        SessionStatus.UNKNOWN: "🔵",
    }
    return icons.get(status, "⚪")


__all__ = [
    "register_sessions_subparser",
    "handle_sessions",
]
