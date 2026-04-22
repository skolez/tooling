"""Fetch images from direct URLs or by scraping <img> tags from a page."""

from __future__ import annotations

import hashlib
import mimetypes
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

USER_AGENT = "image-tool/0.1 (+https://github.com/skolez/tooling)"

EXT_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/avif": ".avif",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
    "image/svg+xml": ".svg",
}


@dataclass
class FetchResult:
    url: str
    path: str | None
    status: int | None
    content_type: str | None
    bytes: int
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _ext_from_url(url: str) -> str | None:
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix else None


def _ext_from_content_type(ct: str | None) -> str | None:
    if not ct:
        return None
    base = ct.split(";", 1)[0].strip().lower()
    return EXT_BY_CONTENT_TYPE.get(base) or mimetypes.guess_extension(base)


def _target_path(url: str, content_type: str | None, out_dir: Path) -> Path:
    digest = hashlib.sha1(url.encode()).hexdigest()[:16]
    ext = _ext_from_url(url) or _ext_from_content_type(content_type) or ".bin"
    return out_dir / f"{digest}{ext}"


def extract_image_urls(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    urls: list[str] = []
    for tag in soup.find_all(["img", "source"]):
        candidates: list[str] = []
        for attr in ("src", "data-src", "data-original"):
            v = tag.get(attr)
            if v:
                candidates.append(v)
        srcset = tag.get("srcset")
        if srcset:
            for part in srcset.split(","):
                u = part.strip().split(" ", 1)[0]
                if u:
                    candidates.append(u)
        for u in candidates:
            absu = urljoin(base_url, u)
            if absu.startswith(("http://", "https://")) and absu not in seen:
                seen.add(absu)
                urls.append(absu)
    return urls


def scrape_page(url: str, client: httpx.Client) -> list[str]:
    resp = client.get(url, follow_redirects=True)
    resp.raise_for_status()
    return extract_image_urls(resp.text, str(resp.url))


def download_one(url: str, out_dir: Path, client: httpx.Client) -> FetchResult:
    try:
        with client.stream("GET", url, follow_redirects=True) as resp:
            content_type = resp.headers.get("content-type")
            if resp.status_code >= 400:
                return FetchResult(url, None, resp.status_code, content_type, 0,
                                   error=f"HTTP {resp.status_code}")
            target = _target_path(url, content_type, out_dir)
            total = 0
            with target.open("wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
                    total += len(chunk)
            return FetchResult(url, str(target), resp.status_code, content_type, total)
    except Exception as e:
        return FetchResult(url, None, None, None, 0, error=f"{type(e).__name__}: {e}")


def fetch_urls(
    urls: list[str],
    out_dir: Path,
    workers: int = 8,
    timeout: float = 30.0,
) -> list[FetchResult]:
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[FetchResult] = []
    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    ) as client:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(download_one, u, out_dir, client): u for u in urls}
            for fut in as_completed(futures):
                results.append(fut.result())
    return results


def fetch_page(
    page_url: str,
    out_dir: Path,
    workers: int = 8,
    timeout: float = 30.0,
) -> tuple[list[str], list[FetchResult]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    ) as client:
        urls = scrape_page(page_url, client)
    results = fetch_urls(urls, out_dir, workers=workers, timeout=timeout)
    return urls, results
