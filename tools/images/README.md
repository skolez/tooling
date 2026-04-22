# image-tool

Crawl, fetch, and categorize images by metadata-based parameters.

Metadata-only categorization today (fast, no ML): aspect ratio, pixel size,
file format, dominant color, grayscale detection, perceptual hash. Semantic /
content-based categorization is a planned follow-up — see "Roadmap" below.

## Install

Using [`uv`](https://docs.astral.sh/uv/) (recommended):

```bash
cd tools/images
uv sync
uv run image-tool --help
```

Using pip + venv:

```bash
cd tools/images
python -m venv .venv && source .venv/bin/activate
pip install -e .
image-tool --help
```

## Commands

### `fetch` — download images

From direct URLs:

```bash
image-tool fetch https://example.com/a.jpg https://example.com/b.png --out ./downloads
```

From a URL list file (one per line, `#` comments OK):

```bash
image-tool fetch --urls-file urls.txt --out ./downloads
```

By scraping `<img>` / `<source srcset>` from a page:

```bash
image-tool fetch --page https://example.com/gallery --out ./downloads
```

Writes files named by URL hash + extension, plus a `_fetch_report.json`
capturing per-URL status, content type, byte count, and errors.

### `categorize` — classify a local directory

```bash
image-tool categorize ./downloads --out manifest.json
```

Produces `manifest.json`:

```json
{
  "summary": {
    "total": 42,
    "errors": 0,
    "by_category": {
      "aspect": {"landscape": 30, "portrait": 10, "square": 2},
      "size":   {"medium": 25, "large": 12, "small": 5},
      "color":  {"warm": 18, "cool": 15, "grayscale": 9},
      "format": {"jpeg": 35, "png": 7}
    }
  },
  "images": [
    {
      "path": "...",
      "width": 1920, "height": 1080, "aspect_ratio": 1.7778,
      "format": "JPEG", "mode": "RGB", "file_size": 284731,
      "is_grayscale": false, "dominant_color": [120, 90, 60],
      "phash": "e1f0a3c7...",
      "categories": {"aspect": "landscape", "size": "medium",
                     "color": "warm", "format": "jpeg"}
    }
  ]
}
```

### `process` — fetch + categorize in one shot

```bash
image-tool process --page https://example.com/gallery \
  --out ./downloads --manifest ./manifest.json
```

## Categorization rules

| Category | Values |
| --- | --- |
| `aspect` | `portrait` (<0.8), `square` (0.8–1.25), `landscape` (1.25–1.9), `wide` (>1.9) |
| `size` | `thumbnail` (<0.1 MP), `small` (<0.5 MP), `medium` (<2 MP), `large` (<8 MP), `xlarge` (≥8 MP) |
| `color` | `grayscale`, `black`, `white`, `neutral`, `warm`, `green`, `cool` |
| `format` | the image format reported by Pillow (`jpeg`, `png`, `webp`, …) |

Thresholds are defined in `src/image_tool/categorize.py` and are easy to tune
or extend — each rule is a single pure function.

## Library use

Everything is importable for scripting / agent use:

```python
from pathlib import Path
from image_tool.categorize import categorize_dir, write_manifest

records = categorize_dir(Path("./downloads"))
write_manifest(records, Path("./manifest.json"))
```

## Semantic tagging (optional, CLIP-based)

Opt-in via the `[semantic]` extras — pulls in `torch` + `open_clip_torch`,
so it's gated behind an explicit install:

```bash
cd tools/images
uv sync --extra semantic            # or: pip install '.[semantic]'
```

Then pass `--semantic` to any command that produces a manifest:

```bash
image-tool categorize ./downloads --semantic --out manifest.json
image-tool categorize ./downloads --semantic --labels my_labels.txt --top-k 5
```

Each image gets a `semantic_tags: [{label, score}, ...]` list on its record
(top-K by cosine similarity) plus a `categories.semantic` field set to the
top label. Labels file format: one candidate caption per line, `#`
comments allowed, e.g.

```
a photograph
a product photo on a white background
a screenshot
a piece of text or document
...
```

The built-in default label set covers common image types (photograph,
illustration, screenshot, portrait, landscape, product photo, etc.) — see
`src/image_tool/semantic.py`.

First run downloads the CLIP weights (~350MB for ViT-B-32/openai) into the
open_clip cache. Swap models with `--model` / `--pretrained` (any open_clip
combo works, e.g. `--model ViT-L-14 --pretrained openai`).

## Roadmap

- Near-duplicate grouping based on pHash Hamming distance.
- Robots.txt + polite rate limiting for page scraping.
- Share bucketing/manifest infrastructure with the content categorizer
  under `tools/content/`.
