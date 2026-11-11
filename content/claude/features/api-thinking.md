---
id: api-thinking
title: Thinking (adaptive)
surface: platform
group: Models and reasoning
status: stable
level: intermediate
payoff: 3
effort: 1
jobs: [debugging, analysis, coding]
tags: [thinking, reasoning, api]
summary: Thinking lets Claude work through a problem in separate thinking blocks before it answers, and on current models it is adaptive, so Claude decides when and how deeply to think.
when: Reach for it on proofs, tricky bugs, analysis and long agentic tasks where the first approach is often not the best one. On current models it is already on, so the real choice is whether to display it and how much effort to allow.
replaces: Adding think-step-by-step instructions to prompts and tuning a thinking token budget by hand.
example_kind: command
docs:
  - title: Thinking
    url: https://platform.claude.com/docs/en/build-with-claude/thinking
verified: 2026-11-11
---
## Try it in a minute
1. Send an ordinary Messages request to a current model. On Claude 5 and later models thinking is on by default and needs no configuration.
2. Add `"thinking": {"type": "adaptive", "display": "summarized"}` to see a summary of the reasoning. On these models `display` defaults to `"omitted"`.
3. Set `max_tokens` high enough for both the thinking and the answer, because thinking tokens count toward it.
4. Read the `thinking` blocks that arrive before the `text` block in `content`.

## Example
```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-10-21" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-opus-5-5",
    "max_tokens": 16000,
    "thinking": {
      "type": "adaptive",
      "display": "summarized"
    },
    "messages": [
      {
        "role": "user",
        "content": "A write succeeds on the primary but a read from the replica 50 ms later returns the old value. List the possible causes in order of likelihood and say how to confirm each."
      }
    ]
  }'
```

## At work
- **Debugging**: read the summarized thinking to check the reasoning behind a diagnosis instead of trusting the conclusion.
- **Analysis and capacity maths**: the docs credit thinking with better results on math, coding and analysis, where quality depends on intermediate work.
- **Interactive tools**: leave `display` at `"omitted"` when you do not show thinking. The answer starts streaming sooner.

## Pitfalls
- Thinking is billed as output tokens even when the text is omitted. Omitting reduces latency, not cost.
- The summary is not the raw chain of thought, and the billed token count will not match what you see.
- `"type": "enabled"` with `budget_tokens` returns a 400 error on the current models. Steer depth with effort instead.
- Thinking cannot be turned off on Fable 5.2 or Opus 5.5. Sonnet 5.5 rejects `"disabled"` and offers `{"type": "between_tools"}`; Haiku 5.5 accepts `{"type": "disabled"}` at `high` effort or below.
- In a tool-use loop, pass `thinking` and `redacted_thinking` blocks back complete and unmodified. Modified blocks are rejected with a 400 error.
- With API version `2026-10-21`, a request that includes `temperature`, `top_p` or `top_k` at any value returns a 400 error.
