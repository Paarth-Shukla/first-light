---
id: api-tool-search
title: Tool search tool
surface: platform
group: Tools
status: stable
level: power
payoff: 2
effort: 2
jobs: [automation, coding]
tags: [tool-search, defer-loading, context, mcp]
summary: The tool search tool lets Claude search a large tool catalog and load only the definitions it needs, instead of putting every tool definition in the context window up front.
when: Reach for it when you have 10 or more tools, when definitions use more than 10k tokens, or when you aggregate several MCP servers. With fewer than 10 small tools, standard tool calling is the better fit.
replaces: Hand-picking a subset of tools for each request to keep the prompt small.
example_kind: command
docs:
  - title: Tool search tool
    url: https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool
verified: 2026-11-11
---
## Try it in a minute
1. Add a search tool to `tools`. Use `tool_search_tool_regex_20251119` (Claude writes regex patterns) or `tool_search_tool_bm25_20251119` (Claude writes natural language queries).
2. Keep sending every tool definition, and add `"defer_loading": true` to the ones that should not load up front.
3. Leave your 3 to 5 most used tools non-deferred so Claude can call them without searching.
4. Send a request. The API returns matches as `tool_reference` blocks and expands them into full definitions for Claude.

## Example
```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-10-21" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-opus-5-5",
    "max_tokens": 2048,
    "messages": [
      {
        "role": "user",
        "content": "Find the open pull requests that touch the replication module."
      }
    ],
    "tools": [
      {
        "type": "tool_search_tool_regex_20251119",
        "name": "tool_search_tool_regex"
      },
      {
        "name": "github_list_prs",
        "description": "List pull requests in a repository, filtered by state and changed path",
        "input_schema": {
          "type": "object",
          "properties": {
            "state": {"type": "string", "enum": ["open", "closed"]},
            "path": {"type": "string"}
          },
          "required": ["state"]
        },
        "defer_loading": true
      }
    ]
  }'
```

## At work
- **One assistant over GitHub, Slack, Jira and monitoring tools**: the docs say a typical multiserver setup can use about 55k tokens in definitions, and that tool search typically cuts this by over 85 percent.
- **Better tool selection**: accuracy degrades past 30 to 50 available tools, and loading a focused set avoids that.

## Pitfalls
- Never set `defer_loading: true` on the search tool itself. If every tool is deferred, the API returns a 400 error.
- You still send every full definition on every request. Deferring changes what enters the context, not the request body.
- A deferred tool cannot also carry `cache_control`.
- Search matches names, descriptions, argument names and argument descriptions. Prefix names by service (for example `github_`, `slack_`) and put keywords in descriptions.
- The regex variant takes Python `re.search()` patterns of up to 200 characters, not natural language.
- A search returns up to 5 tools by default, and a request can hold at most 10,000 deferred tools.
