# tooling

A collection of tools intended to be used by AI agents (e.g. Claude) or
directly by humans. Also a home for custom MCP servers that wrap APIs which
don't already have one available.

## Layout

- `tools/crawlers/` — web crawling / scraping utilities
- `tools/images/` — image gathering, filtering, and categorization
- `tools/apis/` — helpers and clients for working with external APIs
- `mcp-servers/` — custom MCP servers for APIs without existing ones
- `shared/` — utilities shared across tools (config, logging, http clients, etc.)

Each tool or server lives in its own subdirectory with its own README and
dependency manifest so they can be developed and versioned independently.

## Conventions

- Tools should be runnable standalone (CLI entrypoint or `python -m` /
  `npx` invocation).
- Tools intended for AI use should accept clear, typed inputs and return
  structured output (JSON preferred).
- MCP servers follow the spec at https://modelcontextprotocol.io and should
  document the tools/resources they expose in their own README.
