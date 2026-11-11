---
id: claude-tag
title: Claude Tag (Claude in Slack)
surface: integrations
group: Slack
status: beta
level: intermediate
payoff: 3
effort: 2
jobs: [debugging, automation, meetings, planning, coding]
tags: [slack, claude-tag, channels, team, incidents]
summary: Claude Tag puts Claude in your Slack channels, where anyone can tag @Claude into a thread to hand it work that it carries out in the open using tools an admin has connected.
when: Use a channel mention for shared team work that should stay visible, such as investigating an alert or turning a decision thread into a doc. Use a one-to-one DM for personal tasks, which run on your own Claude account and connectors.
replaces: One person disappearing from a thread to investigate, then pasting findings back for everyone else.
example_kind: prompt
docs:
  - title: Work with Claude Tag
    url: https://claude.com/docs/claude-tag/overview
  - title: Get started
    url: https://claude.com/docs/claude-tag/users/getting-started
  - title: What is Claude Tag?
    url: https://support.claude.com/en/articles/15594475-what-is-claude-tag
  - title: Commands Claude Tag understands
    url: https://claude.com/docs/claude-tag/users/commands
verified: 2026-11-11
---
## Try it in a minute
1. In a channel's message box (not inside a thread), run `/invite @Claude`. An Owner must have set Claude Tag up for your organization first.
2. Send `@Claude what can you access from this channel?` to see what it can reach.
3. Mention `@Claude` with a task. Claude posts a checklist in the thread as it goes.
4. Reply in the thread to steer it. Once Claude is in a thread you do not need to mention it again.
5. If a session is stuck, send `@Claude !restart`.

## Example
```text
@Claude the nightly replication check has failed twice this week. Search this channel and #oncall for the alert threads, compare the two failing runs, and summarize the likely cause with links to the messages you used. Then turn this thread into a draft incident note with a timeline.
```

## At work
- **Incident threads.** Everyone in the channel sees the checklist and results. With a monitoring connection, alerts can be investigated as they arrive.
- **Answers from your docs.** Policy and runbook questions answered with the source, given a docs connection such as Confluence.
- **Threads into artifacts.** Hand it a decision thread to turn into a doc, or a bug to reproduce and open a pull request for.

## Pitfalls
- Claude Tag is in public beta on Team and Enterprise plans only.
- Channel work is visible to the whole channel and bills to your organization's usage balance. One-to-one DMs bill to your own seat.
- Claude Tag starts with no access of its own to your external systems until an admin connects them.
- It can search public channels by keyword but cannot read a channel's full history unless it has been added.
- Commands such as `!restart` and `!status` must stand alone, or the message is treated as an ordinary prompt.
