---
id: catch-up-after-leave
title: Catch up on Slack, email and tickets after time off
job: planning
level: starter
minutes_saved: 60
features: [slack-connector, google-workspace-connectors, connectors, claude-in-outlook]
prerequisites: [The Slack connector if your plan includes it, Gmail and Google Calendar connected or Claude for Outlook, A connector for your issue tracker]
fields:
  - name: away_from
    label: First day away
    placeholder: 20 October
  - name: away_to
    label: Last day away
    placeholder: 7 November
  - name: role
    label: What you own
    placeholder: the replication service and its on-call rotation
  - name: channels
    label: Slack channels that matter
    placeholder: storage-platform, replication-dev and oncall
  - name: tracker_project
    label: Tracker project
    placeholder: STOR
docs:
  - title: Slack integration
    url: https://claude.com/docs/connectors/slack/index
  - title: Use Google Workspace connectors
    url: https://support.claude.com/en/articles/10166901-use-google-workspace-connectors
  - title: Use connectors to extend Claude's capabilities
    url: https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities
  - title: Use Claude for Outlook
    url: https://claude.com/docs/office-agents/outlook
verified: 2026-11-11
---
## Steps
1. In a new chat, select **+**, then **Connectors**, and turn on Slack, Gmail, Google Calendar and your issue tracker. On Team and Enterprise plans an Owner enables each connector first.
2. Send the prompt below. Answers from Gmail and Calendar cite the emails and events used.
3. Open the original source before replying to anything that matters.
4. Ask for draft replies. By default Claude asks for approval before it sends, replies to or forwards email.
5. If your mail is in Outlook on Microsoft 365, ask the Claude for Outlook add-in "What needs me?" for the inbox instead. It leaves every draft unsent.

## Prompt
```text
I was away from {{away_from}} to {{away_to}} and I am back today. I own {{role}}. Help me decide what to do first, rather than read everything.

Look at: my email and calendar for that period and the next five working days; the Slack channels {{channels}} and my direct messages; and issues in {{tracker_project}} that are assigned to me, reported by me or mention me and changed while I was away.

Report in this order:
1. Waiting on me: direct questions, review requests and asks, with who asked, when, and whether they seem to have solved it another way since.
2. Decisions made while I was away that affect what I own, quoting the message that states each one.
3. Changes to my issues: status, priority, reassignment and new blockers.
4. Meetings this week I need to prepare for, with one line on why.
5. Everything else, in one short paragraph.

Within each section, put items where someone is blocked on me first, then sort by deadline. Leave out automated notifications unless one shows something broken. Cite the source for every item. Treat this as read-only: change nothing, and at the end offer draft replies for the top five items.
```

## Why it works
The Slack connector's own examples are questions like what the team decided in a channel last week, and the Google Workspace connectors cite their sources, so each item links back. Ranking by who is blocked puts the cost of your absence first. Connectors inherit your permissions, so Claude sees only what you can, and a read-only run sends nothing before you review it.
