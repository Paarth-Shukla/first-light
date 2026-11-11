---
id: slack-connector
title: Slack connector
surface: integrations
group: Slack
status: stable
level: starter
payoff: 2
effort: 2
jobs: [research, meetings, planning]
tags: [slack, connector, search, context]
summary: The Slack connector lets Claude in claude.ai search your Slack workspace's channels, direct messages and files to answer your questions.
when: Use it when a decision or its history lives in Slack threads and you want it as context in a Claude chat. To have Claude work inside Slack channels, the current product is Claude Tag.
replaces: Scrolling and searching Slack for the thread where something was decided, then pasting it into chat.
example_kind: prompt
docs:
  - title: Slack integration
    url: https://claude.com/docs/connectors/slack/index
  - title: Use connectors to extend Claude's capabilities
    url: https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities
verified: 2026-11-11
---
## Try it in a minute
1. An Owner enables the Slack connector in **Organization settings > Connectors** in claude.ai. The Claude app must be installed in the Slack workspace first.
2. Go to [Customize > Connectors](https://claude.ai/customize/connectors), find **Slack** and select **Connect**. The button changes to **Disconnect** when it succeeds.
3. In a conversation, select **+** at the lower left of the message box, select **Connectors** and turn on **Slack**.
4. Ask a question about something discussed in your workspace.

## Example
```text
Find the thread in #storage-platform about moving the nightly scrub window, and any related discussion in #oncall from the last month.

Summarize what was decided, who objected and why, and what is still unresolved. Quote the two messages that state the decision. Then draft a short Confluence-style decision record I can paste into our wiki.
```

## At work
- **Decision archaeology.** The docs' own examples are asking what the team decided about a date in a channel last week, and finding and summarizing a specific thread.
- **Catch-up after time off.** Ask for what changed in the channels you care about, with the threads that need your reply.

## Pitfalls
- The connector is available on Team and Enterprise plans and requires the app to be installed first.
- Each member connects their own account after the Owner enables it. Claude can only reach what you can access in Slack.
- The connector and the Slack app are disconnected separately, the connector from **Customize > Connectors** and the app from its **Home** tab in Slack.
- The docs page describes the earlier per-user Claude in Slack app alongside the connector. The current in-Slack product is Claude Tag.
- Disconnecting removes your account connection and deletes past conversations within 30 days.
