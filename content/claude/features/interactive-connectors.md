---
id: interactive-connectors
title: Interactive connectors
surface: apps
group: Extend
status: stable
level: starter
payoff: 2
effort: 1
jobs: [planning, meetings, analysis]
tags: [connectors, mcp-apps, dashboards, boards]
summary: Some connectors can display live, interactive apps inside a Claude conversation, such as a task board or analytics dashboard, instead of a text-only reply.
when: Use one when you want to see and adjust the real thing while you talk about it, rather than read a description and switch tabs to act on it.
replaces: Asking Claude for a summary, then opening the tool in another tab to make the change yourself.
example_kind: prompt
docs:
  - title: Use interactive connectors in Claude
    url: https://support.claude.com/en/articles/13454812-use-interactive-connectors-in-claude
verified: 2026-11-11
---
## Try it in a minute
1. Open the [Connectors Directory](https://claude.ai/directory) and look for connectors marked with the **Interactive** badge.
2. Connect and authenticate with one. No additional setup is needed.
3. Start a conversation and ask about something that connector handles. The interactive view appears automatically when relevant.
4. Work in the view directly, for example filter data or check off a task, or ask Claude to make the change.

## Example
```text
Draft a Slack message for the #storage-oncall channel summarizing last night's incident:
- what paged, when, and for how long
- customer impact in one sentence
- the mitigation we applied
- the follow-up ticket link placeholder

Keep it under 120 words. Show me the draft so I can edit it before it is sent.
```

## At work
- **Review before sending.** Inline cards suit single actions such as a message draft ready to send.
- **Boards and dashboards in the chat.** Ask about project status and the task board opens in the conversation, where you can check off tasks.
- **Keep a view open.** The side panel keeps the connector open beside your chat so you can watch it update, and supported connectors can be pinned to your sidebar.

## Pitfalls
- What you see varies by connector. Each developer chooses which views and actions to support, and Claude can only take actions the developer has made available.
- The side panel, full-site views and pinning are rolling out on the web and in Claude Desktop to accounts with the new Claude experience. They are not on Claude Mobile yet.
- Pins are saved per browser, so a pin added on the web does not appear in Claude Desktop.
- Purchases through a connector's in-chat views are not supported.
- Team and Enterprise owners can disable the tool calls that render interactive views. The connector's text-based tools keep working.
