---
id: cc-autofix-pr
title: Auto-fix for pull requests
surface: code
group: Review
status: stable
level: intermediate
payoff: 2
effort: 2
jobs: [review, automation, debugging]
tags: [auto-fix, pull-requests, ci, github, cloud]
summary: Auto-fix has a Claude Code cloud session watch a pull request and push a fix when a CI check fails or a reviewer leaves a comment.
when: Turn it on once a pull request is open and the remaining work is reacting to CI and review feedback, instead of checking the PR page yourself.
replaces: Polling a pull request for red checks and making small follow-up commits by hand.
example_kind: command
docs:
  - title: Use Claude Code in the cloud
    url: https://code.claude.com/docs/en/claude-code-on-the-web
  - title: Commands
    url: https://code.claude.com/docs/en/commands
  - title: Desktop application
    url: https://code.claude.com/docs/en/desktop
verified: 2026-11-11
---
## Try it in a minute
1. Make sure the Claude GitHub App is installed on the repository and the `gh` CLI is set up.
2. Check out the pull request's branch and run `/autofix-pr` in Claude Code. It detects the open PR with `gh pr view` and spawns a cloud session that watches it.
3. Open the session at claude.ai/code to see what Claude does for each event.
4. To stop, turn off **Auto-fix** in the pull request's **⋮** menu in the session's **Changes** card, or tell Claude to stop watching the PR.

## Example
```text
/autofix-pr only fix lint and type errors
```

## At work
- **Red CI after a push.** When a check fails, Claude investigates and pushes a fix if one is clear, and explains what it did in the session.
- **Review comments.** Clear requests are fixed and pushed. For an ambiguous or architecturally significant comment, Claude asks you before acting.
- **From the desktop app.** Turning on **Auto-fix** in a pull request's **⋮** menu has Claude fix failing checks for that session's PR.

## Pitfalls
- Auto-fix requires the Claude GitHub App on the repository, and `/autofix-pr` needs `gh` and access to cloud sessions.
- Replies to review threads are posted from your GitHub account, labeled as coming from Claude Code.
- If the repository has comment-triggered automation such as Atlantis or Terraform Cloud, Claude's replies can trigger it. The docs suggest disabling auto-fix where a PR comment can deploy infrastructure.
- GitHub sends no event when the base branch advances and creates a merge conflict, so auto-fix cannot react to conflicts. Ask Claude to rebase.
- By default the session is told to fix every CI failure and review comment. Pass a prompt to narrow that.
