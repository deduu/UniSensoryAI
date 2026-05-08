"""Async web search tool used by policy review agents."""

from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from src.utils.config import ConfigLoader

from .models import WebSearchResult


class _DuckDuckGoHTMLResultParser(HTMLParser):
    """Extract title, URL, and snippet from DuckDuckGo HTML results."""

    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._pending_result: dict[str, str] | None = None
        self._capture_anchor = False
        self._capture_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        class_names = set(attributes.get("class", "").split())

        if tag == "a" and _is_result_anchor(attributes, class_names):
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
        title = _clean_html_text(self._pending_result.get("title", ""))
        url = _normalize_result_url(self._pending_result.get("url", ""))
        snippet = _clean_html_text(self._pending_result.get("snippet", ""))
        if title.lower() in {"next", "previous"}:
            self._pending_result = None
            return
        if title and url.startswith(("http://", "https://")):
            self.results.append({"title": title, "url": url, "snippet": snippet})
        self._pending_result = None


class _ReadableHTMLTextParser(HTMLParser):
    """Extract visible block text from an HTML page."""

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
        text = _clean_html_text(data)
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
        text = _clean_html_text(" ".join(self._current_parts))
        self._current_parts = []
        if len(text) >= 24 or (
            self._current_block_tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and len(text) >= 8
        ):
            self.segments.append(text)
        self._current_block_tag = None


def _clean_html_text(value: str) -> str:
    """Normalize a short HTML text fragment."""
    return " ".join(unescape(value).split())


def _normalize_result_url(url: str) -> str:
    """Resolve DuckDuckGo redirect URLs to the target destination."""
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


def _is_result_anchor(attributes: dict[str, str], class_names: set[str]) -> bool:
    """Return whether an anchor likely represents a search result link."""
    href = attributes.get("href", "")
    if not href:
        return False
    if class_names.intersection({"result__a", "result-link"}):
        return True

    normalized_url = _normalize_result_url(href)
    if not normalized_url.startswith(("http://", "https://")):
        return False

    parsed = urlparse(normalized_url)
    return not parsed.netloc.endswith("duckduckgo.com")


class WebSearchTool:
    """Simple async web search client backed by DuckDuckGo HTML results."""

    def __init__(
        self,
        *,
        provider: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_results: int | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        policy_config = ConfigLoader.get_policy_config()
        web_config = policy_config.get("web_search", {})
        self._provider = provider or web_config.get("provider", "duckduckgo")
        self._base_url = base_url or web_config.get(
            "base_url", "https://html.duckduckgo.com/html/"
        )
        self._lite_url = web_config.get("lite_url", "https://lite.duckduckgo.com/lite/")
        self._timeout_seconds = float(timeout_seconds or web_config.get("timeout_seconds", 10.0))
        self._max_results = int(max_results or web_config.get("max_results", 3))
        self._user_agent = web_config.get(
            "user_agent",
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
            ),
        )
        self._client = client

    async def search(
        self,
        query: str,
        *,
        max_results: int | None = None,
    ) -> list[WebSearchResult]:
        """Run a web search and return parsed result rows."""
        if self._provider.lower() != "duckduckgo":
            raise ValueError(f"Unsupported web search provider: {self._provider}")

        limit = max_results or self._max_results
        owned_client = self._client is None
        client = self._client or httpx.AsyncClient(
            follow_redirects=True,
            timeout=self._timeout_seconds,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "User-Agent": self._user_agent,
            },
        )

        try:
            return await self._search_duckduckgo(query, limit=limit, client=client)
        finally:
            if owned_client:
                await client.aclose()

    async def fetch_page_text(self, url: str, *, max_chars: int = 20000) -> str:
        """Fetch a result page and extract visible text blocks."""
        owned_client = self._client is None
        client = self._client or httpx.AsyncClient(
            follow_redirects=True,
            timeout=self._timeout_seconds,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "User-Agent": self._user_agent,
            },
        )

        try:
            response = await client.get(url)
            response.raise_for_status()
            content_type = (response.headers.get("content-type") or "").lower()
            if "pdf" in content_type or url.lower().endswith(".pdf"):
                return self.extract_pdf_text(response.content, max_chars=max_chars)
            if "html" not in content_type and response.text.lstrip()[:1] != "<":
                return ""
            return self.extract_page_text(response.text, max_chars=max_chars)
        finally:
            if owned_client:
                await client.aclose()

    async def _search_duckduckgo(
        self,
        query: str,
        *,
        limit: int,
        client: httpx.AsyncClient,
    ) -> list[WebSearchResult]:
        """Try a few DuckDuckGo request shapes before giving up."""
        attempts = [
            ("POST", self._base_url, {"data": {"q": query}}),
            ("GET", self._base_url, {"params": {"q": query}}),
            ("POST", self._lite_url, {"data": {"q": query}}),
            ("GET", self._lite_url, {"params": {"q": query}}),
        ]
        errors: list[str] = []

        for method, url, kwargs in attempts:
            try:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                results = self.parse_duckduckgo_html(response.text, limit=limit)
                if results:
                    return results
                errors.append(f"{method} {url} returned no parsable results")
            except httpx.HTTPStatusError as exc:
                errors.append(
                    f"{method} {url} returned {exc.response.status_code} {exc.response.reason_phrase}"
                )
            except httpx.HTTPError as exc:
                errors.append(f"{method} {url} failed with {exc.__class__.__name__}: {exc}")

        raise RuntimeError("DuckDuckGo search failed after fallback attempts: " + "; ".join(errors))

    @classmethod
    def parse_duckduckgo_html(cls, html: str, *, limit: int) -> list[WebSearchResult]:
        """Parse DuckDuckGo HTML response into structured results."""
        parser = _DuckDuckGoHTMLResultParser()
        parser.feed(html)
        parser.close()

        results: list[WebSearchResult] = []
        seen_urls: set[str] = set()
        for raw_result in parser.results:
            url = raw_result["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            results.append(
                WebSearchResult(
                    title=raw_result["title"],
                    url=url,
                    snippet=raw_result["snippet"],
                )
            )
            if len(results) >= limit:
                break
        return results

    @classmethod
    def extract_page_text(cls, html: str, *, max_chars: int = 20000) -> str:
        """Extract readable text blocks from an arbitrary HTML page."""
        parser = _ReadableHTMLTextParser()
        parser.feed(html)
        parser.close()

        deduped: list[str] = []
        seen: set[str] = set()
        total_chars = 0
        for segment in parser.segments:
            normalized = segment.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(segment)
            total_chars += len(segment)
            if total_chars >= max_chars:
                break
        return "\n".join(deduped)

    @classmethod
    def extract_pdf_text(cls, pdf_bytes: bytes, *, max_chars: int = 20000) -> str:
        """Extract text from a remote PDF payload."""
        try:
            import fitz
        except ImportError:
            return ""

        text_parts: list[str] = []
        total_chars = 0
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            for page in document:
                page_text = page.get_text("text")
                if not page_text:
                    continue
                cleaned = _clean_html_text(page_text.replace("\r", "\n"))
                if not cleaned:
                    continue
                text_parts.append(page_text)
                total_chars += len(page_text)
                if total_chars >= max_chars:
                    break
        finally:
            document.close()
        return "\n".join(text_parts)[:max_chars]
