---
id: cc-desktop-app
title: Claude Code in the desktop app
surface: code
group: Surfaces
status: stable
level: starter
payoff: 2
effort: 1
jobs: [coding, review, debugging]
tags: [desktop, code-tab, diff-view, parallel-sessions, preview]
summary: The Code tab of the Claude Desktop app is Claude Code with a graphical interface, including parallel sessions, a visual diff view, an app preview and pull request monitoring.
when: Use it when you want to run several sessions side by side and review changes visually, or when a teammate prefers not to work in a terminal.
replaces: Arranging terminal windows, a browser preview and a diff tool by hand.
example_kind: prompt
docs:
  - title: Get started with the desktop app
    url: https://code.claude.com/docs/en/desktop-quickstart
  - title: Desktop application
    url: https://code.claude.com/docs/en/desktop
verified: 2026-11-11
---
## Try it in a minute
1. Install the Claude Desktop app, sign in, and click the **Code** tab. You do not need Node.js or the CLI for this tab.
2. In the row under the prompt box, pick the top entry in the **Local** group, then choose **Open folder…** and select your project.
3. Type a task and press **Enter**.
4. Click the `+12 -1` style indicator to open the diff view. Hover a line, click **+** to comment, then press **Cmd+Enter** (macOS) or **Ctrl+Enter** (Windows) to send all comments to Claude.

## Example
```text
Add tests for the retry path in upload.py and run them. Then start the dev server and check the upload page still works in the Browser pane. Show me the diff when the tests pass.
```

## At work
- **Parallel sessions.** Click **+ New** for another session, and turn on **Worktree** before starting so it runs in its own git worktree.
- **Review by commenting.** Line comments in the diff view go back to Claude, which revises and shows a new diff.
- **Pull request follow-through.** After you open a PR, its CI status appears in the **Changes** card, where **Auto-fix** has Claude fix failing checks and **Merge when ready** turns on GitHub auto-merge.

## Pitfalls
- The quickstart says Claude Code needs a Pro, Max, Ultra, Team or Enterprise subscription.
- PR monitoring requires the GitHub CLI (`gh`) installed and authenticated on your machine.
- In an SSH session Claude has no Browser pane tools, so it cannot preview or auto-verify there.
- `/desktop`, which moves a CLI session into the app, is available on macOS and x64 Windows with a Claude subscription.
- Dispatch is listed for Pro, Max and Ultra plans, not Team or Enterprise.
