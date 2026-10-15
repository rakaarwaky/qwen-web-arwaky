#!/usr/bin/env python3
"""Standalone real-session pipeline runner for qwen-web-arwaky.

Invokes the real CLI entry point (`qwen-web-arwaky` or
`modules/root_cli_main_entry.py`) to execute 4 end-to-end pipelines against a
live, authenticated chat.qwen.ai session, using the fixtures under
`tests/fixtures/` (a symlink to `modules/prompt/tests/fixtures/`):

1. Pipeline 1: prompt direct (direct inline string prompt)
2. Pipeline 2: prompt file (prompt file: sample_prompt_v5.md)
3. Pipeline 3: prompt attach (prompt file + attachment: sample_attachment_v5.md)
4. Pipeline 4: swarm (fan the prompt fixture out across all role templates)

This is a script, not a pytest suite: it drives the shipped CLI against the
real site, so it needs a logged-in session (see `qwen-web-arwaky session login`)
and never runs in CI.

Outputs are saved in the default qwen-web-arwaky output directory
(~/.local/share/qwen-web-arwaky/output).

Usage:
  python3 scripts/real_tests.py               # Runs all pipelines in headful mode (default)
  python3 scripts/real_tests.py -1            # Run Pipeline 1 only
  python3 scripts/real_tests.py -2            # Run Pipeline 2 only
  python3 scripts/real_tests.py -3            # Run Pipeline 3 only
  python3 scripts/real_tests.py -4            # Run Pipeline 4 (swarm) only
  python3 scripts/real_tests.py -1 -2         # Run Pipeline 1 and 2 only
  python3 scripts/real_tests.py --headless -2 # Run Pipeline 2 only in headless mode
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Repository root path
ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = Path.home() / ".local" / "share" / "qwen-web-arwaky" / "output"
PROMPT_FIXTURE = ROOT_DIR / "tests" / "fixtures" / "sample_prompt_v5.md"
ATTACHMENT_FIXTURE = ROOT_DIR / "tests" / "fixtures" / "sample_attachment_v5.md"
SIMPLE_PROMPT_FIXTURE = ROOT_DIR / "tests" / "fixtures" / "sample_simple_prompt.md"


@dataclass(frozen=True)
class TestArgs:
    """Parsed CLI options selecting which real pipelines to run and how."""

    headless: bool
    run_p1: bool
    run_p2: bool
    run_p3: bool
    run_p4: bool
    output_dir: Path
    cli_entry: Path


def parse_args() -> TestArgs:
    """Parse CLI flags into a typed TestArgs."""
    parser = argparse.ArgumentParser(
        description="Run real end-to-end tests for qwen-web-arwaky pipelines using test fixtures."
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run browser in headless mode (default: False, runs headfully by default)",
    )
    parser.add_argument(
        "-1",
        "--1",
        "--p1",
        "--direct",
        dest="run_p1",
        action="store_true",
        help="Run Pipeline 1 (prompt direct inline text)",
    )
    parser.add_argument(
        "-2",
        "--2",
        "--p2",
        "--prompt-file",
        dest="run_p2",
        action="store_true",
        help="Run Pipeline 2 (prompt file sample_prompt_v5.md)",
    )
    parser.add_argument(
        "-3",
        "--3",
        "--p3",
        "--attachment",
        dest="run_p3",
        action="store_true",
        help="Run Pipeline 3 (prompt attach sample_attachment_v5.md)",
    )
    parser.add_argument(
        "-4",
        "--4",
        "--p4",
        "--swarm",
        dest="run_p4",
        action="store_true",
        help="Run Pipeline 4 (swarm fan-out of the prompt fixture across role templates)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Target directory for output files (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--cli-entry",
        type=Path,
        default=(Path(sys.executable).parent / "qwen-web-arwaky")
        if (Path(sys.executable).parent / "qwen-web-arwaky").exists()
        else ROOT_DIR / "modules" / "root_cli_main_entry.py",
        help="CLI entry point: the installed qwen-web-arwaky executable by default, "
        "or the repo entry script when no installed executable is present. "
        "The installed executable is preferred because running the entry script "
        "directly puts `modules/` on sys.path, and modules/logging/__init__.py "
        "shadows the stdlib `logging` module.",
    )
    ns = parser.parse_args()
    return TestArgs(
        headless=ns.headless,
        run_p1=ns.run_p1,
        run_p2=ns.run_p2,
        run_p3=ns.run_p3,
        run_p4=ns.run_p4,
        output_dir=ns.output_dir,
        cli_entry=ns.cli_entry,
    )


def _latest_swarm_run_dir() -> Path:
    """Return the newest swarm run directory, or a sentinel that never exists.

    ``swarm start`` writes each fan-out to its own swarm-id directory under
    the swarm output root, so the summary cannot check a fixed output file
    the way pipelines 1-3 do. Falls back to a non-existent path so the
    report still shows ``[File Missing]`` when no run directory exists.
    """
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    swarm_root = data_home / "qwen-web-arwaky" / "swarm"
    if not swarm_root.is_dir():
        return swarm_root / "no_run"
    runs = [p for p in swarm_root.iterdir() if p.is_dir()]
    if not runs:
        return swarm_root / "no_run"
    return max(runs, key=lambda p: p.stat().st_mtime)


def run_pipeline_cmd(name: str, cmd: list[str]) -> bool:
    """Execute a single pipeline command subprocess with live logging and metrics."""
    print("\n==================================================")
    print(f"🚀 Starting Pipeline: {name}")
    print(f"   Command: {' '.join(cmd)}")
    print("==================================================")

    start_time = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        elapsed = time.time() - start_time

        print(proc.stdout)
        if proc.returncode == 0:
            print(f"✅ [{name}] COMPLETED SUCCESSFULLY in {elapsed:.2f}s")
            return True
        else:
            print(f"❌ [{name}] FAILED with exit code {proc.returncode} in {elapsed:.2f}s")
            return False
    except Exception as exc:
        elapsed = time.time() - start_time
        print(f"❌ [{name}] FAILED with exception: {exc} in {elapsed:.2f}s")
        return False


def main() -> int:
    """Run the selected real end-to-end pipelines and return an exit code."""
    args = parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    cli_entry: Path = args.cli_entry

    # Verify fixture files exist
    if not PROMPT_FIXTURE.exists():
        print(f"❌ Error: Prompt fixture not found at {PROMPT_FIXTURE}", file=sys.stderr)
        return 1
    if not ATTACHMENT_FIXTURE.exists():
        print(f"❌ Error: Attachment fixture not found at {ATTACHMENT_FIXTURE}", file=sys.stderr)
        return 1

    # Validate the CLI entry point is invocable before launching any pipeline.
    probe = subprocess.run([str(cli_entry), "--help"], capture_output=True, text=True, cwd=str(ROOT_DIR))
    if probe.returncode != 0:
        print(
            f"❌ Error: CLI entry point {cli_entry} is not invocable (exit code {probe.returncode}).", file=sys.stderr
        )
        print(probe.stdout + probe.stderr, file=sys.stderr)
        return 1

    # Determine which pipelines to run: if no specific flags (-1, -2, -3, -4) are set, run all.
    run_p1 = args.run_p1
    run_p2 = args.run_p2
    run_p3 = args.run_p3
    run_p4 = args.run_p4
    if not (run_p1 or run_p2 or run_p3 or run_p4):
        run_p1 = run_p2 = run_p3 = run_p4 = True

    headless_flag = ["--headless"] if args.headless else []

    out_file_1 = output_dir / "real_test_direct_output.md"
    out_file_2 = output_dir / "real_test_prompt_only_output.md"
    out_file_3 = output_dir / "real_test_attachment_output.md"

    results: dict[str, tuple[bool, Path]] = {}

    executed_count = 0

    # --------------------------------------------------------------------------
    # Pipeline 1: Prompt Direct (Inline Text String)
    # --------------------------------------------------------------------------
    if run_p1:
        executed_count += 1
        direct_prompt_text = (
            "High-priority system test: Please provide a 3-bullet point executive summary "
            "of key architecture requirements for distributed microservices."
        )
        cmd_1 = [
            str(cli_entry),
            "prompt",
            "direct",
            "-t",
            direct_prompt_text,
            "-o",
            str(out_file_1),
            *headless_flag,
        ]
        results["Pipeline 1: prompt direct"] = (run_pipeline_cmd("Pipeline 1 (prompt direct)", cmd_1), out_file_1)

    # --------------------------------------------------------------------------
    # Pipeline 2: Prompt Only (File)
    # --------------------------------------------------------------------------
    if run_p2:
        if executed_count > 0:
            time.sleep(2.5)
        executed_count += 1
        cmd_2 = [
            str(cli_entry),
            "prompt",
            "file",
            "-i",
            str(PROMPT_FIXTURE),
            "-o",
            str(out_file_2),
            *headless_flag,
        ]
        results["Pipeline 2: prompt file"] = (run_pipeline_cmd("Pipeline 2 (prompt file)", cmd_2), out_file_2)

    # --------------------------------------------------------------------------
    # Pipeline 3: Prompt With Attachment (File + Attachment)
    # --------------------------------------------------------------------------
    if run_p3:
        if executed_count > 0:
            time.sleep(2.5)
        executed_count += 1
        cmd_3 = [
            str(cli_entry),
            "prompt",
            "attach",
            "-i",
            str(PROMPT_FIXTURE),
            "-a",
            str(ATTACHMENT_FIXTURE),
            "-o",
            str(out_file_3),
            *headless_flag,
        ]
        results["Pipeline 3: prompt attach"] = (
            run_pipeline_cmd("Pipeline 3 (prompt attach)", cmd_3),
            out_file_3,
        )

    # --------------------------------------------------------------------------
    # Pipeline 4: Swarm (Fan-Out Across Role Templates)
    # --------------------------------------------------------------------------
    if run_p4:
        if executed_count > 0:
            time.sleep(2.5)
        executed_count += 1
        cmd_4 = [
            str(cli_entry),
            "swarm",
            "start",
            str(PROMPT_FIXTURE),
        ]
        results["Pipeline 4: swarm"] = (
            run_pipeline_cmd("Pipeline 4 (swarm fan-out)", cmd_4),
            _latest_swarm_run_dir(),
        )

    # --------------------------------------------------------------------------
    # Summary Report
    # --------------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("📊 REAL TESTS PIPELINE SUMMARY REPORT")
    print("=" * 60)
    all_passed = True
    for name, (passed, path) in results.items():
        status = "PASSED ✅" if passed else "FAILED ❌"
        exists = "File Created" if path.exists() else "File Missing"
        print(f" • {name:<35} : {status} | [{exists}] -> {path}")
        if not passed:
            all_passed = False

    print("=" * 60)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
