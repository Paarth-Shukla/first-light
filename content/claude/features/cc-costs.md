---
id: cc-costs
title: Track and reduce usage
surface: code
group: Setup and cost
status: stable
level: starter
payoff: 2
effort: 1
jobs: [coding, automation]
tags: [costs, usage, tokens, limits, budget]
summary: The /usage command shows session token use and plan limits, and a handful of habits such as clearing context and choosing a smaller model keep that usage down.
when: Check it when you hit limits sooner than expected or before rolling Claude Code out to a team, rather than guessing where the tokens went.
replaces: Finding out you are near a limit only when a session stops.
example_kind: command
docs:
  - title: Manage costs effectively
    url: https://code.claude.com/docs/en/costs
  - title: Run Claude Code programmatically
    url: https://code.claude.com/docs/en/headless
  - title: CLI reference
    url: https://code.claude.com/docs/en/cli-reference
verified: 2026-11-11
---
## Try it in a minute
1. Run `/usage`. On a subscription plan you see plan usage bars and a breakdown of what counts against your limits. Press `d` or `w` to switch between the last 24 hours and the last 7 days.
2. Read the recommendation rows, which name changes such as trimming a large `CLAUDE.md`.
3. Run `/context` to see what is taking space right now.
4. Run `/clear` before the next unrelated task.

## Example
Cap an unattended run and print what it cost:

```bash
claude -p "Update the dependency pins and run the tests" \
  --permission-mode auto --permission-prompts none \
  --max-turns 30 --max-budget-usd 5 \
  --output-format json | jq '.total_cost_usd'
```

## At work
- **Find the heavy hitters.** The breakdown attributes recent usage to skills, subagents, plugins and individual MCP servers.
- **Shrink what loads every turn.** Move workflow-specific instructions from `CLAUDE.md` into skills, which load only when invoked, and disable MCP servers you are not using with `/mcp`.
- **Right-size the model.** Use Sonnet for most coding, reserve Opus for complex reasoning, and set `model: haiku` on simple subagents.

## Pitfalls
- The session cost figure is computed locally from token counts at list price. It is an estimate, and for subscribers it is not relevant for billing.
- The `/usage` breakdown is approximate and comes from local session history on this machine only.
- Thinking tokens are billed as output tokens. Lower the effort level for simple tasks.
- Vague requests like "improve this codebase" trigger broad scanning. Specific prompts read fewer files.
- Loops, goals and subagents keep sending requests while you are not typing.
- `--max-budget-usd` and `--max-turns` work in print mode only. The cap is checked against a client-side estimate and spend can pass it, so leave headroom.
