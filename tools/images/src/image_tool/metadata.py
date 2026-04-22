"""Extract structured metadata from image files."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import imagehash
from PIL import Image, ImageStat


@dataclass
class ImageMetadata:
    path: str
    format: str | None
    mode: str | None
    width: int
    height: int
    aspect_ratio: float
    file_size: int
    is_animated: bool
    is_grayscale: bool
    dominant_color: tuple[int, int, int] | None
    phash: str
    error: str | None = None
    semantic_tags: list[dict] | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _dominant_color(img: Image.Image) -> tuple[int, int, int] | None:
    """Cheap dominant color via palette quantization."""
    try:
        small = img.convert("RGB").resize((64, 64))
        quantized = small.quantize(colors=5, method=Image.Quantize.FASTOCTREE)
        palette = quantized.getpalette() or []
        counts = sorted(quantized.getcolors() or [], reverse=True)
        if not counts or not palette:
            return None
        idx = counts[0][1]
        r, g, b = palette[idx * 3 : idx * 3 + 3]
        return (int(r), int(g), int(b))
    except Exception:
        return None


def _is_grayscale(img: Image.Image) -> bool:
    if img.mode in ("L", "LA", "1"):
        return True
    try:
        rgb = img.convert("RGB")
        stat = ImageStat.Stat(rgb)
        r, g, b = stat.mean
        return max(abs(r - g), abs(g - b), abs(r - b)) < 2.0
    except Exception:
        return False


def extract(path: Path) -> ImageMetadata:
    """Extract metadata for a single image file. Never raises."""
    try:
        file_size = path.stat().st_size
    except OSError as e:
        return _error_record(path, f"stat failed: {e}")

    try:
        with Image.open(path) as img:
            img.load()
            width, height = img.size
            aspect = width / height if height else 0.0
            return ImageMetadata(
                path=str(path),
                format=img.format,
                mode=img.mode,
                width=width,
                height=height,
                aspect_ratio=round(aspect, 4),
                file_size=file_size,
                is_animated=bool(getattr(img, "is_animated", False)),
                is_grayscale=_is_grayscale(img),
                dominant_color=_dominant_color(img),
                phash=str(imagehash.phash(img.convert("RGB"))),
            )
    except Exception as e:
        return _error_record(path, f"{type(e).__name__}: {e}", file_size=file_size)


def _error_record(path: Path, msg: str, file_size: int = 0) -> ImageMetadata:
    return ImageMetadata(
        path=str(path),
        format=None,
        mode=None,
        width=0,
        height=0,
        aspect_ratio=0.0,
        file_size=file_size,
        is_animated=False,
        is_grayscale=False,
        dominant_color=None,
        phash="",
        error=msg,
    )
