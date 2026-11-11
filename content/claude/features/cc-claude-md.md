---
id: cc-claude-md
title: CLAUDE.md project memory
surface: code
group: Context and memory
status: stable
level: starter
payoff: 3
effort: 1
jobs: [coding, review, learning]
tags: [memory, instructions, context, rules, onboarding]
summary: CLAUDE.md is a markdown file of standing instructions that Claude Code loads at the start of every session in a project.
when: Reach for it when you correct the same thing twice, or keep re-explaining a build command, convention or team decision that Claude cannot find by reading the repo.
replaces: Retyping test commands, conventions and team decisions at the top of each session.
example_kind: config
docs:
  - title: How Claude remembers your project
    url: https://code.claude.com/docs/en/memory
  - title: Best practices for Claude Code
    url: https://code.claude.com/docs/en/best-practices
verified: 2026-11-11
---
## Try it in a minute
1. In your repository, start `claude` and run `/init`. Claude analyzes the codebase and writes a starter `CLAUDE.md`, or suggests improvements to an existing one.
2. Cut the file down to what Claude cannot learn from the code, such as the exact test and lint commands, team decisions and misleading patterns.
3. Run `/context all` and check the file is listed under **Memory files**.
4. Put personal notes for this project in `CLAUDE.local.md` (add it to `.gitignore`) and preferences for every project in `~/.claude/CLAUDE.md`.

## Example
A short project file at `./CLAUDE.md`:

```markdown
# Commands
- Build: make build
- Run one test file: pytest tests/unit/test_replication.py -q

# Conventions
- New code raises errors through pkg/errors helpers
- Never edit files under gen/, they are generated from proto/

# Decisions that are not in the repo
- Schema migrations need review from the storage platform team
- Link the Confluence design page in every PR description

# More
- Git workflow @docs/git-instructions.md
```

## At work
- **Onboarding.** A new teammate's first session starts with the build commands and conventions already loaded, because the file is shared through version control.
- **Review feedback that sticks.** When a code review catches something Claude should have known, add one line.
- **Scoped rules.** Put rules for one area in `.claude/rules/api.md` with `paths:` frontmatter so they load only when Claude works on matching files.

## Pitfalls
- Claude treats `CLAUDE.md` as context, not enforced configuration. To block an action every time, use a `PreToolUse` hook.
- Target under 200 lines per file. Longer files use more context and reduce adherence, and `@path` imports do not reduce that cost.
- If two instructions contradict each other, Claude may pick one arbitrarily. `/doctor prompt-audit` reports outdated or conflicting instructions.
