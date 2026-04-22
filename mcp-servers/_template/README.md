# mcp-server-template

Starter template for a custom MCP server. Copy this directory, rename it,
and replace the example `echo` tool and `server-info` resource with the
real API surface you want to expose.

Uses the official [`@modelcontextprotocol/sdk`](https://modelcontextprotocol.io)
over stdio transport — the shape Claude Code and Claude Desktop expect for
locally-installed servers.

## Quick start

```bash
cd mcp-servers/_template
npm install
npm run build
npm start                  # runs the compiled server on stdio
```

During development, run `npm run dev` in one terminal (watches + rebuilds)
and have your MCP client spawn `node dist/index.js` (or `npm start`) from
another.

## Creating a new server from this template

```bash
cp -r mcp-servers/_template mcp-servers/my-api
cd mcp-servers/my-api
# edit package.json: change "name" and "bin"
# edit src/index.ts: replace tools/resources with your API
npm install
npm run build
```

Then add it to the root Makefile's `MCP_SUBPROJECTS` list for unified
`make my-api-install`, `make my-api-build`, `make my-api-run` targets.

## Anatomy

- `src/index.ts` — server entry. Registers tools + resources, connects
  stdio transport. This is the only file most servers need to touch.
- `package.json` — sets `"type": "module"` (SDK is ESM) and a `bin` entry
  so the server can be installed globally as a CLI if desired.
- `tsconfig.json` — NodeNext module resolution, ES2022 target, strict.

## Adding a tool

Tools are actions the model can invoke. Inputs are validated with zod:

```ts
server.registerTool(
  "search_widgets",
  {
    title: "Search Widgets",
    description: "Search the Widget API for matching items.",
    inputSchema: {
      query: z.string().describe("Free-text query."),
      limit: z.number().int().min(1).max(50).default(10),
    },
  },
  async ({ query, limit }) => {
    const res = await fetch(`https://api.example.com/widgets?q=${encodeURIComponent(query)}&limit=${limit}`);
    const data = await res.json();
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  },
);
```

## Adding a resource

Resources expose read-only context (docs, config, cached data):

```ts
server.registerResource(
  "widget-schema",
  "widgets://schema",
  {
    title: "Widget Schema",
    description: "JSON schema for the Widget API response shape.",
    mimeType: "application/json",
  },
  async (uri) => ({
    contents: [{ uri: uri.href, mimeType: "application/json", text: schemaJson }],
  }),
);
```

## Wiring into Claude Code

Add to your Claude Code `settings.json` (user or project):

```json
{
  "mcpServers": {
    "template": {
      "command": "node",
      "args": ["/absolute/path/to/mcp-servers/_template/dist/index.js"]
    }
  }
}
```

Or for a server that reads secrets from env:

```json
{
  "mcpServers": {
    "my-api": {
      "command": "node",
      "args": ["/absolute/path/to/mcp-servers/my-api/dist/index.js"],
      "env": {
        "MY_API_KEY": "sk-..."
      }
    }
  }
}
```

## Wiring into Claude Desktop

Same block in `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) or `%APPDATA%/Claude/claude_desktop_config.json` (Windows).

## Testing without a real client

The easiest smoke test is `npm start` and pasting JSON-RPC messages on
stdin. The MCP Inspector (`npx @modelcontextprotocol/inspector node dist/index.js`)
gives a richer UI for listing tools/resources and invoking them.
