---
id: cc-slash-commands
title: Built-in commands
surface: code
group: Session
status: stable
level: starter
payoff: 2
effort: 1
jobs: [coding, review, debugging]
tags: [commands, slash-commands, session, reference]
summary: Built-in commands are slash-prefixed controls typed at the start of a message to manage a Claude Code session, such as /context, /diff, /model and /rewind.
when: Reach for a command when you want to change how the session runs or inspect its state, rather than describing that to Claude in a prompt.
replaces: Asking Claude in prose to do things the harness does directly, like showing the diff or clearing context.
example_kind: command
docs:
  - title: Commands
    url: https://code.claude.com/docs/en/commands
  - title: Use Claude Code in VS Code
    url: https://code.claude.com/docs/en/vs-code
  - title: Claude Code on mobile
    url: https://code.claude.com/docs/en/mobile
verified: 2026-11-11
---
## Try it in a minute
1. Type `/` in a session to see the commands available to you, then type letters to filter.
2. Run `/context` to see what is filling the context window.
3. Run `/diff` to review the changes in your working tree, including Claude's edits.
4. Run `/usage` to see session cost, plan usage limits and activity stats.

## Example
Commands across one working day:

```text
/init                      generate a starter CLAUDE.md
/plan fix the auth bug     enter plan mode with a task
/context                   see what is filling the context window
/diff                      review the working tree changes
/code-review               review the branch for correctness bugs
/security-review           check the branch diff for vulnerabilities
/clear oauth-migration     start fresh and name the session you leave
/resume oauth-migration    come back to it later
```

## At work
- **First session in a repo.** `/init`, then `/memory` to refine the file, `/mcp` for servers and `/permissions` for approval rules.
- **Before you ship.** `/diff` shows what changed, `/code-review` checks the diff for correctness bugs, and `/security-review` checks the branch for security vulnerabilities.
- **When something is wrong.** `/rewind` rolls back code and conversation, `/doctor` checks your setup, `/debug` reads the session debug log, and `/feedback` reports a bug.

## Pitfalls
- A command is recognized only at the start of your message. Text after its name becomes its arguments.
- If you send a command while Claude is responding, it is queued until the turn ends. A few, such as `/status`, `/tasks` and `/usage`, run immediately.
- The VS Code extension offers a subset of commands. Type `/` there to see which.
- Commands that only run in the terminal interface, such as `/plugin` and `/resume`, do not work from the mobile app.
