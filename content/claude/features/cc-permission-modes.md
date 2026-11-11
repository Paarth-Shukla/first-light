---
id: cc-permission-modes
title: Permission modes and auto mode
surface: code
group: Control and safety
status: stable
level: starter
payoff: 3
effort: 1
jobs: [coding, automation]
tags: [permissions, auto-mode, accept-edits, safety]
summary: A permission mode sets which actions Claude Code may take without asking you, from Manual review of every action to auto mode with a classifier.
when: Switch modes when the prompts no longer match the risk, for example Manual for sensitive work and auto mode for a long refactor whose direction you trust.
replaces: Approving the same harmless edits and commands one prompt at a time.
example_kind: config
docs:
  - title: Choose a permission mode
    url: https://code.claude.com/docs/en/permission-modes
verified: 2026-11-11
---
## Try it in a minute
1. Look at the status bar under the prompt. It names the active mode, for example `auto mode on` or `manual mode on`.
2. Press `Shift+Tab` to cycle. From `auto` the first press goes to Manual (`default`), then `acceptEdits`, then `plan`.
3. Start a session in a chosen mode with `claude --permission-mode acceptEdits`.
4. In VS Code, click the mode indicator at the bottom of the prompt box instead.

## Example
Save this in `~/.claude/settings.json` to make every terminal session on your machine start in Manual mode:

```json
{
  "permissions": {
    "defaultMode": "default"
  }
}
```

## At work
- **Code you are reviewing.** `acceptEdits` lets Claude edit files and run common filesystem commands such as `mkdir`, `mv` and `cp` in your working directory, and you review afterwards with `git diff`.
- **Long tasks.** In auto mode a separate classifier model reviews actions and blocks things such as `curl | bash`, force pushes, production deploys and `git reset --hard`.
- **CI.** `dontAsk` denies anything that would prompt, so a pipeline runs only what you pre-approved with `--allowedTools`.

## Pitfalls
- The docs warn that auto mode reduces prompts but does not guarantee safety. Keep reviewing sensitive operations.
- If the classifier blocks an action 3 times in a row or 20 times in total, auto mode pauses and prompting resumes.
- `defaultMode: "auto"` has no effect in `.claude/settings.json` or `.claude/settings.local.json`. Put it in `~/.claude/settings.json`.
- Auto mode needs a supported model, and an organization can turn it off with `permissions.disableAutoMode`.
- `bypassPermissions` is meant for isolated containers and VMs only.
- Deny rules block in every mode, and explicit ask rules still prompt in auto mode.
