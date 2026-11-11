---
id: api-effort
title: Effort
surface: platform
group: Models and reasoning
status: stable
level: starter
payoff: 3
effort: 1
jobs: [automation, coding, analysis]
tags: [effort, cost, latency, thinking]
summary: The effort parameter controls how many tokens Claude spends on a response, covering text, tool calls and thinking, so one model can run cheap and fast or slow and thorough.
when: Reach for it before switching models when a job is too slow or costly, or when Claude thinks too shallowly on a hard one. It is the documented way to control thinking depth where adaptive thinking is available.
replaces: Swapping models, or hand-tuning thinking token budgets, to trade quality against cost.
example_kind: command
docs:
  - title: Effort
    url: https://platform.claude.com/docs/en/build-with-claude/effort
verified: 2026-11-11
---
## Try it in a minute
1. Add `"output_config": {"effort": "medium"}` to a Messages request. No beta header is needed.
2. Pick from `low`, `medium`, `high`, `xhigh` and `max`. Leaving it out uses the model default, which is `high` on most models and `medium` on Claude Opus 5.5 and Claude Haiku 5.5.
3. Run the same prompt at two levels and compare quality, latency and token use. The docs recommend an effort sweep on your own evals.
4. At `high` and above, set a large `max_tokens`. It is the hard limit on thinking plus response text.

## Example
```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-10-21" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-opus-5-5",
    "max_tokens": 4096,
    "messages": [{
      "role": "user",
      "content": "Analyze the trade-offs between microservices and monolithic architectures"
    }],
    "output_config": {
      "effort": "medium"
    }
  }'
```

## At work
- **Bulk or simple jobs** such as summarising tickets or running subagents: `low` gives the best speed and lowest cost, with some loss of capability.
- **Long coding or agentic runs** (over 30 minutes): `xhigh` is described as the level for long-horizon work with token budgets in the millions.
- **Tool-heavy scripts**: lower effort tends to make fewer, combined tool calls and terse confirmations, which shortens routine runs.

## Pitfalls
- Effort is a behavioural signal, not a token budget. Use `max_tokens` when you need a hard ceiling.
- Changing the top-level effort between requests invalidates prompt caching. On models that support it, a per-message effort change (beta header `mid-conversation-output-config-2026-07-01`) keeps the cache.
- Do not pass `adaptive` as an effort value. It is a thinking mode.
- On some models effort barely changes reply length. Prompt for length and tone instead.
- Not every model that supports `max` supports `xhigh`, and levels are recalibrated between model generations, so do not carry a setting over untested.
