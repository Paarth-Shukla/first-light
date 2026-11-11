---
id: cc-goal
title: Goals with /goal
surface: code
group: Automation
status: stable
level: intermediate
payoff: 3
effort: 1
jobs: [coding, automation, debugging]
tags: [goal, autonomy, completion, migration]
summary: The /goal command sets a completion condition, and Claude keeps starting new turns until a separate model judges the condition met or impossible.
when: Use it for substantial work with a verifiable end state, such as a migration that is done when every call site compiles and the tests pass, instead of prompting "continue" after each turn.
replaces: Coming back to find Claude stopped with a progress summary while items were still open.
example_kind: command
docs:
  - title: Keep Claude working toward a goal
    url: https://code.claude.com/docs/en/goal
  - title: Best practices for Claude Code
    url: https://code.claude.com/docs/en/best-practices
verified: 2026-11-11
---
## Try it in a minute
1. In a session, run `/goal all tests in test/auth pass and the lint step is clean`. Setting a goal starts a turn immediately.
2. Watch for the `/goal active` indicator, which shows how long the goal has been running.
3. Run `/goal` with no arguments to see the condition, turns evaluated, token spend and the evaluator's latest reason.
4. Run `/goal clear` to stop early.

## Example
```text
/goal every call site of legacy_retry() under pkg/ is migrated to retry.Do, go build ./... exits 0 and go test ./pkg/... passes, with no test file deleted, or stop after 20 turns
```

## At work
- **Migrations.** One measurable end state, a stated check and a constraint are what the docs recommend for a condition that holds up over many turns.
- **Long background runs.** The best practices guide says a goal matters most there, because Claude sometimes ends a turn with a progress summary while items are still open.
- **Scripts.** `claude -p "/goal CHANGELOG.md has an entry for every PR merged this week"` runs the loop to completion in one invocation.

## Pitfalls
- The evaluator judges the condition against what appears in the conversation. It does not run commands or read files itself, so phrase the condition as something Claude's output can demonstrate.
- A goal does not change your permission mode. In Manual mode Claude still asks before tool calls, so use auto mode for unattended goals.
- One goal can be active per session. `/clear` removes it.
- Add a turn or time clause such as `or stop after 20 turns` to bound the run, and check token spend with `/goal`.
- A turn that fails on an error you have to fix clears the goal.
