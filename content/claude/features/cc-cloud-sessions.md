---
id: cc-cloud-sessions
title: Cloud sessions on the web
surface: code
group: Surfaces
status: stable
level: intermediate
payoff: 3
effort: 2
jobs: [coding, automation, review]
tags: [cloud, web, github, teleport, async]
summary: A cloud session runs Claude Code on cloud infrastructure against a GitHub repository, so the task keeps going after you close your laptop.
when: Use one for a well-defined task that does not need your local environment or frequent steering, or to run several independent tasks at once without managing worktrees.
replaces: Leaving a laptop open overnight to finish a long task.
example_kind: command
docs:
  - title: Get started with Claude Code in the cloud
    url: https://code.claude.com/docs/en/web-quickstart
  - title: Use Claude Code in the cloud
    url: https://code.claude.com/docs/en/claude-code-on-the-web
  - title: Plugins overview
    url: https://code.claude.com/docs/en/plugins/overview
verified: 2026-11-11
---
## Try it in a minute
1. Go to [claude.ai/code](https://claude.ai/code), sign in and connect GitHub when prompted.
2. Select a repository, describe the task and submit it.
3. Watch or step away. When Claude reaches a stopping point it pushes a branch. Review the diff, leave inline comments or create a pull request.
4. From a terminal, start one with `claude --cloud` and pull it back later with `claude --teleport`.

## Example
```bash
git push   # the cloud VM clones your GitHub remote at your current branch, not your local checkout
claude --cloud "Fix the authentication bug in src/auth/login.ts"
claude --teleport   # later, pull the session and its branch into this terminal
```

## At work
- **Parallel tasks.** Each session gets its own VM and branch, so three independent fixes can run at once.
- **Plan locally, execute in the cloud.** Agree a plan in plan mode, commit it, push, then run `claude --cloud "Execute the migration plan in docs/migration-plan.md"`.
- **Review from anywhere.** Sessions persist across devices, so a task started at your desk can be reviewed in the Claude mobile app.

## Pitfalls
- The docs list cloud sessions for Pro, Max, Ultra and Team plans, and for Enterprise users with premium or Chat + Claude Code seats.
- Cloning and pull request creation in Anthropic-hosted environments require GitHub. On Team and Enterprise, an Owner must first turn on the GitHub connector.
- A cloud session uses the repository only, not your local configuration. Plugins in your local settings are not loaded.
- From the CLI the handoff is one-way. You can pull a cloud session into your terminal but cannot push an existing terminal session to the cloud.
- Sessions share rate limits with the rest of your Claude usage.
