---
id: cc-doctor
title: Setup checkup with /doctor
surface: code
group: Setup and cost
status: new
since: 2026-07
level: starter
payoff: 2
effort: 1
jobs: [debugging, coding]
tags: [doctor, setup, diagnostics, audit, configuration]
summary: The /doctor command runs a setup checkup that diagnoses installation, settings, extension and CLAUDE.md problems and proposes fixes that Claude applies after you confirm.
when: Run it when Claude Code behaves oddly after an upgrade, when your setup has grown a pile of skills, servers and plugins, or when instructions seem to be ignored.
replaces: Hunting through settings files, PATH entries and old instruction files by hand.
example_kind: command
docs:
  - title: Extend Claude with skills
    url: https://code.claude.com/docs/en/skills
  - title: How Claude remembers your project
    url: https://code.claude.com/docs/en/memory
  - title: Commands
    url: https://code.claude.com/docs/en/commands
  - title: What's new
    url: https://code.claude.com/docs/en/whats-new
verified: 2026-11-11
---
## Try it in a minute
1. In a session, run `/doctor`. `/checkup` is an alias.
2. Read the findings. Claude reports first and asks for confirmation before it changes anything.
3. Confirm the fixes you want.
4. To audit your instructions for outdated or conflicting content instead, run `/doctor prompt-audit`.
5. For read-only installation diagnostics without starting a session, run `claude doctor` in your terminal.

## Example
Audit one skill folder for outdated or conflicting instructions:

```text
/doctor prompt-audit .claude/skills/deploy
```

## At work
- **Installation health.** The checkup looks for duplicate or leftover installs, `PATH` problems, unparseable settings files and whether a newer version is available.
- **Trim what you do not use.** It compares unused skills, MCP servers and plugins with their context cost, and flags slow hooks.
- **Leaner instruction files.** It finds local `CLAUDE.md` files that duplicate checked-in ones and content Claude could derive from the codebase, and offers to move always-loaded guidance into skills and nested `CLAUDE.md` files.

## Pitfalls
- Nothing in your files changes until you ask Claude to apply the proposed edits.
- By default the prompt audit covers `CLAUDE.md`, `CLAUDE.local.md` and `AGENTS.md` files plus the rules, skills, commands, subagents and output styles under `.claude/` and `~/.claude/`. Pass a path to narrow it.
- The audit runs through the bundled `/claude-api` skill, so it is unavailable when that skill is turned off.
- The usage part of the checkup applies to subscription plans, and `/doctor` leaves it out while Remote Control is connected.
- The docs give minimum Claude Code versions for the `prompt-audit` subcommand and the usage check, so update if a subcommand is missing.
