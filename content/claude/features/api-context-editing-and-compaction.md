---
id: api-context-editing-and-compaction
title: Compaction and context editing
surface: platform
group: Context
status: beta
level: power
payoff: 2
effort: 2
jobs: [automation, coding]
tags: [context, compaction, long-running, agents]
summary: Compaction replaces older turns of a conversation with a summary Claude writes on the server, and context editing clears old tool results or thinking blocks by rule, so long agent runs stay inside the context window.
when: Reach for compaction when a conversation or tool loop may outgrow the context window. Reach for context editing when you need finer control over exactly what is cleared, for example old tool results in a tool-heavy agent.
replaces: Writing your own summarisation step and history-trimming code for long sessions.
example_kind: command
docs:
  - title: Compaction overview
    url: https://platform.claude.com/docs/en/build-with-claude/compaction
  - title: Compaction at a token threshold
    url: https://platform.claude.com/docs/en/build-with-claude/compaction-threshold
  - title: Compaction on demand
    url: https://platform.claude.com/docs/en/build-with-claude/compaction-on-demand
  - title: Context editing
    url: https://platform.claude.com/docs/en/build-with-claude/context-editing
verified: 2026-11-11
---
## Try it in a minute
1. Add the beta header `anthropic-beta: compact-2026-01-12` to your Messages requests.
2. Add `{"type": "compact_20260112"}` to `context_management.edits`. By default compaction starts at 150,000 input tokens.
3. Append each response to `messages` as usual. When compaction runs, the response starts with a `compaction` block, and the API drops everything before it on later requests.
4. To clear old tool results instead of summarising, use the beta header `context-management-2025-06-27` with the edit `{"type": "clear_tool_uses_20250919"}`.

## Example
```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-10-21" \
  -H "anthropic-beta: compact-2026-01-12" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-opus-5-5",
    "max_tokens": 4096,
    "messages": [
      {
        "role": "user",
        "content": "Help me work through this migration plan step by step. I will paste each service config as we go."
      }
    ],
    "context_management": {
      "edits": [
        {
          "type": "compact_20260112"
        }
      ]
    }
  }'
```

## At work
- **Long debugging or migration sessions** in one conversation: older turns become a summary instead of an error at the context limit.
- **Tool-heavy agents**: tool result clearing removes the oldest file contents and search results once Claude has used them, and keeps the 3 most recent tool uses by default.

## Pitfalls
- The compaction overview says to use on-demand compaction wherever it is available. That variant uses the header `compact-2026-09-04` and a top-level `compaction` parameter, and it cannot be combined with `context_management` on one request.
- Compaction is an extra sampling step that is billed. Top-level `usage` excludes it, so sum `usage.iterations` to get the real total.
- When `tools` are defined, the summary step can occasionally return a block with `content: null`. Set `instructions` to tell the model not to call tools while summarising.
- The request's own model writes the summary. You cannot pick a cheaper one.
- Clearing tool results invalidates cached prompt prefixes. Use `clear_at_least` so each clear is worth the cache miss.
