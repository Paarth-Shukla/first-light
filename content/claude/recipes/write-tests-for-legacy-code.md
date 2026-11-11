---
id: write-tests-for-legacy-code
title: Write tests for legacy code before you change it
job: coding
level: intermediate
minutes_saved: 60
features: [cc-common-workflows, cc-plan-mode, cc-best-practices]
prerequisites: [Claude Code running in the repository, An existing test suite you can run locally]
fields:
  - name: target
    label: Code to cover
    placeholder: pkg/quota/enforcer.go
  - name: reason
    label: Why you need the tests now
    placeholder: we are about to change how soft limits are calculated
  - name: conventions
    label: How your tests are written
    placeholder: table-driven tests using the helpers in internal/testutil
  - name: test_command
    label: Command that runs them
    placeholder: go test ./pkg/quota/... -run Enforcer -count=1
docs:
  - title: Common workflows
    url: https://code.claude.com/docs/en/common-workflows
  - title: Choose a permission mode
    url: https://code.claude.com/docs/en/permission-modes
  - title: Best practices for Claude Code
    url: https://code.claude.com/docs/en/best-practices
  - title: Prompting best practices
    url: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
verified: 2026-11-11
---
## Steps
1. Ask `find functions in pkg/quota/enforcer.go that are not covered by tests`, with your own file.
2. Press `Shift+Tab` until the status bar shows `plan mode on`, send the prompt below and review the list of behaviours.
3. Approve the plan. Claude examines your existing test files to match their style and assertion patterns.
4. Read the tests marked surprising. They may pin a bug, so decide with the code owner whether it stays.
5. Commit the tests on their own, before the change they protect.

## Prompt
```text
I need tests for {{target}} because {{reason}}. These are characterisation tests: they record what the code does today, so the upcoming change shows up as a failing test wherever it changes behaviour.

Read the code and its callers first. Then list the behaviours worth pinning, grouped as normal cases, boundary values, error paths and concurrency, and for each one say which inputs reach it. Include behaviour that looks wrong: mark it as surprising, explain why, and test what the code does today rather than what you think it should do.

Write the tests in the style of the existing ones ({{conventions}}). Leave production code exactly as it is. If something cannot be tested without changing it, stop and tell me which seam you would need.

Run {{test_command}} and show me the command and its full result. Every new test must pass against the current code. Prefer tests that assert on outputs and state over tests that restate the implementation or only check that mocks were called.
```

## Why it works
The common workflows recipe is to find uncovered code, then ask for edge cases. The best practices guide says to give Claude a pass or fail check and ask for the command and output as evidence. The prompting guide warns that Claude can focus on making tests pass at the expense of the real goal, so the prompt states the goal and keeps production code off limits.
