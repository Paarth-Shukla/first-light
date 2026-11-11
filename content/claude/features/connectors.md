---
id: connectors
title: Connectors
surface: apps
group: Extend
status: stable
level: starter
payoff: 3
effort: 2
jobs: [research, planning, automation, meetings]
tags: [connectors, mcp, integrations, permissions]
summary: Connectors let Claude access your apps and services, retrieve your data and take actions in them, using the permissions you already have there.
when: Connect a service when you keep copying its content into Claude or carrying Claude's output back to it. One connection replaces every future copy and paste for that tool.
replaces: Exporting tickets, emails and documents by hand so Claude can read them, then re-entering the result in the source system.
example_kind: prompt
docs:
  - title: Use connectors to extend Claude's capabilities
    url: https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities
  - title: Get started with connectors
    url: https://claude.com/docs/connectors/getting-started
  - title: Connectors directory
    url: https://claude.com/docs/connectors/directory
verified: 2026-11-11
---
## Try it in a minute
1. Go to [Customize > Connectors](https://claude.ai/customize/connectors), select **Discover**, and search for a service you use.
2. Open its page, select **Connect to Claude**, sign in to the service and approve the access it asks for.
3. In a chat, select **+** in the message box, then **Connectors**, and make sure the connector's toggle is on.
4. Ask for something the service holds. When Claude asks to use a tool, select **Allow once** or **Always allow**.

## Example
```text
Summarize the open issues assigned to me, grouped by epic.

For each one give the key, a one-line status, and what is blocking it. Flag anything untouched for more than two weeks. Then draft a comment for the three stalest issues asking the reporter whether it is still needed. Show me the drafts before posting anything.
```

## At work
- **Standup and status prep.** Claude reads your tracker and calendar directly, so a weekly status draft starts from real data instead of memory.
- **Acting, not only reading.** The docs' own example is asking Claude to "Create a new issue for the login bug" after connecting an issue tracker.
- **Same connectors everywhere.** Connectors you add in claude.ai are available in Claude Code when you sign in with your Claude account.

## Pitfalls
- Connecting grants Claude permission to access and potentially modify data based on your account permissions. Only connect services you trust and need.
- On Team and Enterprise plans an Owner must add the connector for the organization before members can connect.
- Verification of a directory connector is not a security audit.
- Many active connectors take up room in the conversation. With 10 or more, the docs suggest switching **Tool access** from **Auto** to **On demand**.
- Turning a toggle off in a chat does not sign Claude out. Use **Disconnect** for that.
