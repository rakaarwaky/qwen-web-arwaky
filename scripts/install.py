#!/usr/bin/env python3
"""Cross-platform installation & environment setup script for qwen-web-cli & MCP server.

Supports Windows, macOS, and Linux without external shell dependencies.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def log(msg: str) -> None:
    print(msg, flush=True)


def get_venv_dir() -> Path:
    if os.environ.get("XDG_DATA_HOME"):
        return Path(os.environ["XDG_DATA_HOME"]) / "qwen-web" / "venv"
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local_app_data) / "qwen-web" / "venv"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "qwen-web" / "venv"
    return Path.home() / ".local/share/qwen-web/venv"


def get_venv_python(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def get_venv_pip(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "pip.exe"
    return venv_dir / "bin" / "pip"


def ensure_venv() -> Path:
    venv_dir = get_venv_dir()
    if sys.prefix != sys.base_prefix:
        log(f"⚡ [install] Using active virtual environment: {sys.prefix}")
        return Path(sys.executable)

    python_bin = get_venv_python(venv_dir)
    if not venv_dir.exists() or not python_bin.exists():
        log(f"🐍 [install] Creating virtual environment at {venv_dir}...")
        if venv_dir.exists():
            shutil.rmtree(venv_dir, ignore_errors=True)
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

    python_bin = get_venv_python(venv_dir)
    log(f"⚡ [install] Using virtual environment python: {python_bin}")
    return python_bin


def get_local_bin_dir() -> Path:
    if os.environ.get("XDG_BIN_HOME"):
        return Path(os.environ["XDG_BIN_HOME"])
    return Path.home() / ".local" / "bin"


def setup_project_venv_symlink(venv_dir: Path) -> None:
    """Create symlinks in PROJECT_ROOT (.venv and venv) pointing to XDG venv for IDE/editor support."""
    if sys.platform == "win32":
        return
    for name in (".venv", "venv"):
        target = PROJECT_ROOT / name
        if target.is_symlink():
            try:
                if target.resolve() == venv_dir.resolve():
                    continue
                target.unlink()
            except OSError:
                target.unlink(missing_ok=True)
        elif target.exists():
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            else:
                target.unlink(missing_ok=True)
        try:
            target.symlink_to(venv_dir)
            log(f"🔗 [install] Created project venv symlink: {target} -> {venv_dir}")
        except OSError as err:
            log(f"⚠ [install] Could not create {target} symlink: {err}")


def uninstall_previous(python_bin: Path) -> None:
    log("🧹 [install] Removing any previous qwen-web installation...")
    subprocess.run(
        [str(python_bin), "-m", "pip", "uninstall", "-y", "qwen-web", "qwen-web-cli"],
        capture_output=True,
    )

    if sys.platform != "win32":
        local_bin = get_local_bin_dir()
        for name in ("qwen-web-cli", "qwc", "qwen-web-mcp"):
            target = local_bin / name
            if target.is_symlink() or target.exists():
                with contextlib.suppress(OSError):
                    target.unlink()
        for name in (".venv", "venv"):
            target = PROJECT_ROOT / name
            if target.is_symlink():
                with contextlib.suppress(OSError):
                    target.unlink()


def install_package(python_bin: Path) -> None:
    log("📦 [install] Installing Python package in editable mode (qwen-web-cli / qwc)...")
    subprocess.run([str(python_bin), "-m", "pip", "install", "-e", str(PROJECT_ROOT)], check=True)


def install_playwright(python_bin: Path) -> None:
    log("🌐 [install] Installing Playwright Chromium browser binary...")
    subprocess.run([str(python_bin), "-m", "playwright", "install", "chromium"], check=True)


def setup_xdg_directories(python_bin: Path) -> None:
    log("📁 [install] Creating default runtime directories...")
    is_win = sys.platform == "win32"

    xdg_data = (
        Path(os.environ.get("XDG_DATA_HOME", Path.home() / ("AppData/Local" if is_win else ".local/share")))
        / "qwen-web"
    )
    xdg_state = (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ("AppData/Local" if is_win else ".local/state")))
        / "qwen-web"
    )
    xdg_cache = (
        Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ("AppData/Local/Temp" if is_win else ".cache")))
        / "qwen-web"
    )
    xdg_config = (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ("AppData/Roaming" if is_win else ".config")))
        / "qwen-web"
    )

    roles = ["role-architect", "role-business-analyst", "role-tech-lead"]
    for role in roles:
        (xdg_data / "input" / role / "done").mkdir(parents=True, exist_ok=True)
        (xdg_data / "input" / role / "failed").mkdir(parents=True, exist_ok=True)

    (xdg_data / "output").mkdir(parents=True, exist_ok=True)
    (xdg_data / "qwen_session").mkdir(parents=True, exist_ok=True)
    (xdg_state / "log").mkdir(parents=True, exist_ok=True)
    (xdg_cache / ".processing").mkdir(parents=True, exist_ok=True)
    xdg_config.mkdir(parents=True, exist_ok=True)

    # Session dir permissions & creation
    try:
        res = subprocess.run(
            [
                str(python_bin),
                "-c",
                "from modules.shared.src.taxonomy_core_constant import DEFAULT_SESSION; print(DEFAULT_SESSION)",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        session_dir = Path(res.stdout.strip())
    except Exception:
        session_dir = xdg_data / "qwen_session"

    log(f"🔐 [install] Repairing browser session dir: {session_dir}")
    session_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        with contextlib.suppress(OSError):
            os.chmod(session_dir, 0o700)

    skill_md = PROJECT_ROOT / "SKILL.md"
    if skill_md.exists():
        log("📄 [install] Copying SKILL.md template to XDG data directory...")
        shutil.copy2(skill_md, xdg_data / "SKILL.md")


def setup_bin_links(python_bin: Path) -> None:
    if sys.platform == "win32":
        return

    local_bin = get_local_bin_dir()
    log(f"🔑 [install] Linking entry points into {local_bin}...")
    local_bin.mkdir(parents=True, exist_ok=True)

    venv_bin_dir = python_bin.parent
    for name in ("qwen-web-arwaky", "qwa", "qwen-web-cli", "qwc", "qwen-web-mcp"):
        src = venv_bin_dir / name
        dst = local_bin / name
        if src.exists():
            if dst.is_symlink() or dst.exists():
                with contextlib.suppress(OSError):
                    dst.unlink()
            with contextlib.suppress(OSError):
                dst.symlink_to(src)

    bashrc = Path.home() / ".bashrc"
    path_line = f'export PATH="{local_bin}:${{PATH}}"'
    if bashrc.exists():
        content = bashrc.read_text(encoding="utf-8", errors="ignore")
        if str(local_bin) not in content:
            log(f"📝 [install] Adding {local_bin} to PATH in ~/.bashrc...")
            with bashrc.open("a", encoding="utf-8") as f:
                f.write(f"\n# qwen-web-cli global CLI PATH\n{path_line}\n")


def main() -> None:
    log("🚀 [install] Setting up qwen-web-cli environment (Cross-Platform)...")
    os.chdir(PROJECT_ROOT)

    python_bin = ensure_venv()
    setup_project_venv_symlink(get_venv_dir())
    uninstall_previous(python_bin)
    install_package(python_bin)
    install_playwright(python_bin)
    setup_xdg_directories(python_bin)
    setup_bin_links(python_bin)

    log("\n✅ [install] Setup complete!")
    if sys.platform == "win32":
        venv_scripts = get_venv_dir() / "Scripts"
        log(f"👉 To run CLI on Windows, activate venv: {venv_scripts}\\Activate.ps1")
        log("👉 Then run: qwc --login  atau  qwc --mcp")
    else:
        log("👉 You can now run 'qwc' or 'qwen-web-cli' from anywhere in your terminal!")
        log("👉 To perform initial session login: qwc --login")
        log("👉 To start MCP server: qwc --mcp")


if __name__ == "__main__":
    main()
