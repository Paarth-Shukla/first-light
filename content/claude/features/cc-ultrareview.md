---
id: cc-ultrareview
title: Ultrareview
surface: code
group: Review
status: beta
level: intermediate
payoff: 2
effort: 1
jobs: [review, debugging]
tags: [ultrareview, code-review, cloud, pre-merge]
summary: Ultrareview is a deep code review that runs a fleet of reviewer agents in a cloud sandbox and reports only findings it has independently reproduced and verified.
when: Run it before merging a substantial change when you want more confidence than a local review gives. Use the local /code-review for fast feedback while iterating.
replaces: A second and third manual read of a large, risky diff.
example_kind: command
docs:
  - title: Find bugs with ultrareview
    url: https://code.claude.com/docs/en/ultrareview
  - title: Review locally with /code-review
    url: https://code.claude.com/docs/en/code-review-local
verified: 2026-11-11
---
## Try it in a minute
1. Sign in with a claude.ai account. If you use an API key only, run `/login` first.
2. In a git repository, run `/code-review ultra`. With no arguments it reviews your branch against the default branch, including uncommitted and staged changes.
3. Read the confirmation dialog. It shows the review scope, your remaining free runs and the estimated cost.
4. Keep working. Use `/tasks` to see the running review. Verified findings arrive as a notification in your session.

## Example
```text
/code-review ultra 1234
```

## At work
- **Pre-merge check on a big change.** The docs position it for pre-merge confidence on substantial changes, at roughly 5 to 15 minutes per review.
- **Reviewing a pull request.** Passing a PR number reviews that pull request on github.com and uploads nothing from your machine.
- **From CI or a script.** `claude ultrareview 1234` blocks until the review finishes and prints the findings to stdout.

## Pitfalls
- Ultrareview is a research preview. The feature, pricing and availability may change.
- It bills against usage credits rather than your plan's included usage. The page lists three one-time free runs on Pro, Max and Ultra, then typically $5 to $25 per review depending on the size of the change.
- It is not available on Amazon Bedrock, Google Cloud's Agent Platform or Microsoft Foundry, or to organizations with Zero Data Retention. There, `/code-review ultra` runs a local review instead.
- For a branch review, Claude Code bundles your repository state and uploads it to the cloud sandbox.
- If you stop a review, no partial findings are returned, and a stopped run still uses a free run.
- `claude -p '/code-review ultra'` exits without waiting for findings. Use the `claude ultrareview` subcommand in scripts.
