---
id: cc-scheduled-tasks
title: Loops and in-session scheduling
surface: code
group: Automation
status: stable
level: intermediate
payoff: 2
effort: 1
jobs: [automation, debugging, review]
tags: [loop, polling, reminders, cron, session]
summary: The /loop skill re-runs a prompt on an interval inside an open Claude Code session, and plain-language requests can set one-time reminders.
when: Use it to poll a deploy, babysit a pull request or check back on a long build during a session. For work that must run without your machine, use a cloud scheduled task.
replaces: Re-typing "is it done yet?" and refreshing a CI page.
example_kind: command
docs:
  - title: Run prompts on a schedule
    url: https://code.claude.com/docs/en/scheduled-tasks
  - title: Schedule recurring tasks in Claude Code Desktop
    url: https://code.claude.com/docs/en/desktop-scheduled-tasks
  - title: Manage costs effectively
    url: https://code.claude.com/docs/en/costs
verified: 2026-11-11
---
## Try it in a minute
1. Run `/loop 5m check if the deployment finished and tell me what happened`. Claude schedules the job and confirms the cadence and job ID.
2. Leave out the interval, as in `/loop check whether CI passed and address any review comments`, and Claude picks a delay between one minute and one hour after each iteration.
3. Set a reminder in plain language, for example `remind me at 3pm to push the release branch`.
4. Stop a fixed-interval loop by asking Claude to cancel it. Stop a self-paced loop by pressing `Esc` while it waits.

## Example
```text
/loop 10m check the CI run for my branch. If a job failed, pull its log, diagnose, and push a minimal fix. If review comments arrived, address each one. If everything is green and quiet, say so in one line.
```

## At work
- **Babysitting a PR.** A bare `/loop` runs a built-in maintenance prompt that continues unfinished work and tends to the branch's pull request, including review comments, failed CI and merge conflicts.
- **Your own default.** Put your instructions in `.claude/loop.md` and a bare `/loop` runs those instead.
- **Durable local schedules.** The desktop app's scheduled tasks run on your machine while the app is open and the computer is awake.

## Pitfalls
- Tasks fire only while Claude Code is running and idle. Closing the terminal stops them, unless you send the session to the background first.
- Recurring tasks expire 7 days after creation.
- There is no catch-up for fires missed while Claude is busy.
- A scheduled fire does not execute built-in commands such as `/model`, or skills marked `disable-model-invocation: true`.
- Loops keep using tokens while you are not typing. `/usage` lists the heaviest ones.
