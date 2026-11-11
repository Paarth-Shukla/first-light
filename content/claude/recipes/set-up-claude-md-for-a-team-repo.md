---
id: set-up-claude-md-for-a-team-repo
title: Set up CLAUDE.md project memory for a team repository
job: coding
level: starter
minutes_saved: 30
features: [cc-claude-md, cc-auto-memory, cc-best-practices]
prerequisites: [Claude Code in the repository, Recent review comments or onboarding notes from your team]
fields:
  - name: review_notes
    label: Corrections people keep making
    placeholder: Paste recent review comments, onboarding notes or corrections you have typed more than once
  - name: team_decisions
    label: Decisions that are not in the repo
    placeholder: schema migrations need storage platform review, and deploys go out on the Tuesday release train
docs:
  - title: How Claude remembers your project
    url: https://code.claude.com/docs/en/memory
  - title: Best practices for Claude Code
    url: https://code.claude.com/docs/en/best-practices
verified: 2026-11-11
---
## Steps
1. In the repository, start `claude` and run `/init`. It writes a starting `CLAUDE.md`, or suggests improvements to an existing one.
2. Send the prompt below to cut the draft down and add what only your team knows.
3. Run `/context all` and check the file is listed under **Memory files**.
4. Put personal preferences in `CLAUDE.local.md` and add it to `.gitignore`. Auto memory, which holds corrections Claude saves for you, is machine-local.
5. Commit `CLAUDE.md` and `.claude/rules/`. Run `/doctor prompt-audit` now and then to find outdated or conflicting instructions.

## Prompt
```text
Revise the CLAUDE.md you just generated. It is read by every engineer and loaded into every Claude Code session in this repository, and each line takes a little attention on every task, so keep only what you could not work out by reading the code.

<review_notes>
{{review_notes}}
</review_notes>

<team_decisions>
{{team_decisions}}
</team_decisions>

Keep: the exact build, test and lint commands, including how to run a single test file; places where the code is misleading; the decisions above; anything the review notes show people correcting more than once.
Remove: directory layouts, dependency lists and architecture overviews you can derive from the code.
Move: rules that matter for only one part of the tree into .claude/rules/ files with paths frontmatter. List multi-step procedures as suggested skills, without creating them yet.
Flag: any rule that must hold every time, such as never editing generated code, as a candidate for a hook, because CLAUDE.md is context rather than enforcement.

Write each instruction concretely enough to check ("Run make test before committing", not "test your changes"), keep the file under 200 lines, and show me the diff before saving.
```

## Why it works
The memory guide says to add to `CLAUDE.md` when Claude repeats a mistake or a review catches something it should have known, to stay under 200 lines, and to write instructions concrete enough to verify. The best practices test for each line is whether Claude could find it by reading the repo. Skills and path-scoped rules load only when needed, and hooks are the documented route for rules with no exceptions.
