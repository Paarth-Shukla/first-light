---
id: cc-github-actions
title: GitHub Actions
surface: code
group: Automation
status: stable
level: intermediate
payoff: 3
effort: 2
jobs: [automation, review, coding]
tags: [github, ci, actions, pull-requests, mentions]
summary: Claude Code GitHub Actions is a GitHub Action that runs Claude Code in your repository's workflows, so an @claude mention can implement changes and push commits.
when: Use it when work should start from GitHub itself, such as a comment on an issue or a cron schedule, and you want to control the workflow file, triggers and model yourself.
replaces: Pulling an issue down to your laptop just to make a small, well-described change.
example_kind: config
docs:
  - title: Claude Code GitHub Actions
    url: https://code.claude.com/docs/en/github-actions
verified: 2026-11-11
---
## Try it in a minute
1. Install the GitHub CLI and run `gh auth login`. You need admin access to the repository.
2. Open `claude` in the repository and run `/install-github-app`. It installs the Claude GitHub App, saves an authentication secret, pushes a branch with the workflow files and opens GitHub with a pull request ready to create.
3. Create and merge that pull request.
4. Comment `@claude fix the TypeError in the user dashboard component` on an issue or PR. Claude replies in a comment and updates it as it works.

## Example
`.github/workflows/claude.yml`, responding to mentions:

```yaml
name: Claude Code
on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]
jobs:
  claude:
    if: contains(github.event.comment.body, '@claude')
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
      issues: write
      id-token: write
      actions: read
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 1
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

## At work
- **Issues to pull requests.** A teammate with write access mentions `@claude` on a well-described issue and reviews the result.
- **Scheduled reports.** With a `prompt` input the action runs on any event, including a cron schedule, for example a daily summary of commits and open issues.
- **Your own review job.** Pass a skill such as `/code-review:code-review --comment` as the `prompt` to post inline review comments on each PR.

## Pitfalls
- `/install-github-app` works only with github.com repositories.
- The triggering user must have write access, and bot actors are rejected unless listed in `allowed_bots`.
- Each run uses GitHub Actions minutes and API tokens. Set `--max-turns` in `claude_args` and a workflow timeout.
- Never commit API keys. Store them as GitHub Secrets.
- With a plain-text prompt in automation mode, Claude has no shell or GitHub API access until you grant tools with `--allowedTools`.
