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

## Roadmap

- Semantic categorization via CLIP / a vision model (opt-in, separate command
  so we don't pull heavy deps by default).
- Near-duplicate grouping based on pHash Hamming distance.
- Robots.txt + polite rate limiting for page scraping.
- Unify with a general "content categorizer" once its shape is clearer —
  likely sharing the same bucketing/manifest infrastructure.
