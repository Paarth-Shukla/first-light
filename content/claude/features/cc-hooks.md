---
id: cc-hooks
title: Hooks
surface: code
group: Extend
status: stable
level: intermediate
payoff: 3
effort: 2
jobs: [automation, coding, review]
tags: [hooks, automation, formatting, guardrails, notifications]
summary: Hooks are shell commands you configure that Claude Code runs at fixed points in its lifecycle, such as before a tool call or after a file edit.
when: Use a hook when something must happen every time, like formatting after edits or blocking changes to protected files, instead of asking Claude in a prompt and hoping it remembers.
replaces: Reminding Claude to run the formatter, and watching the terminal to see when it needs you.
example_kind: config
docs:
  - title: Automate actions with hooks
    url: https://code.claude.com/docs/en/hooks-guide
  - title: Best practices for Claude Code
    url: https://code.claude.com/docs/en/best-practices
  - title: Configure the sandboxed Bash tool
    url: https://code.claude.com/docs/en/sandboxing
verified: 2026-11-11
---
## Try it in a minute
1. Open `~/.claude/settings.json` (create it if needed) and add a `hooks` block like the one below. The notification command shown is for macOS.
2. Type `/hooks` in a session and confirm your hooks appear under their events.
3. Ask Claude to edit a JavaScript file, then open it to see the formatter ran.
4. Switch away while Claude waits for permission. A desktop notification should appear.

## Example
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{ "type": "command", "command": "jq -r '.tool_input.file_path' | xargs npx prettier --write" }]
      }
    ],
    "Notification": [
      {
        "matcher": "",
        "hooks": [{ "type": "command", "command": "osascript -e 'display notification \"Claude Code needs your attention\" with title \"Claude Code\"'" }]
      }
    ]
  }
}
```

## At work
- **Formatting without reminders.** The `PostToolUse` hook formats every file Claude edits.
- **Protected paths.** A `PreToolUse` script that exits with code 2 blocks edits to files such as `.env` or generated code, and its stderr message goes back to Claude.
- **A definition of done.** A `Stop` hook running your typecheck with `exit 2` on failure sends Claude back to work until it passes.

## Pitfalls
- Exit 0 from a `PreToolUse` hook does not approve the call. The normal permission flow still applies.
- `PostToolUse` hooks cannot undo an action, because the tool has already run.
- `Stop` hooks fire whenever Claude finishes responding, not only when a task is complete.
- Matchers are case-sensitive and must match the tool name exactly.
- The examples need `jq`, and hook scripts must be executable.
- Hooks run with your full access, outside the Bash sandbox.
- Put shared hooks in `.claude/settings.json` and personal ones in `~/.claude/settings.json`.
