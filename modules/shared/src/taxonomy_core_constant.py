"""Core domain + cross-cutting constants for qwen-web: chat URL,
service name, DOM selectors, and auth/challenge keywords.

Taxonomy layer (taxonomy(constant)): pure literals and constant values only.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]

STATUS_FILENAME: str = "status.json"

# Application identifier used as the leaf of every XDG base directory.
# Previously the hardcoded "qwen-web" string; standardized to the product
# name "qwen-web-arwaky" so all state lives under ~/.local/share/qwen-web-arwaky.
_APP_NAME = "qwen-web-arwaky"

# ─── Application paths (computed inline — pure constants, no functions) ──────
_XDG_DATA_HOME = (
    Path(os.environ["XDG_DATA_HOME"]) / _APP_NAME
    if os.environ.get("XDG_DATA_HOME")
    else (
        Path(os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")) / _APP_NAME
        if sys.platform == "win32"
        else Path.home() / "Library" / "Application Support" / _APP_NAME
        if sys.platform == "darwin"
        else Path.home() / ".local/share" / _APP_NAME
    )
)
_XDG_STATE_HOME = (
    Path(os.environ["XDG_STATE_HOME"]) / _APP_NAME
    if os.environ.get("XDG_STATE_HOME")
    else (
        Path(os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")) / _APP_NAME / "state"
        if sys.platform == "win32"
        else Path.home() / "Library" / "Logs" / _APP_NAME
        if sys.platform == "darwin"
        else Path.home() / ".local/state" / _APP_NAME
    )
)
_XDG_CACHE_HOME = (
    Path(os.environ["XDG_CACHE_HOME"]) / _APP_NAME
    if os.environ.get("XDG_CACHE_HOME")
    else (
        Path(os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")) / _APP_NAME / "cache"
        if sys.platform == "win32"
        else Path.home() / "Library" / "Caches" / _APP_NAME
        if sys.platform == "darwin"
        else Path.home() / ".cache" / _APP_NAME
    )
)
_XDG_CONFIG_HOME = (
    Path(os.environ["XDG_CONFIG_HOME"]) / _APP_NAME
    if os.environ.get("XDG_CONFIG_HOME")
    else (
        Path(os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")) / _APP_NAME
        if sys.platform == "win32"
        else Path.home() / "Library" / "Application Support" / _APP_NAME
        if sys.platform == "darwin"
        else Path.home() / ".config" / _APP_NAME
    )
)

XDG_DATA_HOME = _XDG_DATA_HOME
XDG_STATE_HOME = _XDG_STATE_HOME
XDG_CACHE_HOME = _XDG_CACHE_HOME
XDG_CONFIG_HOME = _XDG_CONFIG_HOME

DEFAULT_OUTPUT = XDG_DATA_HOME / "output"
# Swarm runs use a dedicated sub-directory under the same XDG root so the
# per-swarm run folders do not collide with regular prompt outputs.
SWARM_OUTPUT_ROOT = XDG_DATA_HOME / "swarm"
DEFAULT_LOG = XDG_STATE_HOME / "log"
DEFAULT_VENV = XDG_DATA_HOME / "venv"
DEFAULT_JOBS_DIR = XDG_STATE_HOME / "jobs"
XDG_SKILL_MD = XDG_DATA_HOME / "SKILL.md"

# ─── Parallel job execution & resource budgets (Issue #365) ───────────────────
# Number of prompt jobs allowed to run concurrently. Each worker launches its
# own Chromium browser instance with an ephemeral clone of the login session.
# Resource note: each headless Chromium worker consumes ~150-300 MiB RAM.
# Default limit of 10 workers bounds peak parallel footprint to ~2.5 GiB.
DEFAULT_MAX_WORKERS = 10

# Per-browser memory budget (issue #291). A headless Chromium worker plus its
# ephemeral session clone is budgeted at 700 MiB so a fan-out keeps real
# headroom instead of driving the host into the OOM killer on a small runner.
MIN_MEMORY_PER_WORKER_BYTES = 700 * 1024 * 1024

# Share of total memory withheld from the browser fleet when only total RAM is
# measurable; the rest stays with the OS, the agent process, and the user.
MEMORY_RESERVED_FRACTION = 0.25

# Swarm-specific concurrency override env var and default cap (Issue #323).
DEFAULT_SWARM_CONCURRENCY = 10
SWARM_CONCURRENCY_ENV = "QWEN_SWARM_CONCURRENCY"

#: Resource-governance policy (issue #277). Above this many concurrent browsers
#: a fan-out is announced with an explicit warning before it starts; below it the
#: start is silent, matching the interactive cost users expect.
SWARM_RESOURCE_WARNING_BROWSERS = 4

#: Admission-control bound for the async job queue (issue #362). Submissions
#: beyond this depth are refused with a retryable over-capacity error instead
#: of growing the executor's pending queue without limit. One pending slot per
#: running worker is enough headroom to keep every worker fed while bounding
#: the worst-case backlog to a known depth.
MAX_PENDING_JOBS_PER_WORKER = 1

CHAT_URL = "https://chat.qwen.ai/"

# Browser navigation timeouts (milliseconds). The primary goto uses 30s with
# 4 retries + exponential backoff; shorter values are used for in-session
# resets and thread cleanup where a stale connection is expected.
NAVIGATION_TIMEOUT_MS = 30_000
NAVIGATION_LOAD_TIMEOUT_MS = 15_000

# Default model. Pipeline forces this on every chat session so the
# user never has to pick a model manually (idempotent per-session).
# Overridable via the QWEN_MODEL or QWEN_DEFAULT_MODEL environment variable, or
# per-run via the --model CLI flag (issue #283). QWEN_DEFAULT_MODEL is checked
# first so existing deployments keep their current value.
DEFAULT_MODEL = os.environ.get("QWEN_DEFAULT_MODEL", os.environ.get("QWEN_MODEL", "")).strip() or "Qwen3.8-Max"

# Accessible-name locators for the chat model picker.
MODEL_SELECTOR_BUTTON = "Select Model"

MAX_ATTEMPTS = 3

# ─── Response retry policy ──────────────────────────────────────────────────
# PromptFlowDispatcher retries a dispatch when the model returns a
# rate-limit / throttling page instead of a real answer. Attempts are bounded
# by MAX_ATTEMPTS (3); the wait before retry N is RETRY_BASE_DELAY_SEC * N.
RETRY_BASE_DELAY_SEC: int = 30

RATE_LIMIT_KEYWORDS: tuple[str, ...] = (
    "too many requests",
    "rate limit",
    "rate-limit",
    "ratelimit",
    "throttl",
    "429",
    "slow down",
    "try again later",
    "there was an issue connecting to",
)

SERVICE_NAME = "qwen-web"

SD_NOTIFY_READY = "READY=1"
SD_NOTIFY_STOPPING = "STOPPING=1"
SD_NOTIFY_RELOADING = "RELOADING=1"

TEXTAREA_SELECTOR = "textarea.message-input-textarea"

NEW_CHAT_SELECTORS: tuple[str, ...] = (
    "[aria-label='New Chat']",
    "[aria-label*='New chat' i]",
    "button[aria-label*='New chat' i]",
    "div[aria-label*='New chat' i]",
)

INPUT_SELECTORS: tuple[str, ...] = (
    "textarea.message-input-textarea",
    "textarea",
    "[placeholder*='Ask' i]",
    "[placeholder*='Message' i]",
)

SEND_SELECTORS: tuple[str, ...] = (
    ".message-input-right-button-send button",
    "button[aria-label*='Send' i]:not(.disabled):not([disabled])",
    "button[type='submit']:not(.disabled):not([disabled])",
    "button[class*='send' i]:not(.disabled):not([disabled])",
)

MESSAGE_SELECTORS: tuple[str, ...] = (
    ".qwen-chat-message-assistant",
    ".chat-response-message",
    ".qwen-markdown",
    ".markdown-body",
    "[class*='assistant'] [class*='markdown']",
)

COMBINED_MESSAGE_SELECTOR: str = ", ".join(MESSAGE_SELECTORS)
RESPONSE_CONTENT_SELECTOR: str = ".qwen-markdown, .markdown-body, .response-message-content, .qwen-markdown-text"

#: Selectors matching a committed user turn in Qwen's live chat DOM.
#: The user bubble renders immediately when a turn is acknowledged,
#: long before the assistant response streams in, so these let the
#: dispatch-ACK stage observe the user turn without waiting on the
#: response surface.
USER_MESSAGE_SELECTORS: tuple[str, ...] = (
    ".qwen-chat-message-user",
    ".chat-user-message",
    "[class*='user-message-content']",
)
USER_COMBINED_SELECTOR: str = ", ".join(USER_MESSAGE_SELECTORS)

STOP_BUTTON_SELECTORS: str = (
    "button[aria-label*='Stop' i], .message-input-right-button-send button:has(svg rect), "
    "[class*='stop-btn'], [class*='icon-stop'], [class*='stopButton']"
)
SEND_DISABLED_SELECTORS: str = (
    "button[aria-label*='Send' i][disabled], button[class*='send' i][disabled], "
    ".message-input-right-button-send button[disabled]"
)
TYPING_INDICATOR_SELECTORS: str = (
    ".thinking:not([style*='display: none']):not([class*='completed']):not([class*='complete']), "
    "[class*='qwen-chat-thinking-status-card']:not([class*='completed']):not([class*='complete'])"
    ":not(:has-text('completed')), "
    "[class*='thinking-status-card']:not([class*='completed']):not([class*='complete'])"
    ":not(:has-text('completed')), "
    "[class*='thinking-process'], [class*='thinking']:not([class*='completed']):not([class*='complete'])"
    ":not(:has-text('completed')), "
    "[class*='typing'], [class*='streaming']"
)

JS_GET_RESPONSE_TEXT: str = r"""
() => {
    // Markers for a stale Qwen thinking card. The card renders inside the
    // assistant message container and, once the thinking phase ends, leaves a
    // bare status line such as "Thought stopped". Treating that line as the
    // answer made the stream monitor stabilise on the card instead of the real
    // response (run 20260926_014817_5cd3cc wrote a 32-byte output holding only
    // "Thought stopped"). Any node whose whole text matches one of these is a
    // stale card: skip it and keep scanning older nodes.
    var THINKING_CARD_MARKERS = [
        'thought stopped',
        'thought completed',
        'thought complete',
        'thinking stopped',
        'thinking completed',
        'thinking complete',
        'thinking process'
    ];
    var responseNodes = document.querySelectorAll(
        '.qwen-markdown, .qwen-chat-message-assistant, .chat-response-message, .chat-message-assistant, '
        + '[data-role="assistant"], .response-message-content, .qwen-markdown-text, [class*="message-content"], '
        + '[class*="message-body"], [class*="response"]'
    );
    var paginationRe = /^\s*\d+\s*\/\s*\d+\s*$/;
    for (var ri = responseNodes.length - 1; ri >= 0; ri--) {
        var node = responseNodes[ri];
        if (node.closest('.qwen-chat-message-user') || node.closest('.user-message-content')) continue;

        // Skip pagination indicator nodes (e.g. "1/2", "2/3")
        var nodeText = (node.innerText || '').trim();
        if (paginationRe.test(nodeText)) continue;

        // Tier 1: React Fiber extraction (preserves 100% of raw markdown & code without virtualization truncation)
        var fiberKey = Object.keys(node).find(k => k.startsWith('__reactFiber') || k.startsWith('__reactInternalInstance'));
        if (fiberKey) {
            var curr = node[fiberKey];
            for (var depth = 0; depth < 30 && curr; depth++) {
                if (curr.memoizedProps && typeof curr.memoizedProps === 'object') {
                    var content = curr.memoizedProps.content;
                    if (typeof content === 'string' && content.length > 0 && !paginationRe.test(content.trim())) {
                        return content.trim();
                    }
                }
                curr = curr.return;
            }
        }

        // Tier 2: Live DOM Tree Walker fallback
        var outerContainer = node.closest(
            '.qwen-markdown, .qwen-chat-message-assistant, .chat-response-message, .chat-message-assistant, '
            + '[data-role="assistant"], [class*="message-content"], [class*="message-body"], [class*="response"]'
        );
        var targetNode = outerContainer || node;

        var text = '';
        var blockTags = new Set(['P', 'DIV', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'LI', 'TR', 'TD', 'TH', 'PRE', 'BLOCKQUOTE', 'BR', 'TABLE', 'UL', 'OL', 'SECTION', 'ARTICLE']);
        var ignoreSelectors = '.margin, .line-numbers, .monaco-editor-margin, [class*="line-numbers"], [class*="margin-view"], [class*="thinking"], [class*="status-card"], [class*="status"], [class*="thinking-tool"], button, svg, [class*="copy"], .copy-code-btn, [class*="code-header"], [class*="pagination"], [class*="pager"]';

        function walk(n, isPre) {
            if (n.nodeType === Node.ELEMENT_NODE) {
                if (n.matches && n.matches(ignoreSelectors)) return;

                var tag = n.tagName;
                var classStr = (n.className && typeof n.className === 'string') ? n.className : '';
                var isCodeBlock = tag === 'PRE' || classStr.includes('code-block') || classStr.includes('highlight') || classStr.includes('markdown-code');
                var nextIsPre = isPre || isCodeBlock;

                if (tag === 'BR') {
                    text += '\n';
                    return;
                }

                for (var i = 0; i < n.childNodes.length; i++) {
                    walk(n.childNodes[i], nextIsPre);
                }

                if (blockTags.has(tag) && text.length > 0 && text[text.length - 1] !== '\n') {
                    text += '\n';
                }
            } else if (n.nodeType === Node.TEXT_NODE) {
                var val = n.nodeValue;
                if (!isPre) {
                    val = val.replace(/[\r\n\t ]+/g, ' ');
                }
                text += val;
            }
        }

        walk(targetNode, false);

        var responseText = text.replace(/\u00a0/g, ' ').replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();

        if (responseText.startsWith("Thinking completed")) {
            responseText = responseText.replace(/^Thinking completed\s*/, '');
        }
        if (responseText.endsWith("Skip")) {
            responseText = responseText.replace(/\s*Skip$/, '').trim();
        }
        if (responseText === "Skip") {
            continue;
        }
        // A stale thinking card leaves a bare status line ("Thought stopped")
        // inside the assistant message container. Treat it as a non-answer and
        // keep scanning older nodes for the real response.
        var isThinkingCard = ~THINKING_CARD_MARKERS.indexOf(responseText.toLowerCase().trim());
        if (isThinkingCard) continue;
        // Skip if text is only a pagination indicator
        if (paginationRe.test(responseText)) {
            continue;
        }
        if (responseText.length > 0) return responseText;
    }
    return null;
}
"""


JS_COUNT_TURNS: str = """
() => {
    var turns = document.querySelectorAll(
        '.chat-response-message, [class*="chat-message"], [class*="message-item"], '
        + '[class*="virtual-list-item"], [class*="turn"]'
    );
    return turns.length;
}
"""

AUTH_KEYWORDS = ("login", "passport", "auth", "signin", "account", "sso", "guest")

LOGIN_FORM_SELECTORS: tuple[str, ...] = (
    "input[type='password']",
    "input[name='password']",
    "button:has-text('Log in')",
    "a:has-text('Log in')",
    "button:has-text('Sign in')",
    "a:has-text('Sign in')",
    "button:has-text('Sign up')",
    "a:has-text('Sign up')",
    ".login-form",
    "[class*='login']",
    "[class*='passport']",
)

CHALLENGE_KEYWORDS: tuple[str, ...] = (
    "just a moment",
    "attention required!",
    "verify you are human",
    "enable javascript and cookies",
    "502 bad gateway",
    "504 gateway time-out",
    "service unavailable",
    "access denied",
    "oops! there are files still uploading",
    "files still uploading",
    "please wait for the upload to complete",
    "please wait until the uploaded",
    "currently parsing file",
    "finished processing before sending",
    "failed to upload",
    "something went wrong",
)

# ─── Qwen thinking-card markers ─────────────────────────────────────────────
# Mirror of the JS THINKING_CARD_MARKERS array inside JS_GET_RESPONSE_TEXT.
# Kept as a Python tuple so tests can assert the JS list stays in sync without
# re-parsing the JS source.
THINKING_CARD_TEXT_MARKERS: tuple[str, ...] = (
    "thought stopped",
    "thought completed",
    "thought complete",
    "thinking stopped",
    "thinking completed",
    "thinking complete",
    "thinking process",
)

# ─── Folder compiler defaults ───────────────────────────────────────────────
MAX_FOLDER_DEPTH: int = 5
MAX_IMPORT_DEPTH: int = 1

CODE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".rs",
        ".ts",
        ".js",
        ".jsx",
        ".tsx",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".cfg",
        ".md",
        ".txt",
        ".css",
        ".scss",
        ".html",
        ".go",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".rb",
        ".php",
        ".swift",
        ".kt",
        ".kts",
    }
)

EXCLUDED_DIR_NAMES: frozenset[str] = frozenset(
    {
        "__pycache__",
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "env",
        "node_modules",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        "build",
        "dist",
        ".eggs",
        ".qwen-web",
        "target",
        ".cache",
    }
)

EXCLUDED_FILE_PATTERNS: frozenset[str] = frozenset(
    {
        ".env",
        ".env.local",
        ".env.production",
        ".env.staging",
        ".env.development",
        "id_rsa",
        "id_ed25519",
        "id_ecdsa",
        "id_dsa",
    }
)

EXCLUDED_FILE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pem",
        ".key",
        ".pfx",
        ".p12",
        ".pkcs12",
        ".kdbx",
        ".secret",
    }
)

# ─── Saver defaults ─────────────────────────────────────────
DEFAULT_GENERATE_SIDECAR: bool = True
DEFAULT_ATOMIC_WRITE: bool = True

# ─── Config domain: request timeout ─────────────────────────────────────────
#: Built-in ceiling on the response-wait when no env override is present.
#: Matches the default carried by ``AppConfig`` so a bare probe and a built
#: config never diverge.
DEFAULT_REQUEST_TIMEOUT_SEC: int = 600

#: Environment override for ``DEFAULT_REQUEST_TIMEOUT_SEC``.
REQUEST_TIMEOUT_ENV: str = "QWEN_REQUEST_TIMEOUT_SEC"

#: Truthy spellings for boolean env switches.
TRUE_VALUES: frozenset[str] = frozenset({"1", "true", "yes"})

#: Falsy spellings for boolean env switches.
FALSE_VALUES: frozenset[str] = frozenset({"0", "false", "no"})

# ─── Update domain ───────────────────────────────────────────────────────────
#: Package name the self-update pipeline checks and installs.
DEFAULT_PACKAGE_NAME: str = "qwen-web-arwaky"

#: Upstream GitHub repository for release discovery and git updates.
DEFAULT_GITHUB_REPO: str = "rakaarwaky/qwen-web-arwaky"

#: Release discovery URL template, ``{repo}`` substituted.
GITHUB_RELEASE_URL: str = "https://api.github.com/repos/{repo}/releases/latest"

#: Git ref URL template, ``{repo}`` and ``{tag}`` substituted.
GITHUB_GIT_REF_URL: str = "https://api.github.com/repos/{repo}/git/refs/tags/{tag}"

#: Git tag URL template, ``{repo}`` and ``{sha}`` substituted.
GITHUB_GIT_TAG_URL: str = "https://api.github.com/repos/{repo}/git/tags/{sha}"

#: Environment override for ``DEFAULT_GITHUB_REPO``.
GITHUB_REPO_ENV: str = "QWEN_WEB_GITHUB_REPO"

#: Self-update client identity sent to the GitHub API.
USER_AGENT: str = "qwen-web-arwaky-updater/1.0"

# ─── Prompt domain: stream timeouts ─────────────────────────────────────────
#: Absolute backstop for a stalled stream run; override per environment with
#: ``QWEN_STREAM_SAFETY_TIMEOUT_SEC`` (issue #330) since a 4h hardcoded
#: budget is untestable in staging.
DEFAULT_SAFETY_TIMEOUT_SEC: int = 4 * 60 * 60

#: Event-driven stall threshold: no forward event within this window classifies
#: the run stuck; slow-but-alive generations keep emitting events and are
#: never misclassified.
DEFAULT_STALL_TIMEOUT_SEC: int = 300

#: Environment override for ``DEFAULT_SAFETY_TIMEOUT_SEC``.
SAFETY_TIMEOUT_ENV: str = "QWEN_STREAM_SAFETY_TIMEOUT_SEC"

# ─── Job domain: status document contract ──────────────────────────────────
#: Version of the ``status.json`` document contract; bump when a field is
#: added or its meaning changes so external monitors can branch on it
#: (issue #296).
STATUS_SCHEMA_VERSION: int = 2

# ─── Session domain ──────────────────────────────────────────────────────────
#: The old single-profile location (pre-multi-account). Used only for migration.
DEFAULT_SESSION_OLD: Path = XDG_DATA_HOME / "qwen_session"

#: New per-account session root.
SESSIONS_DIR: Path = XDG_DATA_HOME / "sessions"

#: Default account profile (the one used when no --session flag is given).
DEFAULT_SESSION: Path = SESSIONS_DIR / "default"

#: Pool file recording active session pool under ``SESSIONS_DIR``.
POOL_FILE: Path = SESSIONS_DIR / "sessions.json"

#: Chromium profile directory name reused across runs.
PROFILE_DIR_NAME: str = "Default"

# ─── Config domain: capacity report source labels ────────────────────────────
# Names the effective worker count can come from, for the report's ``source``.

#: Source label when the worker count is derived from measured memory.
SOURCE_DERIVED: str = "derived from measured available memory"

#: Source label when the worker count comes from the env override.
SOURCE_OVERRIDE: str = "QWEN_WEB_MAX_WORKERS environment override"

# ─── Session domain: rate-limit detection ───────────────────────────────────
#: Regex patterns matching rate-limit or capacity-exceeded text in the UI,
#: used by the session health checker to flag a rate-limited session.
RATE_LIMIT_PATTERNS: list[str] = [
    r"upper\s+limit",
    r"rate\s+limit",
    r"daily\s+limit",
    r"quota\s+exceeded",
    r"try\s+again\s+tomorrow",
    r"too\s+many\s+requests",
    r"429",
    r"limit\s+reached",
    r"usage\s+limit",
]


# ─── Prompt templates (role-based built-in templates) ─────────────────────
# Role templates now live as Markdown files under ``modules/templates/{role}.md``
# and are discovered dynamically at runtime by
# ``modules/shared/src/utility_core_prompt_template.py``. No hardcoded manifest
# remains in this module.

# Parse-wait loop tuning for the send dispatcher's document-parse gate:
# window during which parse-waiting stays maximally responsive (fast phase),
# poll interval inside the fast phase, and backed-off interval for long parses.
PARSE_FAST_PHASE_SEC: float = 5.0
PARSE_POLL_FAST_MS: int = 500
PARSE_POLL_SLOW_MS: int = 1000
