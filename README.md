# tooling

A collection of tools intended to be used by AI agents (e.g. Claude) or
directly by humans. Also a home for custom MCP servers that wrap APIs which
don't already have one available.

## Layout

- `tools/crawlers/` — web crawling / scraping utilities
- `tools/images/` — [`image-tool`](tools/images/README.md): fetch + categorize images (metadata + optional CLIP semantic tagging)
- `tools/content/` — [`content-tool`](tools/content/README.md): ingest + categorize text / HTML / PDF
- `tools/apis/` — helpers and clients for working with external APIs
- `mcp-servers/` — custom MCP servers; [`_template/`](mcp-servers/_template/README.md) is a starter to copy
- `shared/` — utilities shared across tools (config, logging, http clients, etc.)

Each tool or server lives in its own subdirectory with its own README and
dependency manifest so they can be developed and versioned independently.
A root `Makefile` delegates to each subproject's build system — run
`make help` for the full list of targets.

## Conventions

- Tools should be runnable standalone (CLI entrypoint or `python -m` /
  `npx` invocation).
- Tools intended for AI use should accept clear, typed inputs and return
  structured output (JSON preferred).
- MCP servers follow the spec at https://modelcontextprotocol.io and should
  document the tools/resources they expose in their own README.
