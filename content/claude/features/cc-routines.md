---
id: cc-routines
title: Cloud scheduled tasks (routines)
surface: code
group: Automation
status: beta
level: intermediate
payoff: 3
effort: 2
jobs: [automation, review, planning]
tags: [scheduled-tasks, routines, cron, triggers, cloud]
summary: A cloud scheduled task, formerly called a routine, is a saved prompt with repositories and connectors that runs as a Claude Code cloud session on a schedule, an API call or a GitHub event.
when: Use one for unattended, repeatable work with a clear outcome that should run even when your laptop is closed. Use /loop for quick polling inside an open session.
replaces: Remembering to do the same triage, summary or cleanup every morning.
example_kind: command
docs:
  - title: Automate work with scheduled tasks
    url: https://code.claude.com/docs/en/routines
  - title: Run prompts on a schedule
    url: https://code.claude.com/docs/en/scheduled-tasks
verified: 2026-11-11
---
## Try it in a minute
1. In any session, run `/schedule` with a description, for example `/schedule daily PR review at 9am`. Claude asks about the schedule, repositories and prompt before saving.
2. Or create one at [claude.ai/code/routines](https://claude.ai/code/routines) with **New task**.
3. Click **Run now** on the task's detail page to test it.
4. Open a run from the **History** list to see what Claude did, review changes and create a pull request.

## Example
```text
/schedule every weekday at 9:07am, summarize the pull requests merged to the replicator repo since the last run, flag any that changed the public API without touching docs/, and open a draft PR that updates the changelog
```

## At work
- **Backlog maintenance.** A nightly run labels new issues, assigns owners and posts a summary, so the team starts with a groomed queue.
- **Alert triage.** Your monitoring tool calls the task's API endpoint, and Claude correlates the stack trace with recent commits and opens a draft fix.
- **Docs drift.** A weekly run scans merged PRs and opens update PRs for documentation that references changed APIs.

## Pitfalls
- Scheduled tasks are in research preview. Behavior, limits and the API surface may change.
- Runs work from a fresh clone in the cloud and cannot see your local files.
- The task runs autonomously, so the prompt must be self-contained and say what success looks like.
- A task belongs to your individual account. Commits, pull requests and connector actions such as Slack messages appear as you.
- All your connected connectors are included by default. Remove the ones the task does not need.
- Schedules cannot run more often than once per hour, and a run set exactly on the hour can start several minutes late.
