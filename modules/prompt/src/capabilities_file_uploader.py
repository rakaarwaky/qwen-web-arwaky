"""Capabilities: file uploader (AES403).

Implements IUploadProtocol.
"""

from __future__ import annotations

import contextlib
import time
from pathlib import Path
from typing import Any, cast

from playwright.sync_api import Error, Page

from modules.shared.src.common.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.common.taxonomy_core_error import FileValidationError
from modules.shared.src.common.taxonomy_core_event import EVENT_DOCUMENT_PARSED, EVENT_FILE_UPLOADED
from modules.shared.src.common.taxonomy_core_vo import (
    DEFAULT_UPLOAD_CONFIG,
    BackoffDelaySec,
    CardRenderTimeoutMs,
    DropdownTimeoutMs,
    FileChooserTimeoutMs,
    FileSizeBytes,
    MaxFileSizeBytes,
    MaxRetries,
    OptionTimeoutMs,
    UploadConfig,
)
from modules.shared.src.common.utility_core_validation import validate_file
from modules.shared.src.common.utility_dom_helper import first_visible_locator
from modules.shared.src.common.utility_logger_factory import get_logger
from modules.shared.src.prompt.contract_prompt_protocol import IUploadProtocol

log = get_logger("capabilities_file_uploader")

# ─── BE-4-001: single-evaluate DOM probes ───────────────────────────────────
#: One Chromium IPC round-trip answers "how many visible attachment cards show
#: this exact filename" across all eight (selector, expected) families. Both
#: sides of the comparison normalize identically: collapse every whitespace
#: run to a single space, trim, and lowercase — Python
#: ``" ".join(name.split()).lower()`` on the expected side, JS
#: ``text.replace(/\s+/g, ' ').trim().toLowerCase()`` on the element side, so
#: a multi-word name like ``quarterly report.md`` matches on a live page.
#: ``str.lower()`` is the deliberate counterpart of ``toLowerCase()`` (not
#: ``casefold()``): the pair keeps aggressive casefold mappings such as ß→ss
#: out of the contract, and the ASCII-shaped attachment stems Qwen renders
#: are identical under both (issue 15).
JS_ATTACHMENT_MATCH_COUNT: str = r"""
(pairs) => {
  for (const [selector, expected] of pairs) {
    let els;
    try { els = document.querySelectorAll(selector); } catch (e) { continue; }
    let matches = 0;
    for (const el of els) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;
      const text = (el.innerText || '').replace(/\s+/g, ' ').trim().toLowerCase();
      if (text === expected) matches++;
    }
    if (matches > 0) return matches;
  }
  return 0;
}
"""

#: Toast shells checked for parse-pending copy. This tuple is the single
#: source for the toast-selector argument list the readiness probe's JS
#: receives.
PARSE_TOAST_SELECTORS: tuple[str, ...] = (
    ".ant-message",
    "[role='alert']",
    "[class*='toast']",
    "[class*='message-notice']",
    "[class*='ant-notification']",
)

#: One Chromium IPC round-trip answers the whole parse-ready question
#: (toast visible? attachment card present? pending/spinner elements
#: visible? parsing keywords?). ``found=False`` means no card matched the
#: stem yet; ``ready`` mirrors the previous per-element locator scan:
#: no parse toast, no visible pending/spinner node on the last card, and
#: no "parsing"/"processing" copy in the card text.
JS_PARSE_READINESS: str = r"""
(arg) => {
  const cardSelector = arg.card_selector;
  const stem = String(arg.stem || '').toLowerCase();
  const pendingSelectors = arg.pending_selectors || [];
  const toastSelectors = arg.toast_selectors || [];
  const toastKeywords = arg.toast_keywords || [];
  const visible = (el) => {
    try {
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) return false;
      return window.getComputedStyle(el).visibility !== 'hidden';
    } catch (e) { return false; }
  };
  let toastVisible = false;
  for (const sel of toastSelectors) {
    let els;
    try { els = document.querySelectorAll(sel); } catch (e) { continue; }
    let seen = 0;
    for (const el of els) {
      if (seen >= 5) break;
      seen += 1;
      if (!visible(el)) continue;
      const txt = (el.innerText || '').toLowerCase();
      if (toastKeywords.some((kw) => txt.includes(kw))) { toastVisible = true; break; }
    }
    if (toastVisible) break;
  }
  let cards = [];
  try {
    for (const el of document.querySelectorAll(cardSelector)) {
      const txt = (el.innerText || el.textContent || '').toLowerCase();
      if (txt.includes(stem)) cards.push(el);
    }
  } catch (e) {}
  if (cards.length === 0) return {found: false, ready: false};
  const card = cards[cards.length - 1];
  const cardText = (card.innerText || '').toLowerCase();
  let pendingVisible = false;
  for (const sel of pendingSelectors) {
    let els;
    try { els = card.querySelectorAll(sel); } catch (e) { continue; }
    if (els.length > 0 && visible(els[0])) { pendingVisible = true; break; }
  }
  let spinnerVisible = false;
  try {
    const spinners = card.querySelectorAll(
      "svg[class*='spin'], svg[class*='loading'], .ant-spin, [class*='spin']");
    for (const el of spinners) {
      if (visible(el)) { spinnerVisible = true; break; }
    }
  } catch (e) {}
  const ready = !toastVisible && !pendingVisible && !spinnerVisible
    && !cardText.includes('parsing') && !cardText.includes('processing');
  return {found: true, ready: ready};
}
"""


# ─── Block 1: Class Definition & Constructor ────────────
class FileUploader(IUploadProtocol):
    """Resilient file upload with validation, retry, and DOM recovery."""

    def __init__(self, config: UploadConfig | None = None) -> None:
        if config is not None:
            self.config = config
        else:
            self.config = DEFAULT_UPLOAD_CONFIG

        self.max_size_bytes = MaxFileSizeBytes(self.config.max_size_bytes)
        self.dropdown_timeout_ms = DropdownTimeoutMs(int(self.config.dropdown_timeout_ms))
        self.option_timeout_ms = OptionTimeoutMs(int(self.config.option_timeout_ms))
        self.file_chooser_timeout_ms = FileChooserTimeoutMs(int(self.config.file_chooser_timeout_ms))
        self.card_render_timeout_ms = CardRenderTimeoutMs(int(self.config.card_render_timeout_ms))
        self.parse_ready_timeout_ms = int(self.config.parse_ready_timeout_ms)
        self.max_retries = MaxRetries(int(self.config.max_retries))
        self.backoff_delay_sec = BackoffDelaySec(float(self.config.backoff_delay_sec))

        self.dropdown_selectors = self.config.dropdown_selectors
        self.upload_option_selectors = self.config.upload_option_selectors
        self.card_selectors = self.config.card_selectors
        self.last_error: Exception | None = None

    def upload_attachment(
        self,
        page: Page,
        filepath: Path,
        emitter: LifecycleEmitter | None = None,
        web_loaded: bool = True,
    ) -> bool:
        """Upload a file as an attachment via the Qwen Web UI in 3 chronological steps:

        Step 1: Validate file pre-flight
        Step 2: Attach file via UI & wait for attachment card
        Step 3: Wait for backend network parsing & DOM parse completion
        """
        if not web_loaded:
            raise RuntimeError("Cannot upload attachment: web page loading (EVENT_WEB_LOADED) is incomplete")

        self.last_error = None

        # ── Step 1: Validate file pre-flight ──
        try:
            size_bytes = FileSizeBytes(validate_file(filepath, max_size_bytes=self.max_size_bytes))
        except FileValidationError as e:
            self.last_error = e
            log.error("Pre-flight validation failed: %s", e)
            return False

        # ── Step 2: Retry loop for attaching file to UI ──
        attempt = 0
        max_attempts = max(1, self.max_retries + 1)
        started_at = time.monotonic()

        while attempt < max_attempts:
            attempt += 1
            log.info(
                "Attempt %d/%d to upload attachment: %s (%d bytes)",
                attempt,
                max_attempts,
                filepath.name,
                size_bytes,
            )

            try:
                success = self._try_upload_attempt(page, filepath)
                if success:
                    elapsed = time.monotonic() - started_at
                    log.info(
                        "File attached successfully in %.2fs (attempt %d): %s",
                        elapsed,
                        attempt,
                        filepath.name,
                    )
                    if emitter:
                        emitter.emit(
                            EVENT_FILE_UPLOADED,
                            {"file": str(filepath), "byte_count": int(size_bytes), "attempt": attempt},
                        )
                    break
            except TimeoutError as e:
                self.last_error = e
                log.warning("Timeout during upload attempt %d/%d: %s", attempt, max_attempts, e)
                self._close_dropdown_if_open(page)
            except Error as e:
                self.last_error = e
                log.warning("Unexpected error during upload attempt %d/%d: %s", attempt, max_attempts, e)
                self._close_dropdown_if_open(page)

            if attempt < max_attempts:
                time.sleep(self.backoff_delay_sec * attempt)
        else:
            log.error(
                "All %d upload attempts failed for %s after %.2fs",
                max_attempts,
                filepath.name,
                time.monotonic() - started_at,
            )
            return False

        # ── Step 3: Wait until document backend parsing is 100% complete ──
        try:
            self._wait_for_parse_ready(page, filepath)
            page.wait_for_timeout(500)
        except TimeoutError as e:
            self.last_error = e
            log.error("Document parsing timed out for %s: %s", filepath.name, e)
            return False

        # ── Step 4: Emit EVENT_DOCUMENT_PARSED & return success ──
        if emitter:
            emitter.emit(
                EVENT_DOCUMENT_PARSED,
                {"file": str(filepath), "byte_count": int(size_bytes), "attempt": attempt},
            )
        return True

    def validate_file(self, filepath: Path, max_size_bytes: MaxFileSizeBytes | None = None) -> FileSizeBytes:
        """Public protocol method — pre-flight validation returning size in bytes."""
        limit = max_size_bytes if max_size_bytes is not None else self.max_size_bytes
        return FileSizeBytes(validate_file(filepath, max_size_bytes=limit))

    # ── Helper for Step 2: Execute single upload attempt ──
    def _try_upload_attempt(self, page: Page, filepath: Path) -> bool:
        """Execute a single attempt to attach a file via the Qwen Web UI."""
        baseline_matches = self._attachment_match_count(page, filepath)

        log.debug("Opening mode-select dropdown using primary/fallback selectors")
        dropdown_element = first_visible_locator(page, self.dropdown_selectors, timeout_ms=1000)

        if not dropdown_element:
            dropdown_element = page.locator(self.dropdown_selectors[0]).first

        dropdown_element.click(timeout=self.dropdown_timeout_ms)
        page.wait_for_timeout(500)

        log.debug("Locating upload option using resilient selector fallbacks")
        option_element = first_visible_locator(page, self.upload_option_selectors, timeout_ms=self.option_timeout_ms)

        if not option_element:
            raise TimeoutError(
                "Unable to locate a visible upload action using configured label, aria-label, or data-testid selectors"
            )

        log.debug("Triggering file chooser")
        with page.expect_file_chooser(timeout=self.file_chooser_timeout_ms) as fc:
            option_element.click()

        log.debug("Setting file on file chooser: %s", filepath.name)
        fc.value.set_files(str(filepath))

        self._wait_for_attachment_card(page, filepath, baseline_matches)
        return True

    # ── Helper for Step 2 Error Recovery: Close dropdown ──
    def _close_dropdown_if_open(self, page: Page) -> None:
        """Send Escape key to close orphaned dropdown menus on upload failure."""
        try:
            page.keyboard.press("Escape")
        except Exception as e:
            log.debug("Cleanup keypress failed (page may be closed or unnavigated): %s", e)

    # ── Helper for Step 2 DOM Verification: Attachment card render ──
    def _wait_for_attachment_card(self, page: Page, filepath: Path, baseline_matches: int = 0) -> None:
        """Wait for a newly rendered exact filename node in Qwen's live attachment DOM.

        Transient Playwright faults (navigation, a destroyed execution
        context) interrupt the poll loop instead of the whole wait: the
        poll keeps its 100ms cadence until the deadline, and only a
        deadline overrun fails the step. A wrong-shaped ``page.evaluate``
        answer is a contract violation and propagates unchanged.
        """
        log.debug("Waiting for exact Qwen attachment filename node: %s", filepath.name)
        deadline = time.monotonic() + (self.card_render_timeout_ms / 1000)
        while time.monotonic() < deadline:
            try:
                matches = self._attachment_match_count(page, filepath)
            except (TimeoutError, Error) as e:
                log.debug("Transient evaluate fault while waiting for attachment card: %s", e)
                page.wait_for_timeout(100)
                continue
            if matches > baseline_matches or (baseline_matches == 0 and matches > 0):
                return
            page.wait_for_timeout(100)
        raise TimeoutError(f"Exact uploaded filename was not rendered in Qwen attachment DOM: {filepath.name}")

    def _attachment_match_count(self, page: Page, filepath: Path) -> int:
        """Count exact filename matches across card selectors (BE-4-001).

        All eight (selector, expected) families are walked inside ONE
        ``page.evaluate``, so each ``_wait_for_attachment_card`` poll costs a
        single Chromium IPC round-trip instead of per-element
        ``count()``/``is_visible()``/``inner_text()`` trips. The evaluate is
        the authoritative path (issue 10): a live page always answers it,
        an answer of the wrong type is a contract violation and fails
        loudly, and transient evaluate failures surface as Playwright
        errors that the upload retry loop already owns.
        """
        normalized_name = " ".join(filepath.name.split()).lower()
        normalized_stem = " ".join(filepath.stem.split()).lower()
        pairs: tuple[tuple[str, str], ...] = (
            (".fileitem-file-name", normalized_name),
            ("[class*='fileitem-file-name']", normalized_name),
            (".fileitem-file-name-text", normalized_stem),
            ("[class*='fileitem-file-name-text']", normalized_stem),
            (".message-input-column-file", normalized_name),
            ("[class*='fileitem']", normalized_name),
            ("[class*='file-card']", normalized_name),
            ("[class*='file-item']", normalized_name),
        )
        count = page.evaluate(JS_ATTACHMENT_MATCH_COUNT, pairs)
        if not isinstance(count, int) or isinstance(count, bool):
            raise TypeError(
                "JS_ATTACHMENT_MATCH_COUNT must answer an int match count; "
                f"got {type(count).__name__!r} — script page.evaluate in this double"
            )
        return count

    # ── Helper for Step 3: Sequential document parse ready check ──
    def _wait_for_parse_ready(self, page: Page, filepath: Path) -> None:
        """Wait sequentially until Qwen document parsing finishes on Network API and DOM levels."""
        self._wait_for_network_parse_completion(page, filepath)
        self._wait_for_dom_parse_ready(page, filepath)

    def _wait_for_network_parse_completion(self, page: Page, filepath: Path) -> None:
        """Step 3a: Wait for backend HTTP API (/files/parse) to return 200 OK."""
        with contextlib.suppress(Exception):
            cast(Any, page).wait_for_response(lambda r: "files/parse" in r.url and r.status == 200, timeout=15000)
            log.info("Qwen backend files/parse API completed for %s", filepath.name)

    def _wait_for_dom_parse_ready(self, page: Page, filepath: Path) -> None:
        """Step 3b: Poll visual DOM attachment cards until loading spinners and toasts clear.

        BE-4-001: each poll asks ONE ``page.evaluate`` (``JS_PARSE_READINESS``)
        for the combined toast/card/pending/spinner state instead of a dozen
        locator round-trips (cadence: 200ms without a card, 300ms while not
        ready, 500ms grace after ready). Transient Playwright errors during
        the poll are swallowed here so a navigation mid-wait keeps the
        cadence; wrong-shaped answers fail loudly via ``_parse_readiness``.
        """
        deadline = time.monotonic() + (self.parse_ready_timeout_ms / 1000)
        container_selectors = (
            ".message-input-column-file",
            "[class*='fileitem-btn']",
            "[class*='file-card']",
            "[class*='file-item']",
            "[class*='fileitem']",
            "[class*='attachment']",
            "[class*='composer']",
            "[class*='input']",
        )
        card_selector = ", ".join(container_selectors)
        parse_keywords = (
            "still uploading",
            "upload to complete",
            "currently parsing",
            "parsing file",
            "wait until",
            "files still",
            "uploading",
        )

        while time.monotonic() < deadline:
            try:
                found, ready = self._parse_readiness(page, filepath, card_selector, parse_keywords)
                if ready:
                    page.wait_for_timeout(500)
                    log.debug("Qwen document parsing DOM is ready for %s", filepath.name)
                    return
                if not found:
                    page.wait_for_timeout(200)
                    continue
            except (TimeoutError, Error):
                pass
            page.wait_for_timeout(300)
        raise TimeoutError(f"Qwen document parsing did not reach ready state: {filepath.name}")

    def _parse_readiness(
        self,
        page: Page,
        filepath: Path,
        card_selector: str,
        parse_keywords: tuple[str, ...],
    ) -> tuple[bool, bool]:
        """Single-evaluate parse-readiness answer: ``(card_found, ready)``.

        The evaluate is the authoritative path (issue 10): the JS answers a
        strict ``{found, ready}`` boolean pair, and anything else is a
        contract violation that fails loudly rather than silently running a
        second implementation of the same scan.
        """
        outcome = page.evaluate(
            JS_PARSE_READINESS,
            {
                "card_selector": card_selector,
                "stem": filepath.stem,
                "pending_selectors": list(self.config.parse_pending_selectors),
                "toast_selectors": list(PARSE_TOAST_SELECTORS),
                "toast_keywords": list(parse_keywords),
            },
        )
        if not isinstance(outcome, dict):
            raise TypeError(
                "JS_PARSE_READINESS must answer {found, ready}; "
                f"got {type(outcome).__name__!r} — script page.evaluate in this double"
            )
        found = outcome.get("found")
        ready = outcome.get("ready")
        if not isinstance(found, bool) or not isinstance(ready, bool):
            raise TypeError(
                "JS_PARSE_READINESS must answer boolean found/ready fields; "
                f"got {outcome!r} — script page.evaluate in this double"
            )
        return found, ready

    def __repr__(self) -> str:
        """Return string representation of FileUploader."""
        return (
            f"FileUploader(max_size_bytes={self.max_size_bytes}, retries={self.max_retries}, "
            f"backoff={self.backoff_delay_sec})"
        )
