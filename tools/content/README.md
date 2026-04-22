# content-tool

Ingest and categorize text / HTML / PDF content. Sibling to `image-tool` —
same manifest shape (`{summary, items}`), same "categorizers are pure
functions" design, different domain.

## Supported inputs

- Plain text: `.txt`, `.md`, `.markdown`, `.rst`, `.csv`, `.log`, extension-less
- HTML: `.html`, `.htm` (text extracted, `<script>`/`<style>` stripped)
- PDF: `.pdf` (text layer via `pypdf`; OCR is out of scope for v1)
- URLs: `http(s)://…` — fetched, HTML-aware

## Install

```bash
cd tools/content
uv sync
uv run content-tool --help
```

## Commands

### `ingest` — normalize one or more inputs

```bash
content-tool ingest ./article.pdf https://example.com/post
content-tool ingest ./corpus/ --out docs.json
```

Emits per-doc records with `source`, `source_kind` (file/url), `format`
(text/html/pdf), normalized `text`, `char_count`, `word_count`, `title`
(HTML/PDF), and `domain` (URL).

### `categorize` — scan a file/dir and emit a manifest

```bash
content-tool categorize ./corpus --out content-manifest.json
```

Default categories:

| Category | Values |
| --- | --- |
| `length` | `empty`, `tiny` (<280 ch), `short` (<2k), `medium` (<10k), `long` (<50k), `very_long` (≥50k) |
| `language` | ISO-639-1 code from `langdetect` (`en`, `fr`, …) or `unknown` |
| `format` | `text`, `html`, `pdf`, `unknown` |
| `source` | `file`, `url`, `unknown` |

Manifests drop the full text (kept as a 280-char `text_preview` instead) to
stay manageable for large corpora.

## Optional semantic tagging

Opt-in via the `[semantic]` extras — uses `sentence-transformers` with
MiniLM by default (~80 MB model, much smaller than CLIP):

```bash
uv sync --extra semantic
content-tool categorize ./corpus --semantic --out content-manifest.json
content-tool categorize ./corpus --semantic --labels labels.txt --top-k 5
```

Each record gains `semantic_tags: [{label, score}, ...]` and a
`categories.semantic` field set to the top label. The built-in label set
covers common document archetypes (news, blog, docs, code, paper, legal,
etc.) — override with `--labels FILE` (one candidate label per line).

## Relationship to image-tool

Both tools emit manifests shaped like `{summary, items | images}`, both
expose categorizers as pure functions keyed by category name, and both
gate semantic tagging behind a `[semantic]` extras group. A future combined
"content categorizer" that handles mixed corpora can route inputs to the
right tool and merge manifests by source path.
