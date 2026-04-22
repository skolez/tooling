"""Normalize content from files and URLs into plain text + source metadata."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

USER_AGENT = "content-tool/0.1 (+https://github.com/skolez/tooling)"

TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".rst", ".csv", ".log"}
HTML_SUFFIXES = {".html", ".htm"}
PDF_SUFFIXES = {".pdf"}

SUPPORTED_SUFFIXES = TEXT_SUFFIXES | HTML_SUFFIXES | PDF_SUFFIXES


@dataclass
class ContentDoc:
    source: str            # original path or URL
    source_kind: str       # "file" | "url"
    format: str            # "text" | "html" | "pdf"
    text: str
    char_count: int
    word_count: int
    title: str | None
    domain: str | None     # for URL sources
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


_WHITESPACE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def _html_to_text(html: str) -> tuple[str, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title_el = soup.find("title")
    title = title_el.get_text(strip=True) if title_el else None
    return _normalize(soup.get_text(" ")), title


def _pdf_to_text(path: Path) -> tuple[str, str | None]:
    from pypdf import PdfReader  # local import keeps startup fast

    reader = PdfReader(str(path))
    title = None
    if reader.metadata and reader.metadata.title:
        title = str(reader.metadata.title)
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return _normalize(" ".join(parts)), title


def _build_doc(
    source: str,
    source_kind: str,
    fmt: str,
    text: str,
    title: str | None,
    domain: str | None,
    error: str | None = None,
) -> ContentDoc:
    return ContentDoc(
        source=source,
        source_kind=source_kind,
        format=fmt,
        text=text,
        char_count=len(text),
        word_count=len(text.split()) if text else 0,
        title=title,
        domain=domain,
        error=error,
    )


def ingest_file(path: Path) -> ContentDoc:
    suffix = path.suffix.lower()
    try:
        if suffix in HTML_SUFFIXES:
            text, title = _html_to_text(path.read_text(errors="replace"))
            return _build_doc(str(path), "file", "html", text, title, None)
        if suffix in PDF_SUFFIXES:
            text, title = _pdf_to_text(path)
            return _build_doc(str(path), "file", "pdf", text, title, None)
        if suffix in TEXT_SUFFIXES or suffix == "":
            text = path.read_text(errors="replace")
            return _build_doc(str(path), "file", "text", _normalize(text), None, None)
        return _build_doc(
            str(path), "file", "unknown", "", None, None,
            error=f"unsupported extension: {suffix}",
        )
    except Exception as e:
        return _build_doc(str(path), "file", "unknown", "", None, None,
                          error=f"{type(e).__name__}: {e}")


def ingest_url(url: str, timeout: float = 30.0) -> ContentDoc:
    domain = urlparse(url).netloc or None
    try:
        with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=timeout) as c:
            resp = c.get(url, follow_redirects=True)
            resp.raise_for_status()
        ct = resp.headers.get("content-type", "").lower()
        body = resp.text
        if "html" in ct or body.lstrip().lower().startswith("<!doctype html"):
            text, title = _html_to_text(body)
            return _build_doc(url, "url", "html", text, title, domain)
        return _build_doc(url, "url", "text", _normalize(body), None, domain)
    except Exception as e:
        return _build_doc(url, "url", "unknown", "", None, domain,
                          error=f"{type(e).__name__}: {e}")


def iter_content_paths(root: Path):
    if root.is_file():
        yield root
        return
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES:
            yield p
