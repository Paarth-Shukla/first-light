---
id: api-prompt-caching
title: Prompt caching
surface: platform
group: Cost and scale
status: stable
level: intermediate
payoff: 3
effort: 1
jobs: [automation, coding, analysis]
tags: [caching, cost, latency, cache-control]
summary: Prompt caching lets the API resume from a prompt prefix it has already processed, so repeated instructions, documents and tool definitions cost less and respond faster.
when: Reach for it when many requests share the same long start, such as a runbook, a code base summary or a growing conversation. It does not help when every prompt is short or different.
replaces: Paying full input price to re-send the same long system prompt or document on every call.
example_kind: command
docs:
  - title: Prompt caching
    url: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
verified: 2026-11-11
---
## Try it in a minute
1. Add `"cache_control": {"type": "ephemeral"}` at the top level of a Messages request. This is automatic caching, where the breakpoint moves forward as the conversation grows.
2. Put stable content first. The prefix is built in the order `tools`, `system`, then `messages`.
3. Send the same request twice within 5 minutes.
4. Check `usage` in the response. `cache_creation_input_tokens` shows a write and `cache_read_input_tokens` shows a hit.
5. For finer control, put `cache_control` on the last content block that stays identical across requests.

## Example
```bash
curl https://api.anthropic.com/v1/messages \
  -H "content-type: application/json" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-10-21" \
  -d '{
    "model": "claude-opus-5-5",
    "max_tokens": 1024,
    "cache_control": {"type": "ephemeral"},
    "system": "You are an on-call assistant for the storage platform team. Follow the runbook below when you answer. <runbook>...paste the full runbook here...</runbook>",
    "messages": [
      {
        "role": "user",
        "content": "Alert: replication lag above 30 seconds on cluster east-2. What do I check first?"
      }
    ]
  }'
```

## At work
- **Runbook or codebase Q&A bots**: the long shared context is written once and then read from cache on each question.
- **Agent loops with many tool calls**: each step is a new API call, and the earlier history becomes a cache read.

## Pitfalls
- The default lifetime is 5 minutes, measured from the start of the request and refreshed on each use. A 1-hour option (`"ttl": "1h"`) costs more.
- Cache writes are priced above base input (1.25 times for 5 minutes, 2 times for 1 hour) and reads well below it, so caching pays only when the prefix is reused.
- Prompts below the model minimum (512 tokens on the current models) are processed without caching and without an error. Zero in both cache fields means nothing was cached.
- Changing tool definitions invalidates everything. Toggling web search or citations, or changing thinking or effort settings, invalidates later levels.
- `input_tokens` counts only the tokens after the last breakpoint, not your whole prompt.
