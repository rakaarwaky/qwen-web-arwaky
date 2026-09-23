"""Benchmark for DOM query operations on parsed HTML.

Uses time.perf_counter for measuring performance without requiring pytest-benchmark plugin.
"""

from __future__ import annotations

import time
from html.parser import HTMLParser


# Simple inline HTML fixture with 3 assistant messages
FIXTURE_HTML = """
<div id="chatLog">
  <div class="message assistant">
    <div class="markdown-body">Response 1</div>
  </div>
  <div class="message assistant">
    <div class="markdown-body">Response 2</div>
  </div>
  <div class="message assistant">
    <div class="markdown-body">Response 3</div>
  </div>
</div>
"""


class MessageParser(HTMLParser):
    """Parser that counts assistant messages."""

    def __init__(self):
        super().__init__()
        self.count = 0
        self.in_markdown_body = False

    def handle_starttag(self, tag, attrs):
        if tag == "div":
            attr_dict = dict(attrs)
            classes = attr_dict.get("class", "").split()
            if "message" in classes and "assistant" in classes:
                self.in_markdown_body = True
                self.count += 1
            elif "markdown-body" in classes and self.in_markdown_body:
                self.in_markdown_body = False


class TextParser(HTMLParser):
    """Parser that extracts latest message text."""

    def __init__(self):
        super().__init__()
        self.messages = []
        self.current_message = None
        self.in_body = False
        self.text_buffer = []

    def handle_starttag(self, tag, attrs):
        if tag == "div":
            attr_dict = dict(attrs)
            classes = attr_dict.get("class", "").split()
            if "message" in classes and "assistant" in classes:
                self.current_message = ""
            elif "markdown-body" in classes and self.current_message is not None:
                self.in_body = True
                self.text_buffer = []

    def handle_endtag(self, tag):
        if tag == "div" and self.in_body:
            self.in_body = False
            if self.current_message is not None:
                self.messages.append("".join(self.text_buffer))
                self.current_message = None

    def handle_data(self, data):
        if self.in_body:
            self.text_buffer.append(data)


def bench_count_messages(iterations: int = 1000) -> float:
    """Benchmark message counting performance."""
    start = time.perf_counter()
    for _ in range(iterations):
        parser = MessageParser()
        parser.feed(FIXTURE_HTML)
        _ = parser.count
    elapsed = time.perf_counter() - start
    return elapsed / iterations * 1_000_000  # microseconds per call


def bench_latest_message_text(iterations: int = 1000) -> float:
    """Benchmark text extraction performance."""
    start = time.perf_counter()
    for _ in range(iterations):
        parser = TextParser()
        parser.feed(FIXTURE_HTML)
        _ = parser.messages[-1] if parser.messages else None
    elapsed = time.perf_counter() - start
    return elapsed / iterations * 1_000_000  # microseconds per call


def test_bench_count_messages():
    """Report benchmark results for count_messages."""
    micros = bench_count_messages()
    print(f"\n[BENCHMARK] count_messages: {micros:.2f} µs/call")
    assert micros > 0  # Sanity check


def test_bench_latest_message_text():
    """Report benchmark results for latest_message_text."""
    micros = bench_latest_message_text()
    print(f"\n[BENCHMARK] latest_message_text: {micros:.2f} µs/call")
    assert micros > 0  # Sanity check
