# mcp-servers

Custom MCP (Model Context Protocol) servers for APIs that don't already
have one available.

Each server is a self-contained project in its own subdirectory with:
- Its own dependency manifest (`package.json`, `pyproject.toml`, etc.)
- A README documenting the tools, resources, and prompts it exposes
- Install / run instructions (including any required env vars)
- An example client config snippet for Claude Code / Claude Desktop

Spec reference: https://modelcontextprotocol.io
