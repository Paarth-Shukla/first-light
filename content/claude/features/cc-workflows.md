---
id: cc-workflows
title: Dynamic workflows
surface: code
group: Parallel work
status: stable
level: power
payoff: 3
effort: 2
jobs: [coding, review, research, automation]
tags: [workflows, ultracode, orchestration, subagents, deep-research]
summary: A dynamic workflow is a JavaScript script that Claude writes to run many subagents in the background and cross-check their results.
when: Use one when a job needs more agents than a single conversation can coordinate, such as a codebase-wide audit or a large migration, or when you want findings verified against each other.
replaces: Splitting a big audit or migration into dozens of prompts by hand and merging the answers yourself.
example_kind: prompt
docs:
  - title: Orchestrate subagents at scale with dynamic workflows
    url: https://code.claude.com/docs/en/workflows
  - title: Run agents in parallel
    url: https://code.claude.com/docs/en/agents
verified: 2026-11-11
---
## Try it in a minute
1. Run the bundled workflow `/deep-research` followed by a question. It needs the WebSearch tool.
2. Select **Yes** when Claude Code asks whether to allow the workflow.
3. Run `/workflows` to watch each phase and its agents. Press `p` to pause or resume and `x` to stop.
4. For your own task, say `use a workflow` or include the keyword `ultracode` in the prompt.
5. To reuse a run, press `s` in `/workflows` and save the script to `.claude/workflows/` or `~/.claude/workflows/`. It then runs as `/<name>`.

## Example
```text
use a workflow to audit every route handler under src/routes/ for missing authentication checks, and adversarially verify each finding before reporting it
```

## At work
- **Audits.** One agent per file, then independent agents check each finding, so you read a filtered list.
- **Migrations.** Ask for each file to be migrated in its own isolated copy and verified.
- **Fix until green.** Ask for a workflow that runs `npx tsc --noEmit` and keeps fixing errors until the check passes or two rounds in a row make no progress.

## Pitfalls
- The docs list dynamic workflows for all paid plans and API access. On Pro you turn them on in `/config`.
- A run can use meaningfully more tokens than doing the task in conversation, and it counts toward your usage and rate limits. Try a small slice first.
- A `Large workflow` warning appears above 25 agents or a projected 1.5 million tokens. It is advisory and does not pause the run.
- A workflow takes no user input mid-run. Use separate workflows if you need sign-off between stages.
- `/effort ultracode` makes Claude plan a workflow for every substantive task in the session. Turn it off with `/effort ultracode off`.
