---
id: cc-vs-code
title: VS Code extension
surface: code
group: Surfaces
status: stable
level: starter
payoff: 3
effort: 1
jobs: [coding, review, debugging]
tags: [vs-code, ide, diffs, mentions, extension]
summary: The VS Code extension is a graphical Claude Code panel inside the editor, with side-by-side diffs, @-mentions of files and selections, and plan review.
when: Use it when you want to review each proposed change as an editor diff and point Claude at the exact lines you have selected, instead of working in a separate terminal.
replaces: Copying file paths, line numbers and terminal output into a prompt by hand.
example_kind: prompt
docs:
  - title: Use Claude Code in VS Code
    url: https://code.claude.com/docs/en/vs-code
  - title: Choose a permission mode
    url: https://code.claude.com/docs/en/permission-modes
verified: 2026-11-11
---
## Try it in a minute
1. Press `Cmd+Shift+X` (Mac) or `Ctrl+Shift+X` (Windows/Linux), search for "Claude Code" and click **Install**.
2. Open a file and click the Spark icon in the editor toolbar, then sign in through your browser.
3. Select some code and press `Option+K` (Mac) or `Alt+K` (Windows/Linux) to insert a reference such as `@file.ts#5-10` into the prompt.
4. Send a request. In Manual mode, Claude shows a side-by-side diff and asks before each edit. Accept, reject, or say what to do instead.

## Example
```text
@terminal:pytest shows the failure. Look at @src/replication/scheduler.py#40-95 and explain why test_backoff_resets fails, then propose the smallest fix and wait for my approval before editing.
```

## At work
- **Reviewing edits one change at a time.** The diff has **Accept this change** and **Reject this change** buttons under each change.
- **Several tasks at once.** **Open in New Tab** or **Open in New Window** from the Command Palette starts another conversation with its own history. A colored dot on the Spark icon shows which tab needs you.
- **Plans as documents.** In Plan mode the plan opens as a Markdown document where you can add inline comments.

## Pitfalls
- The docs list VS Code 1.94.0 or later as a prerequisite.
- The extension bundles its own CLI for the panel but does not put `claude` on your PATH. Install the standalone CLI to use it in the integrated terminal.
- The extension has a subset of commands, and no `!` shell shortcut or tab completion.
- Claude sees your selected text and open file automatically. Add a `Read` deny rule for sensitive files such as `.env`.
- The extension never reads a project's `.claude/settings.json` for the starting permission mode. Use the `claudeCode.initialPermissionMode` setting.
