---
id: cc-context-management
title: Context window, compaction and /clear
surface: code
group: Session
status: stable
level: starter
payoff: 3
effort: 1
jobs: [coding, debugging]
tags: [context, compact, clear, tokens]
summary: The context window holds everything Claude knows about a session, and commands such as /context, /compact and /clear let you see and control what fills it.
when: Use them when a session has drifted across several tasks, answers are getting less focused or you are about to start something long, instead of letting old history ride along.
replaces: Carrying three finished tasks into the fourth and paying for them on every turn.
example_kind: command
docs:
  - title: Explore the context window
    url: https://code.claude.com/docs/en/context-window
  - title: Manage sessions
    url: https://code.claude.com/docs/en/sessions
  - title: Best practices for Claude Code
    url: https://code.claude.com/docs/en/best-practices
verified: 2026-11-11
---
## Try it in a minute
1. Run `/context` for a live breakdown of what is using the window, with optimization suggestions.
2. Before a long new task, run `/compact` with a focus, as in the example below.
3. When switching to unrelated work, run `/clear`. Pass a name, as in `/clear oauth-migration`, to label the session you are leaving so `/resume` can find it.
4. To compress only part of a conversation, run `/rewind`, select a message and choose **Summarize from here** or **Summarize up to here**.

## Example
```text
/compact keep the API changes, the failing test names and the exact test commands
```

## At work
- **Between tasks.** `/clear` costs nothing and stops the next task from re-reading the previous one's history on every turn.
- **Long debugging sessions.** A focused `/compact` keeps what you choose, instead of what the automatic pass guesses is important.
- **Heavy reading.** Send research to a subagent so the file contents stay in its context window, not yours.

## Pitfalls
- Claude Code compacts automatically as you approach the limit, so a full window does not end the session. Unless you compact with a focus first, the automatic pass decides what the summary keeps.
- The project-root `CLAUDE.md`, unscoped rules and auto memory are re-injected after compaction. Path-scoped rules and nested `CLAUDE.md` files are summarized away until their trigger file is read again.
- Invoked skill bodies are capped at 5,000 tokens per skill after compaction, keeping the start of the file.
- After compaction Claude Code re-reads up to five recently modified files. A file over 5,000 tokens comes back only as a path reference.
- On a long session `/compact` is itself a big request, because it reads the whole conversation to summarize it.
