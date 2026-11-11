---
id: cc-statusline
title: Custom status line
surface: code
group: Setup and cost
status: stable
level: intermediate
payoff: 2
effort: 1
jobs: [coding]
tags: [statusline, context, cost, git, terminal]
summary: The status line is a customizable bar at the bottom of Claude Code that runs your shell script and shows whatever it prints, such as context usage, cost or git branch.
when: Set one up when you want context usage or the current branch always visible, instead of running /context or git status to check.
replaces: Interrupting your work to ask how full the context window is.
example_kind: config
docs:
  - title: Customize your status line
    url: https://code.claude.com/docs/en/statusline
verified: 2026-11-11
---
## Try it in a minute
1. Run `/statusline show model name and context percentage with a progress bar`. Claude Code generates a script in `~/.claude/` and updates your settings.
2. Approve the file edit prompts if asked.
3. Look at the bottom of the interface for the new bar.
4. Refine it by running `/statusline` with a new description, or remove it with `/statusline delete`.

## Example
An inline command in `~/.claude/settings.json`, with no script file:

```json
{
  "statusLine": {
    "type": "command",
    "command": "jq -r '\"[\\(.model.display_name)] \\(.context_window.used_percentage // 0)% context\"'"
  }
}
```

## At work
- **Context at a glance.** `context_window.used_percentage` shows how full the window is without running `/context`.
- **Telling sessions apart.** Show the working directory and git branch when you run several sessions in different worktrees.
- **Spend awareness.** `cost.total_cost_usd` is the estimated session cost, and `rate_limits.five_hour.used_percentage` shows plan usage where that data is present.

## Pitfalls
- The script runs locally and does not consume API tokens, but it runs often. Slow commands such as `git status` cause lag, so cache them.
- Output appears only when the script exits with code 0 and prints to stdout. A failing script leaves the line blank.
- The line stays blank until you accept the workspace trust dialog for the folder.
- With a custom status line, Claude Code stops showing most footer keyboard hints.
- `rate_limits` appears only for some accounts and only after the first API response, so handle its absence, for example with `// empty` in `jq`.
- The cost figure is a client-side estimate and may differ from your bill.
- The examples need `jq`, and a script file must be executable (`chmod +x`).
