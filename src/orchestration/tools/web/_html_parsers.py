"""HTML parsing helpers shared across web tools.

The DuckDuckGo result parser and the readable-text parser were lifted from
``src.policy.web_search`` so the new orchestration providers and the
existing policy code share a single, well-tested implementation.
"""

from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlparse


def clean_html_text(value: str) -> str:
    """Decode entities and collapse whitespace in a short HTML fragment."""
    return " ".join(unescape(value).split())


def normalize_result_url(url: str) -> str:
    """Resolve DuckDuckGo redirect URLs to the underlying target."""
    if url.startswith("//"):
        url = f"https:{url}"
    if url.startswith("/"):
        url = f"https://duckduckgo.com{url}"

    parsed = urlparse(url)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        params = parse_qs(parsed.query)
        targets = params.get("uddg", [])
        if targets:
            return unquote(targets[0])
    return url


def is_result_anchor(attributes: dict[str, str], class_names: set[str]) -> bool:
    """Heuristic: does this anchor represent a real search result link?"""
    href = attributes.get("href", "")
    if not href:
        return False
    if class_names.intersection({"result__a", "result-link"}):
        return True

    normalized_url = normalize_result_url(href)
    if not normalized_url.startswith(("http://", "https://")):
        return False

    parsed = urlparse(normalized_url)
    return not parsed.netloc.endswith("duckduckgo.com")


class DuckDuckGoHTMLResultParser(HTMLParser):
    """Extract title / URL / snippet triples from DuckDuckGo HTML output."""

    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._pending_result: dict[str, str] | None = None
        self._capture_anchor = False
        self._capture_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        class_names = set(attributes.get("class", "").split())

        if tag == "a" and is_result_anchor(attributes, class_names):
            self._flush_pending()
            self._pending_result = {
                "title": "",
                "url": attributes.get("href", ""),
                "snippet": "",
            }
            self._capture_anchor = True
            return

        if class_names.intersection({"result__snippet", "result-snippet"}):
            if self._pending_result is None:
                self._pending_result = {"title": "", "url": "", "snippet": ""}
            self._capture_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capture_anchor:
            self._capture_anchor = False
        if tag in {"a", "div", "span"} and self._capture_snippet:
            self._capture_snippet = False

    def handle_data(self, data: str) -> None:
        if self._pending_result is None:
            return
        if self._capture_anchor:
            self._pending_result["title"] += data
        if self._capture_snippet:
            self._pending_result["snippet"] += data

    def close(self) -> None:
        super().close()
        self._flush_pending()

    def _flush_pending(self) -> None:
        if self._pending_result is None:
            return
        title = clean_html_text(self._pending_result.get("title", ""))
        url = normalize_result_url(self._pending_result.get("url", ""))
        snippet = clean_html_text(self._pending_result.get("snippet", ""))
        if title.lower() in {"next", "previous"}:
            self._pending_result = None
            return
        if title and url.startswith(("http://", "https://")):
            self.results.append({"title": title, "url": url, "snippet": snippet})
        self._pending_result = None


class ReadableHTMLTextParser(HTMLParser):
    """Extract visible block text from an arbitrary HTML document."""

    _BLOCK_TAGS = {
        "article",
        "blockquote",
        "dd",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "p",
        "section",
        "td",
        "th",
    }
    _SKIP_TAGS = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__()
        self.segments: list[str] = []
        self._skip_depth = 0
        self._current_parts: list[str] = []
        self._current_block_tag: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag in self._BLOCK_TAGS:
            self._flush()
            self._current_block_tag = tag

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag in self._BLOCK_TAGS:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = clean_html_text(data)
        if not text:
            return
        self._current_parts.append(text)

    def close(self) -> None:
        super().close()
        self._flush()

    def _flush(self) -> None:
        if not self._current_parts:
            self._current_block_tag = None
            return
        text = clean_html_text(" ".join(self._current_parts))
        self._current_parts = []
        if len(text) >= 24 or (
            self._current_block_tag in {"h1", "h2", "h3", "h4", "h5", "h6"}
            and len(text) >= 8
        ):
            self.segments.append(text)
        self._current_block_tag = None


def strip_html_tags(value: str) -> str:
    """Remove HTML tags and decode entities — used for provider snippets."""

    class _Stripper(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.parts: list[str] = []

        def handle_data(self, data: str) -> None:
            self.parts.append(data)

    stripper = _Stripper()
    stripper.feed(value)
    stripper.close()
    return clean_html_text("".join(stripper.parts))
