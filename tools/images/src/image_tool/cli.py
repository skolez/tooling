"""CLI entry point for image-tool."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .categorize import categorize_dir, summarize, write_manifest
from .fetch import fetch_page, fetch_urls

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Crawl, fetch, and categorize images by metadata.",
)
console = Console()


def _read_url_list(urls: list[str], urls_file: Path | None) -> list[str]:
    collected = list(urls)
    if urls_file:
        for line in urls_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                collected.append(line)
    seen: set[str] = set()
    unique: list[str] = []
    for u in collected:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


@app.command()
def fetch(
    urls: list[str] = typer.Argument(None, help="Direct image URLs."),
    urls_file: Path = typer.Option(None, "--urls-file", "-f", help="File with one URL per line."),
    page: str = typer.Option(None, "--page", "-p", help="Page URL to scrape for <img> tags."),
    out: Path = typer.Option(Path("./downloads"), "--out", "-o", help="Output directory."),
    workers: int = typer.Option(8, "--workers", "-w"),
    timeout: float = typer.Option(30.0, "--timeout"),
) -> None:
    """Download images from URLs or by scraping a page."""
    if page:
        found, results = fetch_page(page, out, workers=workers, timeout=timeout)
        console.print(f"[bold]{len(found)}[/bold] image URLs found on {page}")
    else:
        url_list = _read_url_list(urls or [], urls_file)
        if not url_list:
            console.print("[red]No URLs provided. Pass URLs as args, --urls-file, or --page.[/red]")
            raise typer.Exit(code=2)
        results = fetch_urls(url_list, out, workers=workers, timeout=timeout)

    ok = sum(1 for r in results if not r.error)
    failed = len(results) - ok
    total_bytes = sum(r.bytes for r in results)
    console.print(f"downloaded [green]{ok}[/green], failed [red]{failed}[/red], "
                  f"{total_bytes / 1024:.1f} KiB -> {out}")

    report = out / "_fetch_report.json"
    report.write_text(json.dumps([r.to_dict() for r in results], indent=2))
    console.print(f"report: {report}")


@app.command()
def categorize(
    path: Path = typer.Argument(..., exists=True, help="Image file or directory."),
    out: Path = typer.Option(Path("./manifest.json"), "--out", "-o"),
    workers: int = typer.Option(8, "--workers", "-w"),
    quiet: bool = typer.Option(False, "--quiet", "-q"),
) -> None:
    """Scan a directory (or single file) and emit a categorized manifest."""
    records = categorize_dir(path, workers=workers)
    if not records:
        console.print("[yellow]No images found.[/yellow]")
        raise typer.Exit(code=1)
    write_manifest(records, out)
    if not quiet:
        _print_summary(summarize(records))
    console.print(f"manifest: {out}")


@app.command()
def process(
    page: str = typer.Option(None, "--page", "-p"),
    urls: list[str] = typer.Argument(None),
    urls_file: Path = typer.Option(None, "--urls-file", "-f"),
    out: Path = typer.Option(Path("./downloads"), "--out", "-o"),
    manifest: Path = typer.Option(Path("./manifest.json"), "--manifest", "-m"),
    workers: int = typer.Option(8, "--workers", "-w"),
    timeout: float = typer.Option(30.0, "--timeout"),
) -> None:
    """Fetch then categorize in a single run."""
    if page:
        fetch_page(page, out, workers=workers, timeout=timeout)
    else:
        url_list = _read_url_list(urls or [], urls_file)
        if not url_list:
            console.print("[red]No URLs or --page provided.[/red]")
            raise typer.Exit(code=2)
        fetch_urls(url_list, out, workers=workers, timeout=timeout)

    records = categorize_dir(out, workers=workers)
    write_manifest(records, manifest)
    _print_summary(summarize(records))
    console.print(f"manifest: {manifest}")


def _print_summary(summary: dict) -> None:
    console.print(f"\n[bold]{summary['total']}[/bold] images "
                  f"([red]{summary['errors']} errors[/red])")
    for cat_name, counts in summary.get("by_category", {}).items():
        table = Table(title=cat_name, show_header=True, header_style="bold")
        table.add_column("value")
        table.add_column("count", justify="right")
        for value, count in sorted(counts.items(), key=lambda kv: -kv[1]):
            table.add_row(value, str(count))
        console.print(table)


if __name__ == "__main__":
    sys.exit(app())
