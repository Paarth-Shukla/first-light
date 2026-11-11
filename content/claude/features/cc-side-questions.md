---
id: cc-side-questions
title: Side questions with /btw
surface: code
group: Session
status: stable
level: starter
payoff: 2
effort: 1
jobs: [coding, learning, debugging]
tags: [btw, side-question, context, overlay]
summary: The /btw command asks a quick question about your current work and answers it from the existing conversation without adding anything to the history.
when: Use it for a quick recall or clarification while Claude is busy, when a normal prompt would interrupt the turn or clutter the conversation.
replaces: Interrupting a long turn, or scrolling back to find a detail Claude already read.
example_kind: command
docs:
  - title: Interactive mode
    url: https://code.claude.com/docs/en/interactive-mode
  - title: Commands
    url: https://code.claude.com/docs/en/commands
verified: 2026-11-11
---
## Try it in a minute
1. While Claude is working on something, type `/btw what was the name of that config file again?`.
2. Read the answer in the overlay. The main turn keeps running.
3. Press `c` to copy the answer as raw Markdown, or `f` to fork the question into a background subagent that has full tool access.
4. Press `Space`, `Enter` or `Escape` to dismiss. Run `/btw` with no question to reopen your most recent exchange.

## Example
```text
/btw which of the files you have read so far define the retry policy, and what did we decide about the timeout?
```

## At work
- **Recall without derailing.** Ask what Claude decided earlier, or what a function it already read does, while a long refactor continues.
- **Keep the history clean.** The question and answer never enter the conversation, so they do not dilute later context.
- **Check on a subagent.** With a subagent's transcript open, `/btw` answers from that transcript, so you can ask what the subagent did.

## Pitfalls
- Side questions have no tool access. Claude cannot read files, run commands or search when answering one, only use what is already in context.
- Each side question gets a single response. To continue, ask another `/btw`, or press `f` to fork it.
- The answer cannot see the reply Claude is still writing.
- In the terminal the thread lives in memory and is gone when you exit Claude Code.
- A side question is low cost rather than free. The docs say it costs little beyond the answer itself while the conversation's prompt cache is warm.
- In the VS Code extension, `/btw` opens a panel instead of the overlay.
