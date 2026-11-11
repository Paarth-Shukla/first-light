---
id: refactor-across-many-files
title: Migrate or refactor code across many files safely
job: coding
level: power
minutes_saved: 120
features: [cc-plan-mode, cc-worktrees, cc-subagents, cc-checkpointing-and-rewind]
prerequisites: [Claude Code in a git repository with at least one commit, A test command that passes on the main branch]
fields:
  - name: change
    label: The change
    placeholder: replace direct calls to the legacy metrics client with the new telemetry package
  - name: scope
    label: Where
    placeholder: pkg/ and cmd/, excluding generated code under gen/
  - name: invariant
    label: What must not change
    placeholder: exported metric names and label sets, because dashboards and alerts depend on them
  - name: test_command
    label: Test command
    placeholder: go test ./... -race
docs:
  - title: Choose a permission mode
    url: https://code.claude.com/docs/en/permission-modes
  - title: Run parallel sessions with worktrees
    url: https://code.claude.com/docs/en/worktrees
  - title: Commands
    url: https://code.claude.com/docs/en/commands
  - title: Checkpointing
    url: https://code.claude.com/docs/en/checkpointing
  - title: Common workflows
    url: https://code.claude.com/docs/en/common-workflows
  - title: Best practices for Claude Code
    url: https://code.claude.com/docs/en/best-practices
verified: 2026-11-11
---
## Steps
1. Run `claude --worktree metrics-migration` so the work happens in its own checkout. A worktree is a fresh checkout, so install dependencies there first.
2. Send the prompt below. The `/plan` prefix runs it in plan mode: Claude reads and explores but does not edit your source.
3. Press `Ctrl+G` to edit the plan, then choose **Yes, manually approve edits** to review each edit of the first unit.
4. Once that unit is right, hand the rest to `/batch` with the same instruction. It splits the work into 5 to 30 units, shows a plan, then runs one background subagent per unit in its own worktree; each runs the tests and opens a pull request or reports what happened.
5. If an attempt goes wrong, `/rewind` restores code and conversation, but usually not subagent edits. Revert those with git.

## Prompt
```text
/plan {{change}} in {{scope}}.

Constraint: {{invariant}}. Treat any change to that as a bug, even if the tests still pass.

Before proposing edits, find every call site and group them into units that can each be changed and tested on their own. For each unit, list the files, the existing tests that cover it, and anything that makes it riskier than the rest, such as reflection, registration at init time, or code paths only reached in production.

Then propose an order: the smallest representative unit first so we can check the pattern, then the rest. Say which units are independent enough to run in parallel and which must go in sequence.

The check for every unit is `{{test_command}}` passing with the constraint above intact. Say how you will verify the constraint, since the tests may not cover it. Keep each unit to the migration itself: no new dependencies and no cleanup of unrelated code.
```

## Why it works
Plan mode separates deciding from editing, so a wrong approach costs a revised plan, not a reverted diff. The common workflows page advises refactoring in small, testable increments, and the best practices guide says to give Claude a check that comes back pass or fail. Naming the invariant adds a check the tests may miss, and worktrees keep parallel edits apart.
