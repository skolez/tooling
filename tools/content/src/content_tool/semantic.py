"""Optional text semantic tagging via sentence-transformers.

Loads lazily so the tool stays usable without the [semantic] extras.
Uses cosine similarity between doc embedding and candidate label embeddings,
consistent with the image-tool CLIP approach — different model, same shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .ingest import ContentDoc

DEFAULT_LABELS: list[str] = [
    "a news article",
    "a blog post or opinion piece",
    "technical documentation",
    "source code",
    "a research paper or academic text",
    "a product description or marketing copy",
    "a legal or policy document",
    "a financial report",
    "a how-to guide or tutorial",
    "a personal note or journal entry",
    "a conversation or chat log",
    "a list or index",
    "an email",
    "a FAQ or Q&A",
    "a changelog or release notes",
]

MAX_CHARS = 4000  # truncate long docs before embedding for speed


@dataclass
class Tag:
    label: str
    score: float

    def to_dict(self) -> dict:
        return {"label": self.label, "score": round(self.score, 4)}


class SemanticTagger:
    def __init__(self, model, label_embeddings, labels):
        self._model = model
        self._label_embeddings = label_embeddings
        self._labels = labels

    @classmethod
    def load(
        cls,
        labels: list[str] | None = None,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> "SemanticTagger":
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "Semantic tagging requires the [semantic] extras. "
                "Install with:  uv sync --extra semantic   "
                "(or  pip install '.[semantic]')"
            ) from e

        label_list = list(labels) if labels else list(DEFAULT_LABELS)
        model = SentenceTransformer(model_name)
        label_embeddings = model.encode(
            label_list, normalize_embeddings=True, convert_to_numpy=True
        )
        return cls(model, label_embeddings, label_list)

    def tag_docs(self, docs: list[ContentDoc], top_k: int = 3) -> dict[str, list[Tag]]:
        usable = [d for d in docs if d.text and not d.error]
        if not usable:
            return {d.source: [] for d in docs}

        texts = [d.text[:MAX_CHARS] for d in usable]
        emb = self._model.encode(
            texts, normalize_embeddings=True, convert_to_numpy=True, batch_size=32
        )
        sims = emb @ self._label_embeddings.T  # (N, L)

        out: dict[str, list[Tag]] = {}
        for d, row in zip(usable, sims):
            pairs = sorted(zip(self._labels, row.tolist()), key=lambda x: x[1], reverse=True)
            out[d.source] = [Tag(label=l, score=float(s)) for l, s in pairs[:top_k]]
        for d in docs:
            out.setdefault(d.source, [])
        return out


def load_labels_file(path: Path) -> list[str]:
    lines = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines
