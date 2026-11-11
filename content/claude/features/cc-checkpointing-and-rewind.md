---
id: cc-checkpointing-and-rewind
title: Checkpoints and rewind
surface: code
group: Session
status: stable
level: starter
payoff: 3
effort: 1
jobs: [coding, debugging]
tags: [rewind, checkpoints, undo, summarize]
summary: Checkpointing records the state of your code before each prompt, so the rewind menu can restore the code, the conversation or both to an earlier point.
when: Use it when an approach did not work out and you want to go back to before a prompt, rather than asking Claude to undo its own changes one by one.
replaces: Manually reverting a string of edits, or avoiding bold attempts because they are hard to back out.
example_kind: prompt
docs:
  - title: Checkpointing
    url: https://code.claude.com/docs/en/checkpointing
  - title: Best practices for Claude Code
    url: https://code.claude.com/docs/en/best-practices
verified: 2026-11-11
---
## Try it in a minute
1. Let Claude make an edit you do not want to keep.
2. Run `/rewind`, or press `Esc` twice while the prompt is empty.
3. Select the prompt you want to go back to.
4. Choose **Restore code and conversation**, **Restore conversation**, **Restore code**, or one of the **Summarize** options.

## Example
```text
Try replacing the polling loop in watcher.py with inotify. Run the tests under tests/watcher after each change. If they still fail after two attempts, stop and tell me what you learned, and I will rewind to this message.
```

## At work
- **Try the bolder approach first.** The best practices guide points out that rewind makes this low-risk, because you can roll back if it does not work.
- **Recover from a wrong turn.** Restore both code and conversation, and the original prompt returns to the input field so you can edit and resend it.
- **Trim a noisy debugging session.** **Summarize from here** compresses the conversation from that point forward and frees context while keeping your early instructions intact.

## Pitfalls
- A file that only a Bash command changed is not tracked. Revert it with git.
- Edits made by a subagent are usually not restored, including a background `/code-review --fix` run.
- Changes you make outside Claude Code, or in other concurrent sessions, are normally not captured.
- Symlinked and hard-linked files are skipped during a restore.
- Claude Code keeps file snapshots for the 100 most recent checkpoints in a session, and deletes a session's snapshots after a retention period of about 30 days by default.
- If the prompt contains text, double `Esc` clears it instead of opening the menu.
- Checkpoints are for session-level recovery and do not replace version control.
