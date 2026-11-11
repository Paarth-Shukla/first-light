---
id: cc-background-tasks
title: Background commands and shell mode
surface: code
group: Session
status: stable
level: starter
payoff: 2
effort: 1
jobs: [coding, debugging]
tags: [background, bash, tests, dev-server, shell]
summary: Background commands let a long-running shell command, such as a build, test run or dev server, keep going while Claude responds to new prompts.
when: Use it when a command takes minutes and you want to keep working in the same session instead of waiting or opening a second terminal.
replaces: Staring at a test run, or juggling a second terminal and pasting its output back in.
example_kind: prompt
docs:
  - title: Interactive mode
    url: https://code.claude.com/docs/en/interactive-mode
  - title: Commands
    url: https://code.claude.com/docs/en/commands
  - title: Manage sessions
    url: https://code.claude.com/docs/en/sessions
verified: 2026-11-11
---
## Try it in a minute
1. Ask Claude to run a slow command in the background, or press `Ctrl+B` while a Bash command is running to move it there. In tmux, press `Ctrl+B` twice.
2. Keep prompting. The command gets a background task ID and writes its output to a file Claude can read.
3. Run `/tasks` to see background work in the session and to stop an item.
4. Try shell mode by typing `! npm test`. The command runs directly and its output lands in the conversation.

## Example
```text
Start the dev server in the background, then run the integration suite in the background too. While they run, read ci/last-failure.log and propose a fix for the failing test. When the suite finishes, check its output and tell me which tests still fail.
```

## At work
- **Long test suites and builds.** Work on the next change while tests, `make` or a package install runs.
- **Dev servers.** Keep a server up for the whole session while Claude edits and checks it.
- **Quick shell checks.** After a `!` command, Claude responds to the output automatically, so `! npm test` gets you an explanation of the failures without a second prompt.

## Pitfalls
- Background tasks are cleaned up when Claude Code exits, and a resumed session does not restore background Bash tasks.
- A command that reaches its timeout is moved to the background instead of being stopped, unless it starts with `sleep`.
- In an unattended session, such as a `-p` run or a cloud session, a background command is stopped at its time limit.
- Commands you type in shell mode usually run outside the sandbox, because the sandbox applies to commands Claude runs.
