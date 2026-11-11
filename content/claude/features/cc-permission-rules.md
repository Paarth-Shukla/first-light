---
id: cc-permission-rules
title: Permission rules
surface: code
group: Control and safety
status: stable
level: intermediate
payoff: 3
effort: 2
jobs: [coding, automation, review]
tags: [permissions, settings, allow, deny, secrets]
summary: Permission rules are allow, ask and deny entries in settings files that decide which tool calls run, prompt or are blocked.
when: Add rules when a permission mode is too coarse, for example to pre-approve your test command or to keep Claude out of secrets files in every mode.
replaces: Clicking through the same approval prompt, and trusting a line in CLAUDE.md to keep Claude away from sensitive files.
example_kind: config
docs:
  - title: Configure permissions
    url: https://code.claude.com/docs/en/permissions
  - title: Settings files and precedence
    url: https://code.claude.com/docs/en/settings
  - title: Commands
    url: https://code.claude.com/docs/en/commands
  - title: Run Claude Code programmatically
    url: https://code.claude.com/docs/en/headless
verified: 2026-11-11
---
## Try it in a minute
1. Run `/permissions` to see every rule and the settings file it comes from.
2. Add an allow rule for a command you approve constantly, such as `Bash(npm run test *)`.
3. Add a deny rule for a file Claude must not open, such as `Read(./.env)`.
4. Keep team rules in `.claude/settings.json` and commit it. Keep personal rules in `.claude/settings.local.json` or `~/.claude/settings.json`.

## Example
A shared `.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(npm run lint)",
      "Bash(npm run test *)"
    ],
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Bash(git push *)"
    ]
  }
}
```

## At work
- **Team baseline.** Commit the rules so every clone gets the same pre-approved build and test commands.
- **Secrets.** Claude Code also applies a `Read` deny rule, on a best-effort basis, to `@file` mentions and to the selection a connected IDE shares with Claude.
- **Less prompt fatigue.** The bundled `/fewer-permission-prompts` skill scans your transcripts for common read-only Bash and MCP calls and adds an allowlist to the project settings.

## Pitfalls
- Rules are evaluated deny, then ask, then allow. An allow rule cannot carve an exception out of a deny rule.
- Put the `*` after the subcommand. `Bash(git *)` allows every git command, and without the space `Bash(git diff*)` also matches `git diff-index`.
- A bare tool name in a deny rule, such as `Bash`, removes the whole tool.
- A `.claudeignore` file has no effect. Move its entries into `Read` deny rules.
- `Read` and `Edit` deny rules do not stop a script or subprocess that opens files itself. Use the sandbox for OS-level enforcement.
- Rules are enforced by Claude Code, not the model, so wording in a prompt does not change them.
