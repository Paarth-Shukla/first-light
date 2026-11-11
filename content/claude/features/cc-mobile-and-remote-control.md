---
id: cc-mobile-and-remote-control
title: Remote Control and mobile
surface: code
group: Surfaces
status: stable
level: intermediate
payoff: 2
effort: 2
jobs: [coding, automation]
tags: [remote-control, mobile, phone, notifications]
summary: Remote Control connects claude.ai/code or the Claude mobile app to a Claude Code session running on your own machine, so you can steer it from another device.
when: Use it when a long task needs your local files, tools or MCP servers but you want to answer its questions away from your desk. Use a cloud session when your computer will be off.
replaces: Walking back to your desk to approve a prompt or see whether a long run finished.
example_kind: command
docs:
  - title: Continue local sessions from any device with Remote Control
    url: https://code.claude.com/docs/en/remote-control
  - title: Claude Code on mobile
    url: https://code.claude.com/docs/en/mobile
verified: 2026-11-11
---
## Try it in a minute
1. In your project directory, run `claude remote-control`, or run `/remote-control` in a session that is already open.
2. Press the spacebar to show a QR code and scan it, or open the Claude app, tap **Code** and pick the session by name.
3. Send a message from the phone. The conversation stays in sync with your terminal.
4. For push notifications, run `/config` in the terminal and enable **Push when Claude decides**, **Push when actions required**, or both.

## Example
```bash
claude remote-control --name "replicator-refactor" --permission-mode acceptEdits
```

## At work
- **Unblock a long run.** Answer a permission prompt or a question from your phone so the task does not sit idle.
- **Keep your local setup.** Your filesystem, MCP servers and project configuration stay available because Claude keeps running on your machine.
- **Be told when it is done.** Ask in the prompt, for example `notify me when the tests finish`.

## Pitfalls
- The docs list Remote Control for Pro, Max, Ultra, Team and Enterprise plans. API keys are not supported, and on Team and Enterprise an Owner must enable it first.
- It is not available on Amazon Bedrock, Google Cloud's Agent Platform or Microsoft Foundry, or when `ANTHROPIC_BASE_URL` points at a gateway.
- Your computer has to stay on with the `claude` process running. On a remote machine, start it inside `tmux` or `screen`.
- While connected, the session transcript is stored on Anthropic servers. Execution and file access stay local.
- Commands that only run in the terminal interface, such as `/plugin` and `/resume`, do not work from the app.
- You cannot select Bypass permissions from the app.
