"""Optional CLIP-based semantic tagging.

Imports torch + open_clip lazily so the rest of image-tool stays usable
without the [semantic] extras installed. Usage:

    tagger = SemanticTagger.load(labels=[...])
    tags = tagger.tag_paths([Path("a.jpg"), Path("b.png")])
    # -> {"a.jpg": [("photograph", 0.42), ("landscape", 0.31), ...], ...}
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:  # pragma: no cover - type hints only
    import torch as _torch

# A general-purpose starting set. Users can override with --labels FILE.
DEFAULT_LABELS: list[str] = [
    "a photograph",
    "a digital illustration",
    "a painting",
    "a screenshot",
    "a diagram or chart",
    "a product photo on a white background",
    "a photo of people",
    "a portrait of a person",
    "a photo of an animal",
    "a landscape photo",
    "a cityscape or architecture photo",
    "an indoor scene",
    "a food photo",
    "a close-up macro photo",
    "a black and white photo",
    "a low quality or blurry photo",
    "a piece of text or document",
    "a logo or icon",
    "a meme or joke image",
    "abstract art",
]


@dataclass
class Tag:
    label: str
    score: float

    def to_dict(self) -> dict:
        return {"label": self.label, "score": round(self.score, 4)}


class SemanticTagger:
    """Lazy-initialized CLIP tagger. Build via `SemanticTagger.load(...)`."""

    def __init__(self, model, preprocess, tokenizer, text_features, labels, device):
        self._model = model
        self._preprocess = preprocess
        self._tokenizer = tokenizer
        self._text_features = text_features
        self._labels = labels
        self._device = device

    @classmethod
    def load(
        cls,
        labels: list[str] | None = None,
        model_name: str = "ViT-B-32",
        pretrained: str = "openai",
        device: str | None = None,
    ) -> "SemanticTagger":
        try:
            import open_clip
            import torch
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "Semantic tagging requires the [semantic] extras. "
                "Install with:  uv sync --extra semantic   (or  pip install '.[semantic]')"
            ) from e

        label_list = list(labels) if labels else list(DEFAULT_LABELS)
        dev = device or ("cuda" if torch.cuda.is_available() else "cpu")

        model, _, preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained=pretrained
        )
        model.eval().to(dev)
        tokenizer = open_clip.get_tokenizer(model_name)

        with torch.no_grad():
            tokens = tokenizer(label_list).to(dev)
            text_features = model.encode_text(tokens)
            text_features /= text_features.norm(dim=-1, keepdim=True)

        return cls(model, preprocess, tokenizer, text_features, label_list, dev)

    def tag_paths(
        self,
        paths: list[Path],
        top_k: int = 3,
        batch_size: int = 16,
    ) -> dict[str, list[Tag]]:
        """Return top-K tags per path (sorted by score, high to low)."""
        import torch

        results: dict[str, list[Tag]] = {}
        if not paths:
            return results

        for i in range(0, len(paths), batch_size):
            batch_paths = paths[i : i + batch_size]
            tensors = []
            kept: list[Path] = []
            for p in batch_paths:
                try:
                    with Image.open(p) as img:
                        tensors.append(self._preprocess(img.convert("RGB")))
                    kept.append(p)
                except Exception:
                    results[str(p)] = []

            if not tensors:
                continue

            batch = torch.stack(tensors).to(self._device)
            with torch.no_grad():
                img_features = self._model.encode_image(batch)
                img_features /= img_features.norm(dim=-1, keepdim=True)
                # cosine similarity -> softmax over labels
                logits = (100.0 * img_features @ self._text_features.T).softmax(dim=-1)

            for path, row in zip(kept, logits):
                scores = row.detach().cpu().tolist()
                pairs = sorted(
                    zip(self._labels, scores), key=lambda x: x[1], reverse=True
                )[:top_k]
                results[str(path)] = [Tag(label=l, score=float(s)) for l, s in pairs]

        return results


def load_labels_file(path: Path) -> list[str]:
    """Load labels from a text file (one per line, # comments allowed)."""
    lines = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines
