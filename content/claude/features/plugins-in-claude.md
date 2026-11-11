---
id: plugins-in-claude
title: Plugins in Claude
surface: apps
group: Extend
status: stable
level: intermediate
payoff: 2
effort: 2
jobs: [automation, planning, analysis]
tags: [plugins, skills, connectors, marketplace]
summary: A plugin packages skills, MCP connectors, commands and agents so you can add them to Claude as one unit that follows your account across chat, Cowork and Claude Code.
when: Add a plugin when you want a ready-made setup for a role or tool, or want your team's skills and connectors installed and shared together. Add a single skill or connector on its own when that is all you need.
replaces: Installing and configuring each skill and connector separately on every surface you use.
example_kind: prompt
docs:
  - title: Plugins
    url: https://claude.com/docs/plugins/overview
  - title: Use plugins in Claude
    url: https://support.claude.com/en/articles/13837440-use-plugins-in-claude
  - title: Connectors, skills, and plugins
    url: https://claude.com/docs/extend/overview
verified: 2026-11-11
---
## Try it in a minute
1. Open [Customize > Plugins](https://claude.ai/customize/plugins) and select **Discover**.
2. Select a plugin to read what it contains, then select **Add**.
3. Open the plugin's **Connectors** tab and connect any connector that shows **Not connected** or **Not added**.
4. In a chat, type `/` in the message box, type the plugin's name to narrow the list, and select a skill.
5. If it does not help, turn it off with its **Disable plugin** toggle or select **Remove** from its menu.

## Example
In Cowork, run a plugin's command by name (these names are placeholders):

```text
/engineering:standup

Use my calendar and issue tracker connectors. Cover yesterday, today and blockers, and keep it under 120 words so I can paste it into the team channel.
```

## At work
- **Role setups.** Anthropic-built plugins cover functions including engineering, data analysis and operations, each with the relevant skills and connectors.
- **Team standard.** Use **Add > Add marketplace** with a Git repository of your team's plugins.
- **One install, three surfaces.** A plugin added in claude.ai loads into your Cowork tasks and syncs to Claude Code when you sign in with the same account.

## Pitfalls
- Adding a plugin does not add a connector or sign you in to anything. Skills that use a connector cannot reach the service until it shows **Connected**.
- Chat only uses a plugin's skills, commands and connectors. Agents and hooks run in Cowork and Claude Code.
- Anthropic's review covers plugins listed in the directory, not ones you add from a marketplace URL or upload yourself. Add those only from sources you trust.
- Plugins may include local MCP servers that run on your computer with the same permissions as any other program you run.
- On Team and Enterprise plans an Owner controls which sources you see. Required plugins cannot be turned off.
