"""CLI surface: doctor command — system diagnostic checks (AES406).

Audits environment health: Python version, Playwright browser, workspace initialization,
session token directory, and output directory write permissions.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from modules.shared.src.taxonomy_core_constant import DEFAULT_OUTPUT, DEFAULT_SESSION


def run_doctor(json_output: bool = False) -> int:
    """Perform system health diagnostics and print formatted report or JSON summary."""
    checks: list[dict[str, Any]] = []

    # Check 1: Python version
    py_ok = sys.version_info >= (3, 10)
    checks.append(
        {
            "name": "Python Version",
            "passed": py_ok,
            "detail": f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} (>= 3.10)",
        }
    )

    # Check 2: Playwright Chromium installation
    playwright_ok = False
    pw_detail = "Playwright chromium binary check"
    try:
        import shutil

        chrome_in_path = shutil.which("chromium") or shutil.which("chrome")
        from modules.shared.src.utility_core_paths import get_playwright_browsers_path

        ms_pw_dir = get_playwright_browsers_path()
        has_ms_pw = ms_pw_dir.exists() and any(ms_pw_dir.glob("chromium-*"))

        if has_ms_pw or chrome_in_path:
            playwright_ok = True
            pw_detail = "Chromium binary found in Playwright cache or system PATH"
        elif os.environ.get("QWEN_DOCTOR_DEEP") == "1":
            # P4: the sync_playwright cold-start probe (5-15s) is opt-in via
            # QWEN_DOCTOR_DEEP=1 so the common `doctor` path stays fast.
            try:
                from playwright.sync_api import sync_playwright

                pw = sync_playwright().start()
                exe = pw.chromium.executable_path
                playwright_ok = Path(exe).exists() if exe else False
                pw_detail = (
                    f"Chromium binary at: {exe}"
                    if playwright_ok
                    else "Chromium binary missing (run: python3 -m playwright install chromium)"
                )
                pw.stop()
            except Exception as ex:
                pw_detail = f"Chromium binary missing (run: python3 -m playwright install chromium): {ex}"
        else:
            playwright_ok = False
            pw_detail = "Chromium binary not found in cache or PATH (set QWEN_DOCTOR_DEEP=1 for a full probe)"
    except Exception as e:
        pw_detail = f"Playwright check failed: {e}"

    checks.append(
        {
            "name": "Playwright Chromium Browser",
            "passed": playwright_ok,
            "detail": pw_detail,
        }
    )

    # Check 3: Workspace initialization
    dot_qwen = Path.cwd() / ".qwen-web"
    ws_ok = dot_qwen.exists() and (dot_qwen / "input").exists() and (dot_qwen / "output").exists()
    checks.append(
        {
            "name": "Workspace Initialization",
            "passed": ws_ok,
            "detail": f"Workspace found at {dot_qwen}"
            if ws_ok
            else "Workspace not initialized (run: qwen-web-arwaky init)",
        }
    )

    # Check 4: Session token directory
    session_dir = DEFAULT_SESSION
    # C6: single existence check (previously duplicated with confusing precedence).
    sess_ok = session_dir.exists() and any(session_dir.iterdir())
    checks.append(
        {
            "name": "Session Authentication Token",
            "passed": sess_ok,
            "detail": f"Saved session found at {session_dir}"
            if sess_ok
            else f"No active session found in {session_dir} (run: qwen-web-arwaky login)",
        }
    )

    # Check 5: Output directory write permissions
    out_dir = DEFAULT_OUTPUT
    out_ok = False
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        test_file = out_dir / ".doctor_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        out_ok = True
        out_detail = f"Output directory writable ({out_dir})"
    except Exception as e:
        out_detail = f"Output directory not writable ({out_dir}): {e}"

    checks.append(
        {
            "name": "Output Storage Permission",
            "passed": out_ok,
            "detail": out_detail,
        }
    )

    all_passed = all(c["passed"] for c in checks)

    if json_output:
        summary = {
            "status": "healthy" if all_passed else "unhealthy",
            "checks": checks,
        }
        print(json.dumps(summary, indent=2))
        return 0 if all_passed else 1

    # Formatted terminal output
    print("\n🔍 Qwen Web Automation System Health Diagnostic\n" + "─" * 50)
    for c in checks:
        icon = "  [✓]" if c["passed"] else "  [✗]"
        print(f"{icon} {c['name']}")
        print(f"      {c['detail']}")

    print("─" * 50)
    if all_passed:
        print("✅ All diagnostic checks passed! System is healthy and ready for execution.\n")
        return 0
    else:
        print("⚠️ Some diagnostic checks failed. Please follow the instructions above to fix.\n")
        return 1
