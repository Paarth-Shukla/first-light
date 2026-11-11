---
id: cc-skills
title: Skills and custom commands
surface: code
group: Extend
status: stable
level: intermediate
payoff: 3
effort: 2
jobs: [coding, writing, review, automation]
tags: [skills, commands, procedures, reuse]
summary: A skill is a SKILL.md file of instructions that Claude Code loads when relevant or when you type its name as a slash command.
when: Create one when you keep pasting the same checklist or multi-step procedure into chat, or when a section of CLAUDE.md has grown into a procedure rather than a fact.
replaces: Pasting the same PR template, review checklist or release steps into every session.
example_kind: config
docs:
  - title: Extend Claude with skills
    url: https://code.claude.com/docs/en/skills
  - title: Explore the context window
    url: https://code.claude.com/docs/en/context-window
verified: 2026-11-11
---
## Try it in a minute
1. Create a folder with `mkdir -p ~/.claude/skills/pr-description`.
2. Save the file below as `~/.claude/skills/pr-description/SKILL.md`.
3. In a git project, start `claude` and type `/pr-description STOR-4821`, or ask for a PR description and let Claude load the skill.
4. To share it, move the folder to the project's `.claude/skills/` and commit it.

## Example
```markdown
---
description: Drafts a pull request description from the current branch. Use when the user asks for a PR description or a summary of their branch.
---

**Changes on this branch**

!`git diff main...HEAD --stat`

**Instructions**

Write a PR description for Jira issue $ARGUMENTS with these sections.
Summary in two sentences. What changed, as bullets by component.
How it was tested, with commands and results. Risks and rollback.
Do not invent test results. If no tests were run, say so.
```

## At work
- **Consistent write-ups.** PR descriptions, incident summaries and release notes follow the same structure for everyone who clones the repo.
- **Risky procedures on your terms.** Add `disable-model-invocation: true` to a deploy skill so only you can start it.
- **Cheaper context.** A skill's body loads only when it is used, unlike `CLAUDE.md`, so long reference material costs almost nothing until needed.

## Pitfalls
- The `description` is how Claude decides to load a skill. Its combined text with `when_to_use` is cut at 1,536 characters in the listing.
- If the frontmatter YAML is malformed, the skill loads with no metadata, so `/name` works but Claude cannot match it. Run with `--debug` to see the error.
- Claude Code does not re-read the file on later turns, and after compaction it may keep only the start. Put key instructions first.
- Personal skills in `~/.claude/skills/` do not load in cloud sessions.
