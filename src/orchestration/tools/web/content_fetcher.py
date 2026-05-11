"""Fetch the body of a result URL and extract readable text.

Used by ``WebResearcherAgent`` to ground LLM synthesis on real page
content. HTML responses are stripped of script/style and reduced to
visible block text; PDF responses are extracted via PyMuPDF.
"""

from __future__ import annotations

import httpx

from src.orchestration.tools.web._html_parsers import (
    ReadableHTMLTextParser,
    clean_html_text,
)

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
)


class ContentFetcher:
    """Async fetcher that returns text content for an arbitrary URL.

    Args:
        timeout_seconds: Per-request timeout.
        user_agent: UA string to send with each request.
        client: Optional pre-built ``httpx.AsyncClient``; lifecycle is
            externally managed when supplied.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        user_agent: str = _DEFAULT_USER_AGENT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._user_agent = user_agent
        self._client = client

    async def fetch(self, url: str, *, max_chars: int = 20000) -> str:
        """Fetch ``url`` and return readable text (HTML or PDF).

        Returns an empty string for content types that are neither HTML nor
        PDF (and don't auto-detect as HTML by content sniffing).
        """
        owned = self._client is None
        client = self._client or httpx.AsyncClient(
            follow_redirects=True,
            timeout=self._timeout_seconds,
            headers=self._headers(),
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
            if owned:
                await client.aclose()

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": self._user_agent,
        }

    @classmethod
    def extract_page_text(cls, html: str, *, max_chars: int = 20000) -> str:
        """Return deduplicated, visible block text from an HTML document."""
        parser = ReadableHTMLTextParser()
        parser.feed(html)
        parser.close()

        deduped: list[str] = []
        seen: set[str] = set()
        total = 0
        for segment in parser.segments:
            normalized = segment.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(segment)
            total += len(segment)
            if total >= max_chars:
                break
        return "\n".join(deduped)

    @classmethod
    def extract_pdf_text(cls, pdf_bytes: bytes, *, max_chars: int = 20000) -> str:
        """Extract page text from a PDF payload using PyMuPDF.

        Returns an empty string if PyMuPDF is unavailable; the caller may
        choose to skip the source rather than fail the whole research run.
        """
        try:
            import fitz
        except ImportError:
            return ""

        text_parts: list[str] = []
        total = 0
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            for page in document:
                page_text = page.get_text("text")
                if not page_text:
                    continue
                if not clean_html_text(page_text.replace("\r", "\n")):
                    continue
                text_parts.append(page_text)
                total += len(page_text)
                if total >= max_chars:
                    break
        finally:
            document.close()
        return "\n".join(text_parts)[:max_chars]
