---
id: cc-agent-teams
title: Agent teams
surface: code
group: Parallel work
status: beta
level: power
payoff: 2
effort: 3
jobs: [review, debugging, research, coding]
tags: [agent-teams, parallel, experimental, coordination]
summary: Agent teams are an experimental feature where one Claude Code session leads several teammate sessions that share a task list and message each other.
when: Try a team when parallel exploration adds real value and the workers need to challenge each other, such as a multi-angle review or competing debugging hypotheses. Use subagents when only the result matters.
replaces: Running several sessions by hand and carrying findings between them yourself.
example_kind: prompt
docs:
  - title: Orchestrate teams of Claude Code sessions
    url: https://code.claude.com/docs/en/agent-teams
  - title: Manage costs effectively
    url: https://code.claude.com/docs/en/costs
verified: 2026-11-11
---
## Try it in a minute
1. Agent teams are off by default. Add `"env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" }` to your `settings.json` and use an interactive session, since Claude spawns no teammates in `-p` runs.
2. Describe the task and the teammates you want.
3. In the agent panel below the prompt, select a teammate with the arrow keys and press `Enter` to message it directly.
4. If the lead starts implementing on its own, tell it `Wait for your teammates to complete their tasks before proceeding`.

## Example
```text
Create an agent team to review the changes on this branch before I open the PR. Spawn three teammates. One checks the retry and timeout logic for correctness, one looks for security problems in the new HTTP handlers, one checks test coverage for the changed files. Have them share findings and challenge anything they disagree on, then give me one ranked list.
```

## At work
- **Parallel code review.** Each teammate takes one lens and they compare notes before you read one list.
- **Debugging with competing hypotheses.** Teammates test different theories in parallel and converge faster.
- **Start small.** The docs suggest research and review tasks first, with 3-5 teammates.

## Pitfalls
- The feature is experimental, with known limitations around session resumption, task coordination and shutdown.
- Teams use significantly more tokens than one session. The costs guide puts it at roughly 7x when teammates run in plan mode.
- Teammates do not inherit the lead's conversation history, so put task details in the spawn prompt.
- Two teammates editing the same file leads to overwrites. Give each its own files.
- With teams enabled, a subagent that Claude names launches as a teammate, so a team can form when you did not ask for one.
