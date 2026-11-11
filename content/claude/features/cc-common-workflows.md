---
id: cc-common-workflows
title: Everyday prompt recipes
surface: code
group: Workflows
status: stable
level: starter
payoff: 3
effort: 1
jobs: [learning, coding, debugging, writing]
tags: [recipes, onboarding, bugs, tests, pull-requests, docs]
summary: The common workflows page is a set of documented prompt patterns for everyday tasks such as exploring a codebase, fixing a bug, adding tests, writing docs and creating pull requests.
when: Start here when you are new to a repository or to Claude Code and want a prompt sequence that is known to work, instead of inventing one.
replaces: Reading through a codebase file by file to find where a feature lives.
example_kind: prompt
docs:
  - title: Common workflows
    url: https://code.claude.com/docs/en/common-workflows
verified: 2026-11-11
---
## Try it in a minute
1. `cd` to a project root and run `claude`.
2. Ask `give me an overview of this codebase`.
3. Narrow down with `find the files that handle user authentication`, then `trace the login process from front-end to database`.
4. Reference a file directly with `@`, as in `Explain the logic in @src/utils/auth.js`.
5. When you have changes, ask `create a pr`.

## Example
Onboarding to a service you have just inherited:

```text
give me an overview of this codebase, then explain the main architecture patterns used here and the key data models. Add a glossary of project-specific terms. After that, trace one write request from the API handler to disk and list the files involved.
```

## At work
- **Onboarding.** Start broad, then narrow. The docs also suggest asking about conventions and for a glossary.
- **Bug fixing.** Give Claude the command that reproduces the issue and say whether the error is intermittent or consistent, then ask for a few ways to fix it before applying one.
- **Tests and docs.** `find functions in NotificationsService.swift that are not covered by tests`, then `add test cases for edge conditions in the notification service`. Claude matches the style and frameworks of your existing test files.

## Pitfalls
- An `@` file reference includes the file's content only when it fits the Read tool's token limit, 25,000 tokens by default. A text file larger than 256KB is not included.
- A directory reference shows a file listing, not contents.
- `PreToolUse` hooks do not run for files included through `@`, because no tool call is made. Use a `Read` deny rule to block specific paths.
- Review Claude's generated pull request before submitting it, and ask it to highlight risks.
