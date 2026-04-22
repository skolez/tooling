#!/usr/bin/env node
/**
 * MCP server template.
 *
 * Copy this directory, rename the package, and replace the example tool /
 * resource below with the real API surface you want to expose. Everything
 * here uses stdio transport, which is what Claude Code and Claude Desktop
 * expect for locally-installed MCP servers.
 *
 * Spec: https://modelcontextprotocol.io
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({
  name: "mcp-server-template",
  version: "0.1.0",
});

// -------- Example tool --------
// Tools are how the model performs actions. Inputs are validated with zod.
// Replace this echo tool with your real API calls (httpx, fetch, SDK, …).
server.registerTool(
  "echo",
  {
    title: "Echo",
    description: "Return the provided text. Replace with a real tool.",
    inputSchema: {
      text: z.string().describe("Any string to echo back."),
    },
  },
  async ({ text }) => ({
    content: [{ type: "text", text }],
  }),
);

// -------- Example resource --------
// Resources expose read-only data the model (or user) can pull in as context.
// Replace with something meaningful — e.g. a config dump, a cached report,
// a list of available API endpoints, etc.
server.registerResource(
  "server-info",
  "template://info",
  {
    title: "Server Info",
    description: "Static metadata about this template server.",
    mimeType: "application/json",
  },
  async (uri) => ({
    contents: [
      {
        uri: uri.href,
        mimeType: "application/json",
        text: JSON.stringify(
          { name: "mcp-server-template", version: "0.1.0" },
          null,
          2,
        ),
      },
    ],
  }),
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error("mcp-server-template failed:", err);
  process.exit(1);
});
