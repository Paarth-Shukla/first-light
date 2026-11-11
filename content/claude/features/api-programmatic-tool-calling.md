---
id: api-programmatic-tool-calling
title: Programmatic tool calling
surface: platform
group: Tools
status: stable
level: power
payoff: 3
effort: 3
jobs: [automation, analysis]
tags: [tools, code-execution, tokens, fan-out]
summary: Programmatic tool calling lets Claude write code that calls your tools from inside a code execution container, so intermediate results are processed in code and never enter the model's context.
when: Reach for it for fan-out across many items, such as checking 50 endpoints or looking up 20 records, or when tool results are large and can be filtered first. Strictly sequential workflows with small results do not benefit.
replaces: One model round trip per tool call, with every raw result loaded into the context.
example_kind: command
docs:
  - title: Programmatic tool calling
    url: https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling
verified: 2026-11-11
---
## Try it in a minute
1. Add the code execution tool at version `code_execution_20260120` or later to `tools`.
2. Add `"allowed_callers": ["code_execution_20260120"]` to each of your tools that Claude should call from code.
3. Send the request. When Claude's code calls your tool, the API returns a `tool_use` block whose `caller` names the code execution run.
4. Reply with a message that contains only the `tool_result`, and include the `container` id from the response.
5. Repeat until the code finishes and Claude answers.

## Example
```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-10-21" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-opus-5-5",
    "max_tokens": 4096,
    "messages": [
      {
        "role": "user",
        "content": "Query error counts for the us-east, us-west and eu-central clusters over the last 24 hours, then tell me which cluster had the most errors"
      }
    ],
    "tools": [
      {
        "type": "code_execution_20260120",
        "name": "code_execution"
      },
      {
        "name": "query_database",
        "description": "Execute a SQL query against the metrics database. Returns a list of rows as JSON objects.",
        "input_schema": {
          "type": "object",
          "properties": {
            "sql": {
              "type": "string",
              "description": "SQL query to execute"
            }
          },
          "required": ["sql"]
        },
        "allowed_callers": ["code_execution_20260120"]
      }
    ]
  }'
```

## At work
- **Fleet checks**: one script loops over every cluster or host, filters the results and returns only the outliers, instead of one model turn per lookup.
- **Large query results**: aggregation happens in code. The docs report typical token savings of 20 to 40 percent on requests with 10 to 49 tool definitions.

## Pitfalls
- While a programmatic call is waiting, your reply must contain only `tool_result` blocks with text content, and the container id is required.
- A pending call times out after about 4 minutes, so answer quickly.
- Tools with `strict: true`, MCP connector tools, forcing a tool through `tool_choice` and `disable_parallel_tool_use: true` are not supported.
- `allowed_callers` is guidance, not a security boundary. Be ready to handle a direct call to any tool you define.
- Document the JSON shape your tool returns, because Claude parses results in code.
- It is priced like code execution, and the page marks it as not eligible for zero data retention.
