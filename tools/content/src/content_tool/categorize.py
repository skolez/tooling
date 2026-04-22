"""Categorize content docs. Mirrors the image-tool manifest shape."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from langdetect import DetectorFactory, detect

from .ingest import ContentDoc, ingest_file, iter_content_paths

DetectorFactory.seed = 0  # deterministic langdetect results

Categorizer = Callable[[ContentDoc], str]

SemanticTaggerLike = Callable[[list[ContentDoc]], dict[str, list]]


def length_bucket(d: ContentDoc) -> str:
    if d.error or not d.char_count:
        return "empty"
    c = d.char_count
    if c < 280:
        return "tiny"           # tweet-length
    if c < 2_000:
        return "short"          # quick blog post
    if c < 10_000:
        return "medium"         # full article
    if c < 50_000:
        return "long"           # essay / chapter
    return "very_long"


def language_bucket(d: ContentDoc) -> str:
    if d.error or not d.text or d.word_count < 5:
        return "unknown"
    try:
        return detect(d.text[:2000])
    except Exception:
        return "unknown"


def format_bucket(d: ContentDoc) -> str:
    return d.format or "unknown"


def source_bucket(d: ContentDoc) -> str:
    return d.source_kind or "unknown"


def semantic_bucket(d: ContentDoc) -> str:
    tags = getattr(d, "_semantic_tags", None) or []
    if not tags:
        return "unknown"
    top = tags[0]
    return top.get("label") if isinstance(top, dict) else str(top)


DEFAULT_CATEGORIZERS: dict[str, Categorizer] = {
    "length": length_bucket,
    "language": language_bucket,
    "format": format_bucket,
    "source": source_bucket,
}


def categorize_one(
    doc: ContentDoc,
    categorizers: dict[str, Categorizer] | None = None,
) -> dict:
    cats = categorizers or DEFAULT_CATEGORIZERS
    record = doc.to_dict()
    record["categories"] = {name: fn(doc) for name, fn in cats.items()}
    # Avoid bloating manifests with full document text; keep a preview.
    if "text" in record and record["text"]:
        record["text_preview"] = record["text"][:280]
        del record["text"]
    return record


def categorize_dir(
    root: Path,
    categorizers: dict[str, Categorizer] | None = None,
    workers: int = 8,
    semantic_tagger: SemanticTaggerLike | None = None,
) -> list[dict]:
    paths = list(iter_content_paths(root))
    if not paths:
        return []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        docs = list(pool.map(ingest_file, paths))

    if semantic_tagger is not None:
        tags_by_source = semantic_tagger.tag_docs(docs)  # type: ignore[attr-defined]
        for doc in docs:
            raw = tags_by_source.get(doc.source, [])
            doc._semantic_tags = [  # type: ignore[attr-defined]
                t.to_dict() if hasattr(t, "to_dict") else t for t in raw
            ]

    cats = dict(categorizers or DEFAULT_CATEGORIZERS)
    if semantic_tagger is not None and "semantic" not in cats:
        cats["semantic"] = semantic_bucket

    records = [categorize_one(d, cats) for d in docs]
    if semantic_tagger is not None:
        sem_map = {d.source: getattr(d, "_semantic_tags", []) for d in docs}
        for r in records:
            r["semantic_tags"] = sem_map.get(r["source"], [])
    records.sort(key=lambda r: r["source"])
    return records


def summarize(records: list[dict]) -> dict:
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
    payload = {"summary": summarize(records), "items": records}
    out_path.write_text(json.dumps(payload, indent=2))
