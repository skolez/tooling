#!/usr/bin/env python3
"""Check .com domain availability via Verisign RDAP.

Usage:
    domain_check.py foo bar baz.com
    domain_check.py --file names.txt
    echo -e "foo\nbar" | domain_check.py -
    domain_check.py --plain foo bar       # human-readable output
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Iterable

RDAP_URL = "https://rdap.verisign.com/com/v1/domain/{name}"
USER_AGENT = "domain-check/1.0 (+https://github.com/skolez/tooling)"
VALID_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")


@dataclass
class Result:
    input: str
    domain: str | None
    available: bool | None  # None = error/unknown
    status: str              # "available" | "taken" | "invalid" | "error"
    detail: str | None = None


def normalize(raw: str) -> tuple[str | None, str | None]:
    """Return (domain, error). domain is the canonical `<label>.com` or None on error."""
    s = raw.strip().lower()
    if not s:
        return None, "empty"
    # strip scheme + path if a URL was pasted
    s = re.sub(r"^[a-z]+://", "", s)
    s = s.split("/", 1)[0]
    s = s.split("?", 1)[0]
    if s.startswith("www."):
        s = s[4:]
    # accept `<label>` or `<label>.com`; reject anything else
    if "." in s:
        label, _, tld = s.rpartition(".")
        if tld != "com":
            return None, f"only .com is supported (got .{tld})"
    else:
        label = s
    if not VALID_LABEL.match(label):
        return None, "invalid label (a-z, 0-9, hyphen; 1-63 chars; no leading/trailing hyphen)"
    return f"{label}.com", None


def check(domain: str, timeout: float, retries: int = 3) -> tuple[bool | None, str, str | None]:
    """Return (available, status, detail). Retries on 429/503 with backoff."""
    req = urllib.request.Request(
        RDAP_URL.format(name=domain),
        headers={"User-Agent": USER_AGENT, "Accept": "application/rdap+json"},
    )
    last: str | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    return False, "taken", None
                return None, "error", f"unexpected status {resp.status}"
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return True, "available", None
            if e.code in (429, 503) and attempt < retries:
                time.sleep(0.5 * (2 ** attempt) + random.random() * 0.3)
                last = f"HTTP {e.code}"
                continue
            return None, "error", f"HTTP {e.code}"
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < retries:
                time.sleep(0.5 * (2 ** attempt) + random.random() * 0.3)
                last = f"network: {e}"
                continue
            return None, "error", f"network: {e}"
    return None, "error", last or "exhausted retries"


def run(inputs: Iterable[str], workers: int, timeout: float) -> list[Result]:
    normalized: list[tuple[str, str | None, str | None]] = []
    for raw in inputs:
        domain, err = normalize(raw)
        normalized.append((raw, domain, err))

    results: dict[int, Result] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for i, (raw, domain, err) in enumerate(normalized):
            if err is not None:
                results[i] = Result(input=raw, domain=None, available=None,
                                    status="invalid", detail=err)
            else:
                futures[pool.submit(check, domain, timeout)] = (i, raw, domain)
        for fut in concurrent.futures.as_completed(futures):
            i, raw, domain = futures[fut]
            available, status, detail = fut.result()
            results[i] = Result(input=raw, domain=domain, available=available,
                                status=status, detail=detail)
    return [results[i] for i in range(len(normalized))]


def read_inputs(args: argparse.Namespace) -> list[str]:
    items: list[str] = list(args.domains)
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            items.extend(line for line in (l.strip() for l in f) if line and not line.startswith("#"))
    if "-" in items:
        items = [x for x in items if x != "-"]
        items.extend(line for line in (l.strip() for l in sys.stdin) if line)
    return items


def main() -> int:
    p = argparse.ArgumentParser(description="Check .com domain availability.")
    p.add_argument("domains", nargs="*", help="Domain names (with or without .com). Use '-' to read from stdin.")
    p.add_argument("--file", help="Read domains from a file (one per line; # comments allowed).")
    p.add_argument("--plain", action="store_true", help="Human-readable output instead of JSON.")
    p.add_argument("--workers", type=int, default=4, help="Parallel requests (default: 4).")
    p.add_argument("--timeout", type=float, default=10.0, help="Per-request timeout seconds (default: 10).")
    args = p.parse_args()

    inputs = read_inputs(args)
    if not inputs:
        p.error("no domains provided (pass as args, --file, or stdin via '-')")

    results = run(inputs, workers=max(1, args.workers), timeout=args.timeout)

    if args.plain:
        width = max((len(r.domain or r.input) for r in results), default=0)
        symbol = {"available": "OK ", "taken": "-- ", "invalid": "?? ", "error": "!! "}
        for r in results:
            name = r.domain or r.input
            line = f"{symbol[r.status]}{name:<{width}}  {r.status}"
            if r.detail:
                line += f"  ({r.detail})"
            print(line)
    else:
        json.dump([asdict(r) for r in results], sys.stdout, indent=2)
        sys.stdout.write("\n")

    # Exit 0 if at least one domain was checked successfully; 2 if every check errored.
    if all(r.status == "error" for r in results):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
