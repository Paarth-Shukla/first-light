---
id: cc-agent-view
title: Agent view and background sessions
surface: code
group: Parallel work
status: beta
level: intermediate
payoff: 3
effort: 1
jobs: [coding, debugging, review, automation]
tags: [agent-view, background-sessions, parallel, dispatch]
summary: Agent view, opened with claude agents, is one screen that lists your background Claude Code sessions and shows which are working, done or waiting for you.
when: Use it when you have several independent tasks to hand off and want to step in only when one needs you, instead of keeping a terminal open per task.
replaces: A row of terminal tabs that you cycle through to see whether anything is waiting.
example_kind: command
docs:
  - title: Manage multiple agents with agent view
    url: https://code.claude.com/docs/en/agent-view
  - title: Run agents in parallel
    url: https://code.claude.com/docs/en/agents
verified: 2026-11-11
---
## Try it in a minute
1. Run `claude agents` in your project. If you have not trusted the folder yet, the workspace trust dialog appears first.
2. Type a task and press `Enter`. A new background session starts and appears as a row. Each prompt you enter here starts another session.
3. Select a row and press `Space` to peek at its latest output or question, and type a reply.
4. Press `Enter` or `→` to attach to the full conversation, and `←` on an empty prompt to detach.
5. In a normal session, run `/bg` to send the conversation to the background.

## Example
```bash
claude --bg "investigate why test_snapshot_restore is flaky and report the cause"
claude agents          # one screen for every session and its state
claude logs <id>       # print a session's recent output
claude stop <id>       # stop it
```

## At work
- **Three tasks at once.** Dispatch a bug fix, a pull request review and a flaky-test investigation as three rows, then check back when a row turns yellow for input or green for done.
- **Safe parallel edits.** A dispatched session moves into its own git worktree under `.claude/worktrees/` before it edits files.
- **Branch a line of thought.** `/fork` copies the current conversation into a new background session while you keep working.

## Pitfalls
- Agent view is in research preview, so the interface and shortcuts may change.
- Each session uses your subscription quota independently.
- `--bg` cannot be combined with `-p`. The prompt is the positional argument.
- A session you sent to the background with `/bg` keeps editing where it was already working, without a new worktree.
- Sessions keep running when you close the terminal and survive sleep, but shutting the machine down stops them.
