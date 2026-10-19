"""Session management CLI commands.

Smart surface: delegates to the session aggregate
(:class:`ISessionAggregate`) — no capability imports. Failures funnel through
``_fail_json`` (the canonical ``--json`` envelope / ``[ERROR]`` channel) and
the pool tables render through ``render_pool_table``, fitted to the terminal
in display columns so wide status glyphs never overflow.

``login`` is the one interactive subcommand: it opens a headed browser for a
manual sign-in and — without ``--json`` — offers an "add another" re-prompt.
With ``--json`` it runs exactly one login, prints no banner, and emits the
fixed-key success envelope, so non-interactive callers never block on
``input()``.
"""

from __future__ import annotations

import argparse
import json
from typing import TYPE_CHECKING, Any

from modules.cli.src.surface_cli_json_hook import (
    EXIT_FAILURE,
    _fail_json,
    _fit,
    display_width,
    print_error,
    status_glyph,
)
from modules.shared.src.session.taxonomy_session_vo import SessionRequest, SessionResponse, SessionStatus

if TYPE_CHECKING:
    from modules.shared.src.session.contract_session_aggregate import ISessionAggregate

#: ``list`` / ``status`` share the leading ID / Name / Status columns; the
#: per-column floors keep short cells readable when the terminal is narrow.
_LIST_COLUMNS = ("ID", "Name", "Status", "Last Used")
_LIST_FLOORS = (6, 8, 8, 10)
_STATUS_COLUMNS = ("ID", "Name", "Status", "Requests", "Failed")
_STATUS_FLOORS = (6, 8, 8, 8, 6)
_PAD = 2


def register_sessions_subparser(subparsers: Any) -> None:
    """Register the ``session`` command group.

    Single source of truth for the group's parser shape: the Root CLI calls
    this function so the command names and the handler below cannot drift.
    ``--json`` is a group-level flag on every subcommand, so the root parses
    ``session <cmd> --json`` uniformly (matching the job/swarm groups).
    """
    sessions_parser = subparsers.add_parser(
        "session",
        help="Manage Qwen login sessions",
    )
    sessions_sub = sessions_parser.add_subparsers(dest="session_command", metavar="SUBCOMMAND")

    # List command
    list_parser = sessions_sub.add_parser("list", help="List all sessions")
    list_parser.add_argument("--json", action="store_true", help="Format output as JSON")

    # Login command
    login_parser = sessions_sub.add_parser("login", help="Add a new session")
    login_parser.add_argument("--json", action="store_true", help="Format output as JSON")
    login_parser.add_argument(
        "--name",
        required=True,
        help="Session name (e.g., personal, work)",
    )

    # Health check command
    health_parser = sessions_sub.add_parser("health", help="Check health of all sessions")
    health_parser.add_argument("--json", action="store_true", help="Format output as JSON")

    # Remove command
    remove_parser = sessions_sub.add_parser("remove", help="Remove a session")
    remove_parser.add_argument("--json", action="store_true", help="Format output as JSON")
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
    status_parser = sessions_sub.add_parser("status", help="Show detailed session status")
    status_parser.add_argument("--json", action="store_true", help="Format output as JSON")


def handle_sessions(args: argparse.Namespace, session: ISessionAggregate | None = None) -> int:
    """Handle sessions subcommand via the session aggregate.

    ``session`` is the injected :class:`ISessionAggregate`.  The CLI root
    always injects one; ``None`` is tolerated for library consumers that
    only call :func:`register_sessions_subparser`.
    """
    if session is None:
        return _fail_json(
            "Session aggregate not injected. Run via the CLI root.",
            "cli-500",
            bool(getattr(args, "json", False)),
        )

    json_output = bool(getattr(args, "json", False))
    if args.session_command == "list":
        return cmd_list(session, json_output)
    if args.session_command == "login":
        return cmd_login(session, args, json_output)
    if args.session_command == "health":
        return cmd_health_check(session, json_output)
    if args.session_command == "remove":
        return cmd_remove(session, args, json_output)
    if args.session_command == "status":
        return cmd_status(session, json_output)

    print("Use 'qwen-web-arwaky session --help' for usage")
    return 1


def _pool_row(s: Any, columns: tuple[str, ...]) -> tuple[str, ...]:
    """One pool row: the cell for each column of either table."""
    key = "health_ok" if s.is_healthy else ("health_limited" if s.is_limited else "health_unknown")
    values = {
        "ID": str(s.session_id),
        "Name": str(s.name),
        "Status": f"{status_glyph(key)} {s.status.value}",
        "Last Used": s.last_used.strftime("%Y-%m-%d %H:%M") if s.last_used else "Never",
        "Requests": str(s.total_requests),
        "Failed": str(s.failed_requests),
    }
    return tuple(values[column] for column in columns)


def render_pool_table(
    pool: list[Any],
    columns: tuple[str, ...],
    floors: tuple[int, ...],
    *,
    budget: int | None = None,
) -> str:
    """Render the sessions list/status table fitted to the terminal width.

    One print path for both commands: column widths come from the display
    width of every cell (wide glyphs included), overflow is squeezed from
    the widest columns down to their floors, and every cell is truncated by
    :func:`_fit`, so a rendered line never exceeds the terminal. Rows are
    built per column set, so a header and a row always carry the same cell
    count.
    """
    available = _terminal_columns() if budget is None else max(20, int(budget))
    gapless = available - _PAD * (len(columns) - 1)
    rows: list[tuple[str, ...]] = [tuple(columns)] + [_pool_row(s, columns) for s in pool]
    widths = _column_widths(rows, floors, gapless)

    def _line(row: tuple[str, ...]) -> str:
        cells = [_fit(cell, widths[index]) for index, cell in enumerate(row)]
        padded = [cell + " " * max(0, widths[index] - display_width(cell)) for index, cell in enumerate(cells)]
        return (" " * _PAD).join(padded)

    # ``━`` renders two columns per character, so the border is half of the
    # display width it must not exceed.
    border_display = min(available, sum(widths) + _PAD * (len(columns) - 1))
    border = "━" * (border_display // 2)
    return "\n".join([border, *[_line(row) for row in rows], border])


def _column_widths(rows: list[tuple[str, ...]], floors: tuple[int, ...], budget: int) -> list[int]:
    """Content-width columns squeezed to *budget* in display columns."""
    widths = list(floors)
    for row in rows:
        for index in range(min(len(floors), len(row))):
            widths[index] = max(widths[index], display_width(row[index]))
    surplus = sum(widths) - budget
    if surplus <= 0:
        return widths
    ordered = sorted(range(len(floors)), key=lambda i: widths[i], reverse=True)
    for index in ordered:
        if surplus <= 0:
            break
        shrink = min(surplus, widths[index] - floors[index])
        widths[index] -= shrink
        surplus -= shrink
    if surplus > 0:
        # Nothing more can be squeezed; the widest columns absorb the rest so
        # the line still fits instead of overflowing the terminal.
        shrinkable = [index for index in range(len(floors)) if widths[index] > 1]
        while surplus > 0 and shrinkable:
            widest = max(shrinkable, key=lambda i: widths[i])
            widths[widest] -= 1
            surplus -= 1
            if widths[widest] <= 1:
                shrinkable.remove(widest)
    return widths


def _terminal_columns() -> int:
    """Return the terminal width, defaulting to 80 when it cannot be read."""
    import shutil

    try:
        return max(20, shutil.get_terminal_size().columns)
    except Exception:
        return 80


def cmd_list(session: ISessionAggregate, json_output: bool = False) -> int:
    """List all sessions."""
    response = session.execute(SessionRequest(verb="list_sessions"))
    if response.error:
        return _fail_json(str(response.error), "cli-500", json_output)
    pool: list[Any] = list(response.sessions) if response.sessions else []

    if json_output:
        payload = {
            "success": True,
            "sessions": [
                {
                    "session_id": s.session_id,
                    "name": s.name,
                    "status": s.status.value,
                    "is_healthy": s.is_healthy,
                    "is_limited": s.is_limited,
                    "last_used": s.last_used.isoformat() if s.last_used else None,
                }
                for s in pool
            ],
        }
        print(json.dumps(payload, indent=2, default=str))
        return 0

    if not pool:
        print("No sessions found. Use 'session login --name <name>' to add one.")
        return 0

    print("\n📊 Session Pool")
    print(render_pool_table(pool, _LIST_COLUMNS, _LIST_FLOORS))
    print(f"Total: {len(pool)} sessions")
    print(f"Healthy: {sum(1 for s in pool if s.is_healthy)}")
    print(f"Limited: {sum(1 for s in pool if s.is_limited)}")
    print()

    return 0


def _login_once(session: ISessionAggregate, name: str, json_output: bool = False) -> int:
    """Run one headed login and report it; the re-prompt loop drives iteration.

    With *json_output* the banner and every human line are skipped and the
    fixed-key envelope carries the result, so a non-interactive caller gets
    one machine-readable answer and never blocks on ``input()``.
    """
    if not json_output:
        print(f"\n🔐 Login to Qwen ({name})")
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
            name=name,
            wait_for_confirmation=lambda: False,
        )
    )

    if not response.valid:
        message = f"Login failed: {response.error or response.message or 'login failed'}"
        if json_output:
            return _fail_json(message, "cli-500", True)
        print_error(message)
        return EXIT_FAILURE

    if json_output:
        print(json.dumps({"success": True, "message": f"Session '{name}' saved"}, indent=2))
        return 0

    print(f"\n{status_glyph('ok')} Session '{name}' saved!")
    if response.profile_path:
        print(f"   Path: {response.profile_path}")
    print()
    return 0


def cmd_login(session: ISessionAggregate, args: argparse.Namespace, json_output: bool = False) -> int:
    """Add a new session by launching a headed browser for manual login.

    Delegates to the ``login`` verb on the session aggregate, which runs
    the headed browser and registers the profile in the pool. The
    "add another" prompt is iterative so long runs cannot recurse through
    ``args`` mutation. Under ``--json`` exactly one login runs and no
    re-prompt is offered, so non-interactive callers never block.
    """
    name = args.name
    if json_output:
        return _login_once(session, name, json_output=True)
    while True:
        if _login_once(session, name) != 0:
            return EXIT_FAILURE
        try:
            again = input("Add another session? [y/N]: ").strip().lower()
            if again not in ("y", "yes"):
                return 0
            next_name = input("Session name: ").strip()
        except EOFError:
            # A closed stdin (piped input, Ctrl+D) ends the session instead of
            # escaping as a traceback.
            return 0
        name = next_name or "session_default"


def cmd_health_check(session: ISessionAggregate, json_output: bool = False) -> int:
    """Health check all sessions using real ping test.

    Delegates to the session aggregate; real browser probing is owned by
    the session capability, not by this surface. JSON mode prints only the
    envelope, so the human-readable banner is skipped.
    """
    if not json_output:
        print("\n🏥 Running health checks...")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    try:
        response = session.execute(SessionRequest(verb="check_health"))
    except Exception as exc:
        return _fail_json(f"Health check failed: {exc}", "cli-500", json_output)

    if not json_output:
        print(f"Result: {response.message}")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()
    if response.error:
        return _fail_json(str(response.error), "cli-500", json_output)

    if json_output:
        payload: dict[str, Any] = {
            "success": True,
            "message": response.message,
            "states": [
                {
                    "session_id": s.session_id,
                    "status": s.status.value,
                    "is_healthy": s.is_healthy,
                }
                for s in list(response.sessions or [])
            ],
        }
        print(json.dumps(payload, indent=2, default=str))
    return 0


def cmd_remove(session: ISessionAggregate, args: argparse.Namespace, json_output: bool = False) -> int:
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
            return _fail_json(str(response.error), "cli-500", json_output)
        if json_output:
            print(json.dumps({"success": True, "message": f"Removed session '{token}'"}, indent=2))
        else:
            print(f"{status_glyph('ok')} Removed session '{token}' from the pool")
            print("   Profile kept")
        return 0

    # Resolve the profile path for the token, then delete profile + pool entry.
    listing = session.execute(SessionRequest(verb="list_sessions"))
    matches = [s for s in list(listing.sessions or []) if s.session_id == token or s.name == token]
    if not matches:
        return _fail_json(f"Session '{token}' not found in the pool", "cli-400", json_output)

    response = session.execute(
        SessionRequest(
            verb="delete",
            session_path=matches[0].path,
            force=getattr(args, "force", False),
        )
    )
    if response.error:
        return _fail_json(str(response.error), "cli-500", json_output)

    if json_output:
        print(json.dumps({"success": True, "message": f"Removed session '{token}'"}, indent=2))
    else:
        print(f"{status_glyph('ok')} Removed session '{token}' from the pool")
        if matches[0].path:
            print(f"   Profile deleted: {matches[0].path}")
    return 0


def cmd_status(session: ISessionAggregate, json_output: bool = False) -> int:
    """Show detailed session status."""
    response = session.execute(SessionRequest(verb="list_sessions"))
    if response.error:
        return _fail_json(str(response.error), "cli-500", json_output)
    pool: list[Any] = list(response.sessions) if response.sessions else []

    if json_output:
        payload = {
            "success": True,
            "sessions": [
                {
                    "session_id": s.session_id,
                    "name": s.name,
                    "status": s.status.value,
                    "total_requests": s.total_requests,
                    "failed_requests": s.failed_requests,
                }
                for s in pool
            ],
            "healthy": sum(1 for s in pool if s.is_healthy),
            "limited": sum(1 for s in pool if s.is_limited),
            "unknown": sum(1 for s in pool if s.status == SessionStatus.UNKNOWN),
        }
        print(json.dumps(payload, indent=2, default=str))
        return 0

    if not pool:
        print("No sessions configured.")
        return 0

    print("\n📊 Session Pool Status")
    print(render_pool_table(pool, _STATUS_COLUMNS, _STATUS_FLOORS))
    print(f"Healthy: {sum(1 for s in pool if s.is_healthy)}")
    print(f"Limited: {sum(1 for s in pool if s.is_limited)}")
    print(f"Unknown: {sum(1 for s in pool if s.status == SessionStatus.UNKNOWN)}")
    print()

    return 0


__all__ = [
    "handle_sessions",
    "register_sessions_subparser",
    "render_pool_table",
]
