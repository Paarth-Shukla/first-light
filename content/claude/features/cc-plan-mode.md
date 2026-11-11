---
id: cc-plan-mode
title: Plan mode
surface: code
group: Control and safety
status: stable
level: starter
payoff: 3
effort: 1
jobs: [planning, coding, review]
tags: [plan, permissions, design, refactor]
summary: Plan mode has Claude read the code and write a plan for a change, with edits blocked until you approve it.
when: Use it before a change that spans several files or where the approach is not obvious, instead of letting Claude start editing and correcting it afterwards.
replaces: Finding out halfway through a diff that Claude took the wrong approach.
example_kind: prompt
docs:
  - title: Choose a permission mode
    url: https://code.claude.com/docs/en/permission-modes
  - title: Commands
    url: https://code.claude.com/docs/en/commands
  - title: Use Claude Code in the cloud
    url: https://code.claude.com/docs/en/claude-code-on-the-web
  - title: Manage costs effectively
    url: https://code.claude.com/docs/en/costs
verified: 2026-11-11
---
## Try it in a minute
1. In a session, press `Shift+Tab` until the status bar shows `plan mode on`, or prefix one prompt with `/plan`.
2. Describe the change. Claude reads files, runs shell commands to explore and writes a plan without editing your source.
3. Press `Ctrl+G` to open the proposed plan in your text editor and change it directly.
4. Choose **Yes, and use auto mode**, **Yes, manually approve edits**, or **No, keep planning** and say what to change.

## Example
```text
/plan migrate the retry logic in pkg/replication from fixed sleeps to exponential backoff. List every call site, the order you would change them in, which tests cover each one, and what could break for callers. Do not add new dependencies.
```

## At work
- **Design before code.** Review the plan as you would a short design note, edit it, then approve. The costs guide recommends this for complex tasks because it prevents expensive rework when the first direction is wrong.
- **Plan locally, run elsewhere.** Start with `claude --permission-mode plan`, save the agreed plan to the repo, push, then run `claude --cloud "Execute the migration plan in docs/migration-plan.md"`.
- **Unfamiliar code.** Explore a module and get a proposal without any risk of edits.

## Pitfalls
- Approving a plan exits plan mode and switches to the permission mode named in the option you picked. Press `Shift+Tab` or use `/plan` to plan again.
- In an interactive terminal session started with bypass permissions available, plan mode's blocks are not enforced.
- To start every terminal session in a project in plan mode, set `defaultMode` to `plan` in `.claude/settings.json`. The VS Code extension ignores project settings for this, so set `claudeCode.initialPermissionMode` there.
