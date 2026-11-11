---
id: cc-model-and-effort
title: Model, effort level and fast mode
surface: code
group: Setup and cost
status: stable
level: starter
payoff: 3
effort: 1
jobs: [coding, planning, debugging]
tags: [model, effort, fast-mode, ultrathink, opusplan]
summary: Claude Code lets you pick the model, set an effort level that controls how much it reasons, and toggle a faster, more expensive fast mode on supported models.
when: Change these when the default is slower, costlier or shallower than the task needs, for example lower effort for renames and higher effort for a subtle bug.
replaces: Using one setting for everything and writing "think hard" into prompts.
example_kind: command
docs:
  - title: Model configuration
    url: https://code.claude.com/docs/en/model-config
  - title: Speed up responses with fast mode
    url: https://code.claude.com/docs/en/fast-mode
  - title: Best practices for Claude Code
    url: https://code.claude.com/docs/en/best-practices
verified: 2026-11-11
---
## Try it in a minute
1. Run `/model` to open the picker. `Enter` switches and saves the choice as your default. `s` switches for this session only.
2. Run `/effort` to open the slider, or set a level directly with `/effort high`.
3. Add the word `ultrathink` to one prompt to ask for deeper reasoning on that turn only.
4. Run `/fast` to toggle fast mode. A `↯` icon appears next to the prompt while it is on.

## Example
```text
/model opusplan      Opus in plan mode, Sonnet for execution
/effort high         work where verification matters, such as a bug in existing code
/effort low          quick exchanges, a first sketch or a rename
/fast on             faster responses on supported models, at a higher price per token
```

## At work
- **Match effort to the task.** The docs describe `low` for quick exchanges where you review each result, `medium` for day-to-day work with a clear scope and `high` where edge cases are likely.
- **Plan with one model, build with another.** `opusplan` uses `opus` in plan mode and switches to `sonnet` for execution.

## Pitfalls
- Aliases such as `opus` and `sonnet` resolve to different versions on different providers. Use a full model name to pin one.
- `max` applies to the current session only and, according to the docs, is prone to overthinking.
- Phrases like "think hard" are ordinary prompt text, not keywords. `ultrathink` is the one that is recognized.
- Fast mode costs more per token and works only on some models. On subscription plans it is billed through usage credits, and Team and Enterprise organizations need an Owner to enable it.
- Turning fast mode on mid-conversation re-reads the whole context at the uncached fast price, so enable it at the start of a session.
