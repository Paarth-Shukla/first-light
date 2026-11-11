---
id: cc-auto-memory
title: Auto memory
surface: code
group: Context and memory
status: stable
level: starter
payoff: 2
effort: 1
jobs: [coding, learning]
tags: [memory, preferences, context, corrections]
summary: Auto memory is a set of notes Claude Code writes for itself about your preferences, corrections and project context, and loads into later sessions.
when: Rely on it for things you would otherwise repeat as corrections, and use CLAUDE.md instead when you want to write the rule yourself and share it with the team.
replaces: Giving Claude the same correction in every new session.
example_kind: prompt
docs:
  - title: How Claude remembers your project
    url: https://code.claude.com/docs/en/memory
verified: 2026-11-11
---
## Try it in a minute
1. In a local session, ask Claude to remember something, for example `remember that the API tests require a local Redis instance`.
2. Watch for a line such as "Saved 2 memories" in the interface.
3. Run `/memory` to browse the memory files, open the auto memory folder, or switch auto memory on or off.
4. Open `~/.claude/projects/<project>/memory/MEMORY.md`. The files are plain markdown that you can edit or delete at any time.

## Example
```text
remember that integration tests in this repo need the array simulator running on port 8443, and that I prefer table-driven tests with one assertion helper per file
```

## At work
- **Fewer repeated corrections.** Claude saves four kinds of notes, marked `user`, `feedback`, `project` and `reference`, so a correction you give once can carry into the next session.
- **Pointers to other systems.** A `reference` note records where information lives outside the project, such as an issue tracker or dashboard.
- **Parallel checkouts.** All worktrees and subdirectories of the same git repository share one memory directory, so a preference learned in one worktree applies in the others.

## Pitfalls
- Only the first 200 lines of `MEMORY.md`, or the first 25KB, load at the start of a conversation. Topic files are read on demand.
- Auto memory is machine-local. It is not shared across machines or cloud environments.
- Claude does not save something every session, and it skips anything it can derive from the codebase or that your `CLAUDE.md` already says.
- Like `CLAUDE.md`, memory is context, not enforcement.
- The main conversation's auto memory is not loaded into subagents, except forks.
- To turn it off for one project, set `"autoMemoryEnabled": false` in that project's settings, or set `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`.
