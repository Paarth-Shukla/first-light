---
id: cowork-scheduled-tasks
title: Scheduled tasks in Cowork
surface: cowork
group: Delegate
status: stable
level: intermediate
payoff: 3
effort: 2
jobs: [automation, meetings, planning, research]
tags: [cowork, schedule, recurring, briefings, reports]
summary: Scheduled tasks are Cowork tasks you describe once and Claude then runs automatically on a recurring cadence, or on demand, in the cloud.
when: Schedule a task when you produce the same briefing, report or clean-up on a regular rhythm and the inputs come from connectors or files saved to your Claude account.
replaces: Rebuilding the same weekly status summary or morning catch-up by hand each time.
example_kind: prompt
docs:
  - title: Schedule recurring tasks in Claude Cowork
    url: https://support.claude.com/en/articles/13854387-schedule-recurring-tasks-in-claude-cowork
  - title: Get started with Claude Cowork
    url: https://support.claude.com/en/articles/13345190-get-started-with-claude-cowork
verified: 2026-11-11
---
## Try it in a minute
1. In Cowork, click **Scheduled** in the left sidebar, then **New task**, and choose **Create with Claude**. You can also type `/schedule` in any Cowork task.
2. Describe the task and how often it should run, and answer any questions Claude asks.
3. Review the task name, schedule and instructions Claude proposes, then click **Schedule**.
4. Open **Scheduled** again to review upcoming and past runs, or to pause, edit or run the task on demand.

## Example
```text
Every weekday at 8 AM, prepare my morning briefing.

Summarize new messages from the last 24 hours in my team's Slack channels, grouped by channel, and list anything addressed to me that I have not answered. Add today's calendar with one line of context per meeting. Finish with the three things most worth my attention first. Keep it under 300 words and do not send or post anything.
```

## At work
- **Daily briefings.** The docs list summarizing Slack messages, emails or calendar events from the past 24 hours as a common use.
- **Weekly reports.** Compile data from Google Drive, spreadsheets or connected tools into a formatted summary, or generate standup summaries from project management tools.
- **Recurring research.** Track a topic or industry news on a regular cadence and review each run as its own Cowork session.

## Pitfalls
- Scheduled tasks are for paid plans, in Cowork and in the new Claude experience.
- They run remotely, even when your computer is asleep. A task that requires local files or apps will only run locally.
- When set up manually, cadence options are hourly, daily, weekly, on weekdays or manually, and you pick an approval mode for the task.
- For work with real consequences, such as messages sent as you, consider the **Manually approve** mode.
