"""Session management CLI commands."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING, Any

from modules.core.src.capabilities_session_manager import SessionManager
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
    login_parser = sessions_sub.add_parser(
        "login", help="Add a new session"
    )
    login_parser.add_argument(
        "--name",
        required=True,
        help="Session name (e.g., personal, work)",
    )

    # Health check command
    sessions_sub.add_parser(
        "health-check", help="Check health of all sessions"
    )

    # Remove command
    remove_parser = sessions_sub.add_parser(
        "remove", help="Remove a session"
    )
    remove_parser.add_argument(
        "session_id",
        help="Session ID to remove (e.g., session_1)",
    )

    # Status command
    sessions_sub.add_parser(
        "status", help="Show detailed session status"
    )


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
        last_used = (
            s.last_used.strftime("%Y-%m-%d %H:%M") if s.last_used else "Never"
        )
        print(f"{s.session_id:<12} {s.name:<15} {status_icon} {s.status.value:<8} {last_used}")

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"Total: {len(sessions)} sessions")
    print(f"Healthy: {sum(1 for s in sessions if s.is_healthy)}")
    print(f"Limited: {sum(1 for s in sessions if s.is_limited)}")
    print()

    return 0


def cmd_login(manager: SessionManager, args: argparse.Namespace) -> int:
    """Add a new session by launching a headed browser for manual login."""
    import subprocess
    import sys

    pool = manager.load_pool()
    next_num = len(pool.sessions) + 1
    session_id = f"session_{next_num}"
    profile_path = manager._base_dir / session_id
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

    # Launch Playwright to open chat.qwen.ai with isolated profile
    launch_script = f'''
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            "{profile_path}",
            headless=False,
            args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        page = browser.pages[0] if browser.pages else await browser.new_page()
        await page.goto("https://chat.qwen.ai")
        # Wait until user closes the browser
        try:
            await browser.wait_for_event("close")
        except Exception:
            pass
        await browser.close()

asyncio.run(main())
'''
    proc = subprocess.Popen(
        [sys.executable, "-c", launch_script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        print("\nLogin cancelled.")
        return 1

    if not profile_path.exists():
        print("❌ Profile was not created. Login may have failed.")
        return 1

    info = manager.add_session(args.name, profile_path)
    print(f"\n✅ Session '{args.name}' saved!")
    print(f"   ID: {info.session_id}")
    print(f"   Path: {profile_path}")
    print()

    again = input("Add another session? [y/N]: ").strip().lower()
    if again in ("y", "yes"):
        return cmd_login(manager, args)

    return 0


def cmd_health_check(manager: SessionManager) -> int:
    """Health check all sessions using real ping test."""
    import asyncio

    from modules.core.src.capabilities_session_health_checker import SessionHealthChecker
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
    """Remove a session."""
    if manager.remove_session(args.session_id):
        print(f"✅ Removed {args.session_id}")
        return 0
    print(f"❌ Session {args.session_id} not found")
    return 1


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
