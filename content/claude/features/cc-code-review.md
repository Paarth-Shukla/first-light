---
id: cc-code-review
title: Local code review with /code-review
surface: code
group: Review
status: stable
level: starter
payoff: 3
effort: 1
jobs: [review, coding, debugging]
tags: [code-review, bugs, pull-requests, security-review]
summary: The /code-review command has Claude review the changes on your branch, a pull request or a path for correctness bugs and report the findings in your session.
when: Run it before you open a pull request or before approving a teammate's, when you want a fresh reviewer that never saw the conversation that produced the code.
replaces: Rereading your own diff hoping to spot the bug, and pasting diffs into a chat window.
example_kind: command
docs:
  - title: Review locally with /code-review
    url: https://code.claude.com/docs/en/code-review-local
  - title: Commands
    url: https://code.claude.com/docs/en/commands
verified: 2026-11-11
---
## Try it in a minute
1. On a branch with changes, run `/code-review`. With no target it reviews your branch's commits ahead of its upstream plus your uncommitted changes.
2. Keep working. In a terminal session the review runs as a background subagent and the findings arrive when it completes.
3. Ask Claude to fix what it found, or rerun with `--fix` to have the findings applied to your working tree.
4. Point it elsewhere with a target, such as `/code-review 1234` for a pull request or `/code-review src/auth` for a path.

## Example
```text
/code-review high main...my-feature
```

## At work
- **Before you push.** Get a review of the branch from a subagent with its own context window before a person looks at it. `/review` is an alias.
- **Reviewing a teammate's PR.** `/code-review --comment 1234` posts the findings on the GitHub pull request as inline comments.
- **Security and cleanup passes.** `/security-review` checks the branch diff for risks like injection and data exposure, and `/simplify` reviews for cleanup only.

## Pitfalls
- The review runs in your own session, so it counts toward your plan's usage or API billing.
- A background review applies `--fix` edits outside your session's checkpoints. `/rewind` will not restore them, so use git.
- The effort level trades coverage for confidence. `low` reports only the findings it is most confident in. From `medium` through `max` coverage broadens.
- When you type no level, the review reuses the last level you typed, even from an earlier session.
- It follows your `CLAUDE.md` but does not read `REVIEW.md`, which configures the managed Code Review service.
- On GitLab, `--comment` posts through the `glab` CLI. Without it, findings print in the terminal.
- `/security-review` needs an `origin` remote.
