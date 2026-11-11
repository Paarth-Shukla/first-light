---
id: api-mcp-connector
title: MCP connector
surface: platform
group: Tools
status: beta
level: power
payoff: 3
effort: 2
jobs: [automation, planning]
tags: [mcp, connectors, remote-tools, beta]
summary: The MCP connector lets a Messages API request connect to remote MCP servers and call their tools directly, without you writing an MCP client.
when: Reach for it when a remote MCP server already exposes the system you need, such as an issue tracker or a calendar, and you want its tools in a script. If you only need one internal function, define a client tool instead.
replaces: Writing and hosting your own MCP client, or wrapping each service API as a hand-made tool.
example_kind: command
docs:
  - title: MCP connector
    url: https://platform.claude.com/docs/en/agents-and-tools/mcp-connector
verified: 2026-11-11
---
## Try it in a minute
1. Add the beta header `anthropic-beta: mcp-client-2025-11-20` to the request.
2. Describe the server in `mcp_servers` with `type` set to `url`, an `https://` URL, a unique `name` and, if the server needs it, an `authorization_token`.
3. Add an `mcp_toolset` entry to `tools` whose `mcp_server_name` matches that name.
4. Ask a question that maps to one of the server's tools. The response contains MCP tool use and tool result blocks, followed by Claude's answer.

## Example
```bash
curl https://api.anthropic.com/v1/messages \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-10-21" \
  -H "anthropic-beta: mcp-client-2025-11-20" \
  -d '{
    "model": "claude-opus-5-5",
    "max_tokens": 1000,
    "messages": [{"role": "user", "content": "What tools do you have available?"}],
    "mcp_servers": [
      {
        "type": "url",
        "url": "https://example-server.modelcontextprotocol.io/sse",
        "name": "example-mcp",
        "authorization_token": "YOUR_TOKEN"
      }
    ],
    "tools": [
      {
        "type": "mcp_toolset",
        "mcp_server_name": "example-mcp"
      }
    ]
  }'
```

## At work
- **Release questions from a script**: with a Jira server attached, the docs give "what's blocking the release?" as a request that triggers the tool without naming it.
- **Read-only automation**: set `"default_config": {"enabled": false}` and enable only the tools you list in `configs`, so a nightly job cannot call write tools.
- **Several systems in one request**: connect multiple servers, and combine with tool search by setting `defer_loading` on rarely used tools.

## Pitfalls
- Only MCP tool calls are supported, not the rest of the MCP specification.
- The server must be publicly reachable over HTTP (Streamable HTTP or SSE). Local STDIO servers cannot be connected directly.
- You handle OAuth yourself. Obtain the access token before the call and refresh it as needed.
- Every server in `mcp_servers` must be referenced by exactly one `mcp_toolset`.
- A tool name in `configs` that does not exist on the server produces no error.
- A server can change its tools at any time. The newer header `mcp-client-2026-09-15` lets you pin the tool list.
- The page says the MCP connector is not covered by zero data retention arrangements.
