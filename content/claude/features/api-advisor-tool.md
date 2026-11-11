---
id: api-advisor-tool
title: Advisor tool
surface: platform
group: Tools
status: beta
level: power
payoff: 2
effort: 2
jobs: [coding, automation, planning]
tags: [advisor, multi-model, cost, agents, beta]
summary: The advisor tool lets a faster, lower-cost executor model consult a higher-intelligence advisor model for a plan or course correction in the middle of a request.
when: Reach for it on long agentic work, such as a coding agent or a multistep research pipeline, where most turns are mechanical but a good plan matters. It is a weak fit for single-turn questions, where there is nothing to plan.
replaces: Running the whole task on the most capable model, or building your own planner and worker hand-off.
example_kind: command
docs:
  - title: Advisor tool
    url: https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool
verified: 2026-11-11
---
## Try it in a minute
1. Add the beta header `anthropic-beta: advisor-tool-2026-03-01`.
2. Set the top-level `model` to the executor, the model that does most of the work.
3. Add a tool with `"type": "advisor_20260301"`, `"name": "advisor"` and the advisor's `model`.
4. Send the task. The executor decides when to consult the advisor, and the advice comes back inside the same request as an `advisor_tool_result` block.
5. Read `usage.iterations` to see what each model consumed.

## Example
```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-10-21" \
  -H "anthropic-beta: advisor-tool-2026-03-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-sonnet-5-5",
    "max_tokens": 16000,
    "tools": [
      {
        "type": "advisor_20260301",
        "name": "advisor",
        "model": "claude-opus-5-5"
      }
    ],
    "messages": [{
      "role": "user",
      "content": "Build a concurrent worker pool in Go with graceful shutdown. Keep it brief."
    }]
  }'
```

## At work
- **Coding agents on a budget**: the docs say a Sonnet executor at medium effort with an Opus advisor reaches intelligence comparable to Sonnet at default effort, at lower cost.
- **A step up from Haiku**: add an Opus or Fable advisor. Expect a higher cost than Haiku alone, but lower than moving the whole job to a larger model.

## Pitfalls
- The advisor must be at least as capable as the executor, and only listed pairs are valid. Check the model compatibility section.
- Advisor calls are billed at the advisor model's rates. Top-level `usage` shows executor tokens only, so sum `usage.iterations` for cost tracking.
- The top-level `max_tokens` does not limit the advisor. Set `max_tokens` and `max_uses` on the tool definition to cap it.
- The advisor sees the executor's full transcript, including your system prompt, tool definitions and tool results.
- With a current Opus advisor the advice arrives encrypted, as an `advisor_redacted_result`, so your client cannot read it. Pass the result blocks back verbatim in later requests.
- Results depend on the task. The docs tell you to evaluate on your own workload.
