---
id: cc-large-codebases
title: Monorepos and large codebases
surface: code
group: Context and memory
status: stable
level: power
payoff: 3
effort: 3
jobs: [coding, planning, review]
tags: [monorepo, large-codebase, context, settings, worktrees]
summary: The large codebase guide shows how to scope Claude Code to the part of a big repository a task touches, using per-directory CLAUDE.md files, Read deny rules, sparse worktrees and code intelligence.
when: Apply it when a big repository fills the context window with instructions and file reads unrelated to your task, which costs tokens and degrades Claude's performance.
replaces: One giant root CLAUDE.md, and watching Claude wander through vendored and generated code.
example_kind: config
docs:
  - title: Set up Claude Code in a monorepo or large codebase
    url: https://code.claude.com/docs/en/large-codebases
verified: 2026-11-11
---
## Try it in a minute
1. Decide where to start `claude`. From the repository root it can reach every file and loads the root `CLAUDE.md`. From a subdirectory it reaches that subtree and loads that directory's `CLAUDE.md` plus every ancestor's.
2. Split instructions. Keep repository-wide rules in the root `CLAUDE.md` and put each subsystem's conventions in its own `CLAUDE.md`.
3. Add `Read` deny rules for checked-in generated and vendored code, as in the example.
4. Run `/context all` and check the list under **Memory files** to confirm which instruction files loaded.

## Example
A `.claude/settings.json` that keeps Claude out of build output and vendored code and limits new worktrees to two packages:

```json
{
  "permissions": {
    "deny": [
      "Read(./**/dist/**/*)",
      "Read(./**/build/**/*)",
      "Read(./**/*.generated.*)",
      "Read(./**/vendor/**/*)"
    ]
  },
  "worktree": {
    "sparsePaths": [".claude", "packages/api", "packages/shared"]
  }
}
```

## At work
- **Only the conventions you need.** Starting from `packages/api/` loads its rules and the root rules, with nothing from sibling packages in context.
- **Skip other teams' instructions.** `claudeMdExcludes` in `.claude/settings.local.json`, for example `"**/packages/web/**"`, stops those files from ever loading.
- **Cross-package changes.** Grant a sibling directory with `claude --add-dir ../shared`, and plan first in plan mode, because the plan file is re-injected after each compaction.

## Pitfalls
- Project settings in `.claude/settings.json` are not inherited from parent directories the way `CLAUDE.md` files are.
- Content searches already respect `.gitignore`, so deny rules are only needed for paths that are checked in.
- End directory patterns with `/**/*` rather than `/**`, so Claude can still list the directory.
- Relative `Read` patterns anchor at the session's working directory, not the repository root.
- Include `.claude` in `sparsePaths` if you want the root settings and rules inside the worktree.
- A directory added through the `additionalDirectories` setting never loads its `CLAUDE.md`, rules or skills.
