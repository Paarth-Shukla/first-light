---
id: api-fast-mode
title: Fast mode
surface: platform
group: Cost and scale
status: stable
level: intermediate
payoff: 2
effort: 1
jobs: [coding, automation]
tags: [fast-mode, latency, speed, pricing]
summary: Fast mode runs the same model with a faster inference configuration, giving up to 2.5x higher output tokens per second at premium pricing, with no change to intelligence or capabilities.
when: Reach for it when a person is waiting on a long generation, such as a large refactor or a long report, and the wait matters more than the price. It does not shorten the time to the first token, so it helps little on short replies.
replaces: Dropping to a smaller model only to get a long answer back sooner.
example_kind: command
docs:
  - title: Fast mode
    url: https://platform.claude.com/docs/en/build-with-claude/fast-mode
verified: 2026-11-11
---
## Try it in a minute
1. Use a model that supports fast mode. At the time of writing the page lists Claude Fable 5.2 and Claude Opus 5.5 as available on the Claude API.
2. Add `"speed": "fast"` to the Messages request.
3. Turn on streaming, where the gain in output speed is most visible.
4. Check `usage.speed` in the response. It reads `"fast"` or `"standard"`.

## Example
```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-10-21" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-opus-5-5",
    "max_tokens": 4096,
    "speed": "fast",
    "messages": [{
      "role": "user",
      "content": "Refactor this module to use dependency injection"
    }]
  }'
```

## At work
- **Interactive coding tools**: long diffs and generated files arrive sooner while you wait at the keyboard.
- **Live incident support**: a long draft of the customer update or the timeline comes back faster during the call.

## Pitfalls
- Pricing is a multiplier on standard rates. At the time of writing the page lists Claude Opus 5.5 in fast mode at $8 per million input tokens and $40 per million output tokens.
- The gain is in output tokens per second, not time to first token.
- Fast mode has its own rate limit, separate from the standard one. Exceeding it returns a `429` error with a `retry-after` header.
- Falling back to standard speed is a prompt cache miss. Requests at different speeds do not share cached prefixes.
- It is not available with the Batch API or with a Priority Tier commitment.
- Fast mode on Claude Opus 5 and Claude Opus 4.8 is a research preview that needs the `fast-mode-2026-02-01` beta header, and the page says fast mode on Opus 4.8 will be removed on November 30, 2026.
- Organizations in the Evaluation usage tier cannot use it until they move to the Start, Build or Scale tier.
