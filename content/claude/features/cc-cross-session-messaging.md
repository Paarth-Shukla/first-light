---
id: cc-cross-session-messaging
title: Cross-session messaging
surface: code
group: Parallel work
status: new
since: 2026-08
level: intermediate
payoff: 2
effort: 1
jobs: [coding, debugging, planning]
tags: [sessions, messaging, parallel, worktrees, coordination]
summary: Cross-session messaging lets Claude deliver a plain-text message from one of your Claude Code sessions to another, on this machine, another machine or in the cloud.
when: Use it when one session learns something another needs mid-task, such as a breaking change or a finished migration, instead of copy-pasting between terminals.
replaces: Re-explaining a finding to a second session by hand.
example_kind: prompt
docs:
  - title: Message your other Claude Code sessions
    url: https://code.claude.com/docs/en/cross-session-messaging
  - title: What's new
    url: https://code.claude.com/docs/en/whats-new
verified: 2026-11-11
---
## Try it in a minute
1. Open two sessions on the same machine and name each with `/rename`.
2. In one session, run `/list-agents` to confirm messaging is available. If the command is not recognized, the session does not have the feature.
3. Tell Claude what the other session should know. Type `@` and the first letters of the session's name to pick the target.
4. In the receiving session, look for a line such as `› Message from @api-worker: Schema migration finished` and press `Ctrl+O` to read the full text.

## Example
```text
Let @api-worker know the schema migration finished, that the new column is tenant_id, and that rebasing on main is safe now. Then ask it whether its integration tests still pass.
```

## At work
- **Hand over a finding.** When one session discovers a breaking change, Claude summarizes it for the session working on the affected area.
- **Coordinate parallel worktrees.** Sessions working the same repository can tell each other what landed.
- **Status from long-running work.** Ask a session running a migration or test suite to report back to the one you are watching.

## Pitfalls
- A message is text that one Claude writes to another. It never carries the sender's conversation history or files.
- Messages on the same machine travel over a local per-session socket and never through Anthropic servers. Reaching sessions on other machines or in the cloud needs Remote Control with a claude.ai sign-in.
- The receiving session applies its own inbound controls and can hold or drop a message. Set `crossSessionInbound` to `refuse` to stop a session receiving them.
- Repeated messages are rate-limited per sender and at most 50 accepted messages are queued, so a loop between two sessions stops on its own.
