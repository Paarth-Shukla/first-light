---
id: cc-worktrees
title: Worktrees for parallel sessions
surface: code
group: Parallel work
status: stable
level: intermediate
payoff: 3
effort: 1
jobs: [coding, review, debugging]
tags: [worktree, git, parallel, isolation]
summary: The worktree flag starts Claude Code in a separate git worktree with its own files and branch, so parallel sessions do not edit the same checkout.
when: Use it when you want a second session to fix a bug or review a pull request while the first keeps building a feature in the same repository.
replaces: Stashing work, cloning the repository a second time, or waiting for one session to finish.
example_kind: command
docs:
  - title: Run parallel sessions with worktrees
    url: https://code.claude.com/docs/en/worktrees
  - title: CLI reference
    url: https://code.claude.com/docs/en/cli-reference
  - title: Commands
    url: https://code.claude.com/docs/en/commands
verified: 2026-11-11
---
## Try it in a minute
1. From a repository you have already opened with Claude Code, run `claude --worktree feature-auth`. The worktree is created under `.claude/worktrees/feature-auth/` on a branch named `worktree-feature-auth`.
2. Open another terminal and run the command again with a different name.
3. Add `.claude/worktrees/` to `.gitignore`.
4. Add a `.worktreeinclude` file listing gitignored files such as `.env` so they are copied into each new worktree.
5. When you exit, choose whether to keep or remove a worktree that has work in it.

## Example
```bash
# terminal 1: build the feature
claude --worktree feature-auth

# terminal 2: fix a bug at the same time, in its own checkout
claude --worktree fix-flaky-upload-test

# terminal 3: branch a worktree from pull request 1234 to review it
claude --worktree "#1234"
```

## At work
- **Feature and bug fix side by side.** Neither session sees the other's half-finished edits.
- **Review without disturbing your branch.** Passing `#<number>` or a pull request URL fetches that PR and branches the worktree from it.
- **Large mechanical changes.** `/batch <instruction>` splits a change into 5 to 30 units and runs one background subagent per unit, each in its own worktree. A custom subagent gets the same isolation with `isolation: worktree` in its frontmatter.

## Pitfalls
- A worktree is a fresh checkout. Install dependencies there before running tests.
- Removing a worktree deletes its directory and its branch, with all the work in them.
- Worktrees branch from the repository's default branch unless `worktree.baseRef` is set to `"head"`.
- Non-interactive `-p` runs have no exit prompt, so their worktrees are not cleaned up. Remove them with `git worktree remove`.
- Worktrees need a git repository, or `WorktreeCreate` hooks for another version control system.
