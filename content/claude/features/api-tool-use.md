---
id: api-tool-use
title: Tool use
surface: platform
group: Tools
status: stable
level: intermediate
payoff: 3
effort: 2
jobs: [automation, coding]
tags: [tools, function-calling, agents, api]
summary: Tool use lets Claude call functions you define (client tools, which your code runs) or tools Anthropic hosts (server tools such as web search and code execution) during a Messages request.
when: Reach for it when the answer depends on live data or an action in one of your systems, such as a ticket lookup or a build status. Use a server tool when Anthropic already hosts what you need.
replaces: Pasting query results into a prompt by hand, or parsing free text to decide which script to run next.
example_kind: command
docs:
  - title: Tool use with Claude
    url: https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview
  - title: Define tools
    url: https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools
verified: 2026-11-11
---
## Try it in a minute
1. Describe one function as a tool with a `name`, a detailed `description` and a JSON Schema `input_schema`.
2. Pass it in `tools`. When Claude wants it, the response has `stop_reason: "tool_use"` and a `tool_use` block with the arguments.
3. Run the function yourself, then send the assistant content back followed by a `tool_result` block carrying the same `tool_use_id`.
4. Read the final `text` block. To skip writing this loop, use the SDK tool runner.

## Example
```python
import anthropic

client = anthropic.Anthropic()

tools = [
    {
        "name": "get_build_status",
        "description": "Get the latest CI build status for a branch. Use it when the user asks whether a branch is passing. Returns the status and the failing test names, nothing else.",
        "input_schema": {
            "type": "object",
            "properties": {
                "branch": {"type": "string", "description": "Branch name, e.g. main"}
            },
            "required": ["branch"],
        },
    }
]
messages = [{"role": "user", "content": "Is main green right now?"}]

response = client.messages.create(
    model="claude-opus-5-5",
    max_tokens=1024,
    tools=tools,
    # Ask for at most one tool call in each turn.
    tool_choice={"type": "auto", "disable_parallel_tool_use": True},
    messages=messages,
)
tool_use = next(block for block in response.content if block.type == "tool_use")

status = "failed: test_snapshot_restore"  # your lookup goes here
messages += [
    {"role": "assistant", "content": response.content},
    {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": tool_use.id, "content": status}
        ],
    },
]
followup = client.messages.create(
    model="claude-opus-5-5",
    max_tokens=1024,
    tools=tools,
    tool_choice={"type": "auto", "disable_parallel_tool_use": True},
    messages=messages,
)
print(next(block for block in followup.content if block.type == "text").text)
```

## At work
- **Status questions answered from real systems**: wrap your CI, Jira or metrics lookups as tools and ask in plain language.
- **Guaranteed argument shape**: add `strict: true` to a tool so calls always match your schema.

## Pitfalls
- Descriptions are "by far the most important factor". Aim for at least three or four sentences per tool.
- Tool names, descriptions and schemas are billed as input tokens on every request.
- Claude Fable 5.2, Opus 5.5 and Sonnet 5.5 reject forced tool use (`tool_choice` of type `any` or `tool`) with a 400 error. Use `auto` with strict tool use.
- If a required parameter is missing from the prompt, Claude may guess a value instead of asking.
