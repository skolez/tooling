"""CLI entry point for content-tool."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .categorize import categorize_dir, summarize, write_manifest
from .ingest import ingest_file, ingest_url

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Ingest and categorize text/HTML/PDF content.",
)
console = Console()


@app.command()
def ingest(
    targets: list[str] = typer.Argument(..., help="File paths or URLs."),
    out: Path = typer.Option(None, "--out", "-o", help="Write JSON to this path."),
) -> None:
    """Ingest one or more files/URLs and print (or write) normalized docs."""
    docs = []
    for t in targets:
        if t.startswith(("http://", "https://")):
            docs.append(ingest_url(t).to_dict())
        else:
            docs.append(ingest_file(Path(t)).to_dict())
    if out:
        out.write_text(json.dumps(docs, indent=2))
        console.print(f"wrote {len(docs)} docs -> {out}")
    else:
        console.print(json.dumps(docs, indent=2))


@app.command()
def categorize(
    path: Path = typer.Argument(..., exists=True, help="File or directory."),
    out: Path = typer.Option(Path("./content-manifest.json"), "--out", "-o"),
    workers: int = typer.Option(8, "--workers", "-w"),
    quiet: bool = typer.Option(False, "--quiet", "-q"),
    semantic: bool = typer.Option(
        False, "--semantic",
        help="Enable embedding-based semantic tagging. Requires [semantic] extras.",
    ),
    labels_file: Path = typer.Option(None, "--labels"),
    top_k: int = typer.Option(3, "--top-k"),
    model: str = typer.Option("sentence-transformers/all-MiniLM-L6-v2", "--model"),
) -> None:
    """Scan a file/dir and emit a categorized manifest."""
    tagger = _build_tagger(semantic, labels_file, top_k, model)
    records = categorize_dir(path, workers=workers, semantic_tagger=tagger)
    if not records:
        console.print("[yellow]No supported content files found.[/yellow]")
        raise typer.Exit(code=1)
    write_manifest(records, out)
    if not quiet:
        _print_summary(summarize(records))
    console.print(f"manifest: {out}")


def _build_tagger(semantic: bool, labels_file: Path | None, top_k: int, model: str):
    if not semantic:
        return None
    from .semantic import SemanticTagger, load_labels_file

    labels = load_labels_file(labels_file) if labels_file else None
    console.print(f"[cyan]loading embedding model {model}…[/cyan]")
    base = SemanticTagger.load(labels=labels, model_name=model)

    class _WithTopK:
        def tag_docs(self, docs):
            return base.tag_docs(docs, top_k=top_k)

    return _WithTopK()


def _print_summary(summary: dict) -> None:
    console.print(f"\n[bold]{summary['total']}[/bold] items "
                  f"([red]{summary['errors']} errors[/red])")
    for cat_name, counts in summary.get("by_category", {}).items():
        table = Table(title=cat_name, show_header=True, header_style="bold")
        table.add_column("value")
        table.add_column("count", justify="right")
        for value, count in sorted(counts.items(), key=lambda kv: -kv[1]):
            table.add_row(value, str(count))
        console.print(table)


if __name__ == "__main__":
    app()
