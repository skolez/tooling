"""Categorize images by metadata-based bucketing rules.

Start simple and fast: no ML. Each categorizer is a pure function from
ImageMetadata to a string label. Compose them to tag an image with multiple
orthogonal categories (e.g. aspect="landscape", size="large", color="warm").
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from .metadata import ImageMetadata, extract

Categorizer = Callable[[ImageMetadata], str]

SemanticTaggerLike = Callable[[list[Path]], dict[str, list]]
"""Anything with a `tag_paths` method — see semantic.SemanticTagger."""

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".bmp", ".tiff", ".tif", ".avif", ".heic",
}


def aspect_bucket(m: ImageMetadata) -> str:
    if m.error or not m.aspect_ratio:
        return "unknown"
    r = m.aspect_ratio
    if r < 0.8:
        return "portrait"
    if r > 1.25 and r <= 1.9:
        return "landscape"
    if r > 1.9:
        return "wide"
    return "square"


def size_bucket(m: ImageMetadata) -> str:
    if m.error:
        return "unknown"
    pixels = m.width * m.height
    if pixels == 0:
        return "unknown"
    if pixels < 100_000:
        return "thumbnail"      # < ~316x316
    if pixels < 500_000:
        return "small"          # < ~707x707
    if pixels < 2_000_000:
        return "medium"         # < ~1414x1414
    if pixels < 8_000_000:
        return "large"          # < ~2828x2828
    return "xlarge"


def semantic_bucket(m: ImageMetadata) -> str:
    tags = m.semantic_tags or []
    if not tags:
        return "unknown"
    return tags[0].get("label", "unknown")


def color_bucket(m: ImageMetadata) -> str:
    if m.is_grayscale:
        return "grayscale"
    if not m.dominant_color:
        return "unknown"
    r, g, b = m.dominant_color
    mx = max(r, g, b)
    mn = min(r, g, b)
    if mx < 40:
        return "black"
    if mn > 215:
        return "white"
    if mx - mn < 20:
        return "neutral"
    # Hue-ish classification from dominant channel
    if r >= g and r >= b:
        return "warm" if r - b > 30 else "neutral"
    if g >= r and g >= b:
        return "green"
    return "cool"


def format_bucket(m: ImageMetadata) -> str:
    return (m.format or "unknown").lower()


DEFAULT_CATEGORIZERS: dict[str, Categorizer] = {
    "aspect": aspect_bucket,
    "size": size_bucket,
    "color": color_bucket,
    "format": format_bucket,
}


def iter_image_paths(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS:
            yield p


def categorize_one(
    path: Path,
    categorizers: dict[str, Categorizer] | None = None,
) -> dict:
    cats = categorizers or DEFAULT_CATEGORIZERS
    meta = extract(path)
    record = meta.to_dict()
    record["categories"] = {name: fn(meta) for name, fn in cats.items()}
    return record


def categorize_dir(
    root: Path,
    categorizers: dict[str, Categorizer] | None = None,
    workers: int = 8,
    semantic_tagger: SemanticTaggerLike | None = None,
) -> list[dict]:
    """Scan a dir (or file) and return categorized records.

    If `semantic_tagger` is provided, it runs as a batched pre-pass and its
    output is stitched into each record before bucketing — so a "semantic"
    categorizer can read them.
    """
    paths = list(iter_image_paths(root))
    results: list[dict] = []
    if not paths:
        return results

    semantic_by_path: dict[str, list[dict]] = {}
    if semantic_tagger is not None:
        raw = semantic_tagger.tag_paths(paths)  # type: ignore[attr-defined]
        for key, tags in raw.items():
            semantic_by_path[key] = [
                t.to_dict() if hasattr(t, "to_dict") else t for t in tags
            ]

    cats = categorizers or DEFAULT_CATEGORIZERS
    if semantic_by_path and "semantic" not in cats:
        cats = {**cats, "semantic": semantic_bucket}

    def _work(p: Path) -> dict:
        meta = extract(p)
        if semantic_by_path:
            meta.semantic_tags = semantic_by_path.get(str(p), [])
        record = meta.to_dict()
        record["categories"] = {name: fn(meta) for name, fn in cats.items()}
        return record

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_work, p): p for p in paths}
        for fut in as_completed(futures):
            results.append(fut.result())
    results.sort(key=lambda r: r["path"])
    return results


def summarize(records: list[dict]) -> dict:
    """Group counts per category value for a quick overview."""
    summary: dict[str, dict[str, int]] = {}
    for r in records:
        for cat_name, value in (r.get("categories") or {}).items():
            summary.setdefault(cat_name, {})
            summary[cat_name][value] = summary[cat_name].get(value, 0) + 1
    return {
        "total": len(records),
        "errors": sum(1 for r in records if r.get("error")),
        "by_category": summary,
    }


def write_manifest(records: list[dict], out_path: Path) -> None:
    payload = {"summary": summarize(records), "images": records}
    out_path.write_text(json.dumps(payload, indent=2))
