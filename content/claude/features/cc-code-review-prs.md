---
id: cc-code-review-prs
title: Code Review for pull requests
surface: code
group: Review
status: stable
level: intermediate
payoff: 3
effort: 2
jobs: [review, automation]
tags: [code-review, github, pull-requests, review-md, managed]
summary: Code Review is a managed service in which several Claude agents review each GitHub pull request, verify their findings and post them as inline comments.
when: Use it when every pull request in a repository should get an automatic first review without maintaining a workflow file. For a one-off pass on your own branch, run /code-review locally.
replaces: Human reviewers spending their first pass on logic errors and broken edge cases.
example_kind: config
docs:
  - title: Code Review
    url: https://code.claude.com/docs/en/code-review
  - title: Customize Code Review
    url: https://code.claude.com/docs/en/code-review-customize
  - title: Set up Code Review
    url: https://code.claude.com/docs/en/code-review-setup
verified: 2026-11-11
---
## Try it in a minute
1. Ask an Owner of your Claude organization to turn the service on. Setup installs the Claude GitHub App and chooses repositories, a review level and when reviews run.
2. On a pull request, comment `@claude review`. The command needs write access to the repository.
3. Read the inline comments, ranked by severity, and the **Claude Code Review** check run.
4. Commit a `REVIEW.md` at the repository root to tune what gets flagged.

## Example
A `REVIEW.md` that recalibrates severity and cuts noise:

```markdown
# Review instructions

**What Important means here**

Reserve Important for findings that would break behavior, leak data,
or block a rollback. Style, naming, and refactoring suggestions are
Nit at most.

**Do not report**

- Anything CI already enforces: lint, formatting, type errors
- Generated files under `src/gen/` and any `*.lock` file

**Always check**

- New API routes have an integration test
- Log lines don't include email addresses, user IDs, or request bodies
```

## At work
- **A consistent first pass.** Reviews focus on correctness by default, not formatting or missing test coverage, so people can spend their review on design.
- **Tuned per repository.** An Owner can set Quick, Standard or Deep per repository, and `REVIEW.md` adds your own checks.

## Pitfalls
- The docs list it for Team and Enterprise plans, on GitHub repositories only, and not for organizations with Zero Data Retention.
- A review never approves or blocks a pull request, and it reads the diff and surrounding code without building or running anything.
- It can miss bugs. A review with no findings does not mean the code is error-free or secure.
- `REVIEW.md` is read from the base or default branch, never from the pull request's own changes.
