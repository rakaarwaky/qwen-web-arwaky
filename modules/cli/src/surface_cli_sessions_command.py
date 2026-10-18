"""Session management CLI commands.

Smart surface: delegates to the session aggregate
(:class:`ISessionAggregate`) — no capability imports.
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING, Any

from modules.shared.src.session.taxonomy_session_vo import SessionRequest, SessionResponse, SessionStatus

if TYPE_CHECKING:
    from modules.shared.src.session.contract_session_aggregate import ISessionAggregate


def register_sessions_subparser(subparsers: Any) -> None:
    """Register the ``session`` command group.

    Single source of truth for the group's parser shape: the Root CLI calls
    this function so the command names and the handler below cannot drift.
    """
    sessions_parser = subparsers.add_parser(
        "session",
        help="Manage Qwen login sessions",
    )
    sessions_sub = sessions_parser.add_subparsers(dest="session_command", metavar="SUBCOMMAND")

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
    sessions_sub.add_parser("health", help="Check health of all sessions")

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


def handle_sessions(args: argparse.Namespace, session: ISessionAggregate | None = None) -> int:
    """Handle sessions subcommand via the session aggregate.

    ``session`` is the injected :class:`ISessionAggregate`.  The CLI root
    always injects one; ``None`` is tolerated for library consumers that
    only call :func:`register_sessions_subparser`.
    """
    if session is None:
        print("[ERROR] Session aggregate not injected. Run via the CLI root.", file=sys.stderr)
        return 1

    if args.session_command == "list":
        return cmd_list(session)
    if args.session_command == "login":
        return cmd_login(session, args)
    if args.session_command == "health":
        return cmd_health_check(session)
    if args.session_command == "remove":
        return cmd_remove(session, args)
    if args.session_command == "status":
        return cmd_status(session)

    print("Use 'qwen-web-arwaky session --help' for usage")
    return 1


def cmd_list(session: ISessionAggregate) -> int:
    """List all sessions."""
    response = session.execute(SessionRequest(verb="list_sessions"))
    pool: list[Any] = list(response.sessions) if response.sessions else []
    if not pool:
        print("No sessions found. Use 'session login --name <name>' to add one.")
        return 0

    print("\n📊 Session Pool")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"{'ID':<12} {'Name':<15} {'Status':<10} {'Last Used':<20}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    for s in pool:
        status_icon = _status_icon(s.status)
        last_used = s.last_used.strftime("%Y-%m-%d %H:%M") if s.last_used else "Never"
        print(f"{s.session_id:<12} {s.name:<15} {status_icon} {s.status.value:<8} {last_used}")

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"Total: {len(pool)} sessions")
    print(f"Healthy: {sum(1 for s in pool if s.is_healthy)}")
    print(f"Limited: {sum(1 for s in pool if s.is_limited)}")
    print()

    return 0


def cmd_login(session: ISessionAggregate, args: argparse.Namespace) -> int:
    """Add a new session by launching a headed browser for manual login.

    Delegates to the ``login`` verb on the session aggregate, which runs
    the headed browser and registers the profile in the pool.
    """
    profile_name = args.name

    print(f"\n🔐 Login to Qwen ({profile_name})")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("Creating isolated browser profile...")
    print()
    print("⏳ Launching browser for manual login...")
    print("   Login at chat.qwen.ai, then close the browser window when done.")
    print()
    print("💡 Tip: Close the browser window to continue.")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    response: SessionResponse = session.execute(
        SessionRequest(
            verb="login",
            name=profile_name,
            wait_for_confirmation=lambda: False,
        )
    )

    if not response.valid:
        print(f"\n❌ {response.error or response.message or 'Login failed'}")
        return 1

    print(f"\n✅ Session '{profile_name}' saved!")
    if response.profile_path:
        print(f"   Path: {response.profile_path}")
    print()

    again = input("Add another session? [y/N]: ").strip().lower()
    if again in ("y", "yes"):
        name = input("Session name: ").strip()
        if not name:
            name = "session_default"
        args.name = name
        return cmd_login(session, args)

    return 0


def cmd_health_check(session: ISessionAggregate) -> int:
    """Health check all sessions using real ping test.

    Delegates to the session aggregate; real browser probing is owned by
    the session capability, not by this surface.
    """
    print("\n🏥 Running health checks...")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    try:
        response = session.execute(SessionRequest(verb="check_health"))
    except Exception as exc:
        print(f"❌ Health check failed: {exc}")
        return 1

    print(f"Result: {response.message}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    if response.error:
        print(f"❌ {response.error}")
        return 1
    return 0


def cmd_remove(session: ISessionAggregate, args: argparse.Namespace) -> int:
    """Remove a session entry via the session aggregate.

    Drops the pool entry; when ``--keep-profile`` is set the Chromium
    profile directory is left on disk, otherwise the pool removal also
    deletes the profile directory.
    """
    token = args.session_id

    if getattr(args, "keep_profile", False):
        # Drop the pool entry only; leave the profile on disk.
        response: SessionResponse = session.execute(SessionRequest(verb="remove_session", name=token))
        if response.error:
            print(f"❌ {response.error}")
            return 1
        print(f"✅ Removed session '{token}' from the pool")
        print("   Profile kept")
        return 0

    # Resolve the profile path for the token, then delete profile + pool entry.
    listing = session.execute(SessionRequest(verb="list_sessions"))
    matches = [s for s in list(listing.sessions or []) if s.session_id == token or s.name == token]
    if not matches:
        print(f"❌ Session '{token}' not found in the pool")
        return 1

    response = session.execute(
        SessionRequest(
            verb="delete",
            session_path=matches[0].path,
            force=getattr(args, "force", False),
        )
    )
    if response.error:
        print(f"❌ {response.error}")
        return 1

    print(f"✅ Removed session '{token}' from the pool")
    if matches[0].path:
        print(f"   Profile deleted: {matches[0].path}")
    return 0


def cmd_status(session: ISessionAggregate) -> int:
    """Show detailed session status."""
    response = session.execute(SessionRequest(verb="list_sessions"))
    pool: list[Any] = list(response.sessions) if response.sessions else []
    if not pool:
        print("No sessions configured.")
        return 0

    print("\n📊 Session Pool Status")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"{'ID':<12} {'Name':<15} {'Status':<10} {'Requests':<12} {'Failed':<10}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    for s in pool:
        status_icon = _status_icon(s.status)
        print(
            f"{s.session_id:<12} "
            f"{s.name:<15} "
            f"{status_icon} {s.status.value:<8} "
            f"{s.total_requests:<12} "
            f"{s.failed_requests:<10}"
        )

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"Healthy: {sum(1 for s in pool if s.is_healthy)}")
    print(f"Limited: {sum(1 for s in pool if s.is_limited)}")
    print(f"Unknown: {sum(1 for s in pool if s.status == SessionStatus.UNKNOWN)}")
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
