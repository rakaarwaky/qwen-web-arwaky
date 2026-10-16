#!/usr/bin/env python3
"""Cross-platform installation & environment setup script for qwen-web-arwaky & MCP server.

Supports Windows, macOS, and Linux without external shell dependencies.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Playwright's downloader applies a hard 30s socket timeout (NET_DEFAULT_TIMEOUT)
# unless PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT overrides it. Chrome-for-Testing is
# ~180MB, so the default reliably fails on slower links.
PW_DOWNLOAD_SOCKET_TIMEOUT_MS = "300000"
PW_DOWNLOAD_RETRIES = 3
PW_DOWNLOAD_TIMEOUT_SECONDS = 600
PW_MARKER_FILES = ("INSTALLATION_COMPLETE", "DEPENDENCIES_VALIDATED")


def log(msg: str) -> None:
    """Print an install progress message, flushing immediately."""
    print(msg, flush=True)


def get_venv_dir() -> Path:
    """Return the XDG/platform-conventional directory for the managed venv."""
    if os.environ.get("XDG_DATA_HOME"):
        return Path(os.environ["XDG_DATA_HOME"]) / "qwen-web-arwaky" / "venv"
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local_app_data) / "qwen-web-arwaky" / "venv"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "qwen-web-arwaky" / "venv"
    return Path.home() / ".local/share/qwen-web-arwaky/venv"


def get_venv_python(venv_dir: Path) -> Path:
    """Return the python executable path inside *venv_dir*."""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def get_venv_pip(venv_dir: Path) -> Path:
    """Return the pip executable path inside *venv_dir*."""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "pip.exe"
    return venv_dir / "bin" / "pip"


def ensure_venv() -> Path:
    """Create the managed venv when missing and return its python executable."""
    venv_dir = get_venv_dir()

    # If the current executable is already inside the target XDG venv, use it directly.
    try:
        resolved = Path(sys.executable).resolve()
        if resolved.is_relative_to(venv_dir.resolve()):
            log(f"⚡ [install] Using active virtual environment: {resolved}")
            return resolved
    except (ValueError, OSError):
        pass

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
    """Return the directory where CLI entry-point symlinks are placed."""
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
    """Remove earlier package installs, entry-point links, and venv symlinks."""
    log("🧹 [install] Removing any previous qwen-web-arwaky installation...")
    subprocess.run(
        [str(python_bin), "-m", "pip", "uninstall", "-y", "qwen-web", "qwen-web-cli", "qwen-web-arwaky"],
        capture_output=True,
    )

    if sys.platform != "win32":
        local_bin = get_local_bin_dir()
        for name in ("qwen-web-arwaky", "qwa", "qwen-web-mcp"):
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
    """Pip-install the project into the managed venv and clean build artifacts."""
    log("📦 [install] Installing Python package (immutable mode)...")
    subprocess.run([str(python_bin), "-m", "pip", "install", str(PROJECT_ROOT)], check=True)
    # Cleanup build artifacts
    build_dir = PROJECT_ROOT / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)


def _pw_env() -> dict[str, str]:
    """Build the environment for playwright install with a workable socket timeout."""
    env = os.environ.copy()
    env["PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT"] = PW_DOWNLOAD_SOCKET_TIMEOUT_MS
    return env


def _pw_cache_dir() -> Path:
    """Return the Playwright browsers cache root for the current platform."""
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        return Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"])
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "ms-playwright"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "ms-playwright"


def _pw_dry_run(python_bin: Path) -> str:
    """Return ``playwright install --dry-run`` output for the chromium bundle."""
    proc = subprocess.run(
        [str(python_bin), "-m", "playwright", "install", "--dry-run", "chromium"],
        capture_output=True,
        text=True,
        env=_pw_env(),
    )
    return proc.stdout + proc.stderr


def _pw_install_complete(python_bin: Path) -> bool:
    """True when every Chromium component playwright needs is already installed."""
    return "is already installed" in _pw_dry_run(python_bin)


def _pw_component_url(python_bin: Path, display_name: str) -> str:
    """Extract the primary download URL for one component from the dry-run output."""
    target = display_name.strip()
    lines = _pw_dry_run(python_bin).splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == target or stripped.startswith(target + " "):
            for follow in lines[idx + 1 : idx + 6]:
                if "Download url:" in follow:
                    return follow.split("Download url:", 1)[1].strip()
    return ""


def _pw_component_complete(browser_dir: Path) -> bool:
    """True when the component dir holds its payload and both marker files.

    Also repairs the executable bit on any ELF binaries, which the zip
    extraction drops and which Playwright's own installer preserves.
    """
    if not browser_dir.exists():
        return False
    if any(not (browser_dir / marker).exists() for marker in PW_MARKER_FILES):
        return False
    _pw_make_extracted_executables(browser_dir)
    return any(p.is_dir() and not p.name.startswith(".") for p in browser_dir.iterdir())


def _pw_make_extracted_executables(browser_dir: Path) -> None:
    """Restore the executable bit the zip extraction drops on ELF binaries."""
    for path in browser_dir.rglob("*"):
        if not path.is_file():
            continue
        with path.open("rb") as fh:
            if fh.read(4) == b"\x7fELF":
                path.chmod(0o755)


def _pw_curl_fallback(python_bin: Path) -> bool:
    """Fetch each Chromium component zip with curl and unpack it into the cache."""
    cache_dir = _pw_cache_dir()
    components: list[tuple[str, str]] = []
    name = ""
    for line in _pw_dry_run(python_bin).splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith(("Install location:", "Download ")) and not name:
            name = stripped.split(" (playwright")[0]
        elif stripped.startswith("Install location:"):
            location = stripped.split("Install location:", 1)[1].strip()
            if location.startswith(str(cache_dir)):
                components.append((name, location))
            name = ""
    if not components:
        log("⚠ [install] Could not determine the Chromium install locations for curl fallback.")
        return False

    for display_name, location in components:
        url = _pw_component_url(python_bin, display_name)
        if not url:
            log(f"⚠ [install] No download URL for {display_name}; skipping.")
            continue
        browser_dir = Path(location)
        if _pw_component_complete(browser_dir):
            log(f"✅ [install] Cached {display_name} present at {browser_dir}; skipping download.")
            continue

        log(f"⬇ [install] curl fallback for {display_name}: {url}")
        with tempfile.TemporaryDirectory(prefix="pw-chromium-") as tmp:
            zip_path = Path(tmp) / url.rsplit("/", 1)[-1]
            curl_cmd = [
                "curl",
                "-fSL",
                "--retry",
                "3",
                "--retry-delay",
                "5",
                "--connect-timeout",
                "30",
                "--max-time",
                str(PW_DOWNLOAD_TIMEOUT_SECONDS),
                "-o",
                str(zip_path),
                url,
            ]
            result = subprocess.run(curl_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                log(f"⚠ [install] curl download failed for {display_name}: {result.stderr.strip()}")
                return False

            browser_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(browser_dir)
            _pw_make_extracted_executables(browser_dir)
            for marker in PW_MARKER_FILES:
                (browser_dir / marker).touch()
        log(f"✅ [install] {display_name} extracted to {browser_dir}")
    return True


def install_playwright(python_bin: Path) -> None:
    """Install the Playwright Chromium binary, falling back to a curl download.

    The bounded retry count exists because ``playwright install`` has a hard
    30s socket timeout in its Node downloader and the Chromium archive is a
    large download. Each attempt runs with the raised connection timeout;
    when every retry fails, the curl fallback fetches the archives with a
    generous ``--max-time`` and unpacks them straight into the browsers
    cache, marking each install complete so playwright stops trying.
    """
    log("🌐 [install] Installing Playwright Chromium browser binary...")
    # A zip extraction that dropped the executable bit leaves markers in place,
    # so repair the cache before trusting the "already installed" early exit.
    cache_dir = _pw_cache_dir()
    if cache_dir.exists():
        _pw_make_extracted_executables(cache_dir)
    if _pw_install_complete(python_bin):
        log("✅ [install] Playwright Chromium is already installed.")
        return

    env = _pw_env()
    last_error = ""
    for attempt_no in range(1, PW_DOWNLOAD_RETRIES + 1):
        try:
            subprocess.run(
                [str(python_bin), "-m", "playwright", "install", "chromium"],
                check=True,
                env=env,
            )
            log("✅ [install] Playwright Chromium installed.")
            return
        except subprocess.CalledProcessError as exc:
            last_error = str(exc)
            log(f"⚠ [install] Playwright download attempt {attempt_no}/{PW_DOWNLOAD_RETRIES} failed ({last_error}).")
            if attempt_no < PW_DOWNLOAD_RETRIES:
                log("  Retrying...")

    log("⚠ [install] Playwright installer failed; attempting direct curl download...")
    if shutil.which("curl") and _pw_curl_fallback(python_bin):
        return

    log("⚠ [install] Playwright Chromium download failed (network restricted?).")
    log("  The CLI is still installed; use a cached browser binary, or run:")
    log(f"    PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT={PW_DOWNLOAD_SOCKET_TIMEOUT_MS} \\")
    log(f"      {python_bin} -m playwright install chromium")
    log("  and retry once the network allows it.")


def setup_xdg_directories(python_bin: Path) -> None:
    """Create the runtime data directories and seed the SKILL.md template."""
    log("📁 [install] Creating default runtime directories...")
    is_win = sys.platform == "win32"

    xdg_data = (
        Path(os.environ.get("XDG_DATA_HOME", Path.home() / ("AppData/Local" if is_win else ".local/share")))
        / "qwen-web-arwaky"
    )
    xdg_state = (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ("AppData/Local" if is_win else ".local/state")))
        / "qwen-web-arwaky"
    )
    xdg_cache = (
        Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ("AppData/Local/Temp" if is_win else ".cache")))
        / "qwen-web-arwaky"
    )
    xdg_config = (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ("AppData/Roaming" if is_win else ".config")))
        / "qwen-web-arwaky"
    )

    roles = ["role-architect", "role-business-analyst", "role-tech-lead"]
    for role in roles:
        (xdg_data / "input" / role / "done").mkdir(parents=True, exist_ok=True)
        (xdg_data / "input" / role / "failed").mkdir(parents=True, exist_ok=True)

    (xdg_data / "output").mkdir(parents=True, exist_ok=True)
    (xdg_data / "sessions" / "default").mkdir(parents=True, exist_ok=True)
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
        session_dir = xdg_data / "sessions" / "default"

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
    """Symlink CLI entry points into the local bin dir and extend PATH."""
    if sys.platform == "win32":
        return

    local_bin = get_local_bin_dir()
    log(f"🔑 [install] Linking entry points into {local_bin}...")
    local_bin.mkdir(parents=True, exist_ok=True)

    venv_bin_dir = python_bin.parent
    for name in ("qwen-web-arwaky", "qwa", "qwen-web-mcp"):
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
                f.write(f"\n# qwen-web-arwaky global CLI PATH\n{path_line}\n")


def main() -> None:
    """Run the full install pipeline: venv, package, browser, dirs, links."""
    log("🚀 [install] Setting up qwen-web-arwaky environment (Cross-Platform)...")
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
        log("👉 Then run: qwa --login  atau  qwa --mcp")
    else:
        log("👉 You can now run 'qwa' or 'qwen-web-arwaky' from anywhere in your terminal!")
        log("👉 To perform initial session login: qwa --login")
        log("👉 To start MCP server: qwa --mcp")


if __name__ == "__main__":
    main()
