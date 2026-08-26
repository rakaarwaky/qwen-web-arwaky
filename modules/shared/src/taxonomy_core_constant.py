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

# ─── Application paths (computed inline — pure constants, no functions) ──────
_XDG_DATA_HOME = (
    Path(os.environ["XDG_DATA_HOME"]) / "qwen-web"
    if os.environ.get("XDG_DATA_HOME")
    else (
        Path(os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")) / "qwen-web"
        if sys.platform == "win32"
        else Path.home() / "Library" / "Application Support" / "qwen-web"
        if sys.platform == "darwin"
        else Path.home() / ".local/share/qwen-web"
    )
)
_XDG_STATE_HOME = (
    Path(os.environ["XDG_STATE_HOME"]) / "qwen-web"
    if os.environ.get("XDG_STATE_HOME")
    else (
        Path(os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")) / "qwen-web" / "state"
        if sys.platform == "win32"
        else Path.home() / "Library" / "Logs" / "qwen-web"
        if sys.platform == "darwin"
        else Path.home() / ".local/state/qwen-web"
    )
)
_XDG_CACHE_HOME = (
    Path(os.environ["XDG_CACHE_HOME"]) / "qwen-web"
    if os.environ.get("XDG_CACHE_HOME")
    else (
        Path(os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")) / "qwen-web" / "cache"
        if sys.platform == "win32"
        else Path.home() / "Library" / "Caches" / "qwen-web"
        if sys.platform == "darwin"
        else Path.home() / ".cache/qwen-web"
    )
)
_XDG_CONFIG_HOME = (
    Path(os.environ["XDG_CONFIG_HOME"]) / "qwen-web"
    if os.environ.get("XDG_CONFIG_HOME")
    else (
        Path(os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")) / "qwen-web"
        if sys.platform == "win32"
        else Path.home() / "Library" / "Application Support" / "qwen-web"
        if sys.platform == "darwin"
        else Path.home() / ".config/qwen-web"
    )
)

XDG_DATA_HOME = _XDG_DATA_HOME
XDG_STATE_HOME = _XDG_STATE_HOME
XDG_CACHE_HOME = _XDG_CACHE_HOME
XDG_CONFIG_HOME = _XDG_CONFIG_HOME

DEFAULT_OUTPUT = XDG_DATA_HOME / "output"
DEFAULT_LOG = XDG_STATE_HOME / "log"
DEFAULT_SESSION = XDG_DATA_HOME / "qwen_session"
DEFAULT_VENV = XDG_DATA_HOME / "venv"
XDG_SKILL_MD = XDG_DATA_HOME / "SKILL.md"

CHAT_URL = "https://chat.qwen.ai/"

# Hardcoded default model. Pipeline forces this on every chat session so the
# user never has to pick a model manually (idempotent per-session).
DEFAULT_MODEL = "Qwen3.8-Max"

# Accessible-name locators for the chat model picker.
MODEL_SELECTOR_BUTTON = "Select Model"

MAX_ATTEMPTS = 3

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
    var responseNodes = document.querySelectorAll(
        '.qwen-markdown, .qwen-chat-message-assistant, .chat-response-message, .chat-message-assistant, '
        + '[data-role="assistant"], .response-message-content, .qwen-markdown-text, [class*="message-content"], '
        + '[class*="message-body"], [class*="response"]'
    );
    for (var ri = responseNodes.length - 1; ri >= 0; ri--) {
        var node = responseNodes[ri];
        if (node.closest('.qwen-chat-message-user') || node.closest('.user-message-content')) continue;

        // Tier 1: React Fiber extraction (preserves 100% of raw markdown & code without virtualization truncation)
        var fiberKey = Object.keys(node).find(k => k.startsWith('__reactFiber') || k.startsWith('__reactInternalInstance'));
        if (fiberKey) {
            var curr = node[fiberKey];
            for (var depth = 0; depth < 30 && curr; depth++) {
                if (curr.memoizedProps && typeof curr.memoizedProps === 'object') {
                    var content = curr.memoizedProps.content;
                    if (typeof content === 'string' && content.length > 0) {
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
        var ignoreSelectors = '.margin, .line-numbers, .monaco-editor-margin, [class*="line-numbers"], [class*="margin-view"], [class*="thinking"], [class*="status-card"], [class*="status"], [class*="thinking-tool"], button, svg, [class*="copy"], .copy-code-btn, [class*="code-header"]';

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

# ─── Saver defaults ─────────────────────────────────────────
DEFAULT_INCLUDE_HEADER: bool = True
DEFAULT_GENERATE_SIDECAR: bool = True
DEFAULT_ATOMIC_WRITE: bool = True
