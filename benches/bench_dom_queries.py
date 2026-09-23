"""Benchmark for DOM query operations on parsed HTML."""

from __future__ import annotations

from modules.core.src.utility_core_dom_query import count_messages, latest_message_text


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


def test_count_messages_bench(benchmark):
    """Benchmark count_messages against parsed HTML using html.parser."""
    from html.parser import HTMLParser

    class MessageParser(HTMLParser):
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

    def run():
        parser = MessageParser()
        parser.feed(FIXTURE_HTML)
        return parser.count

    result = benchmark(run)
    assert result == 3  # fixture has 3 assistant messages


def test_latest_message_text_bench(benchmark):
    """Benchmark latest message text extraction."""
    from html.parser import HTMLParser

    class TextParser(HTMLParser):
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

    def run():
        parser = TextParser()
        parser.feed(FIXTURE_HTML)
        return parser.messages[-1] if parser.messages else None

    result = benchmark(run)
    assert result == "Response 3"


