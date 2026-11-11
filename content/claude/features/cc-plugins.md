---
id: cc-plugins
title: Plugins and marketplaces
surface: code
group: Extend
status: stable
level: intermediate
payoff: 2
effort: 1
jobs: [coding, automation, review]
tags: [plugins, marketplace, sharing, team-setup]
summary: A plugin is a directory of skills, agents, hooks and MCP servers that Claude Code installs and loads as one unit, usually from a marketplace.
when: Install a plugin to get a setup someone else built with one command, and make one when you want to hand several skills, hooks or servers to teammates as a versioned package.
replaces: Copying skill folders, hook scripts and server configs between repositories and teammates by hand.
example_kind: command
docs:
  - title: Plugins overview
    url: https://code.claude.com/docs/en/plugins/overview
  - title: Install and manage plugins
    url: https://code.claude.com/docs/en/plugins/install
verified: 2026-11-11
---
## Try it in a minute
1. In a terminal session, run `/plugin` to browse the **Discover** tab, or run the install command below.
2. Read the details pane. **Will install** lists the commands, agents, skills, hooks and servers the plugin adds.
3. Choose a scope. User scope is for you in every project, project scope is for everyone in the repository, local scope is for you in this repository.
4. Type `/` and look for the plugin's skills as `/<plugin>:<skill>`, for example `/commit-commands:commit`.

## Example
```text
/plugin install commit-commands@claude-plugins-official
```

## At work
- **One setup for the team.** Install at project scope so the plugin entry lands in `.claude/settings.json`, which you commit.
- **An internal catalog.** A marketplace is a repository with a `.claude-plugin/marketplace.json` file. Add yours with `/plugin marketplace add` followed by a GitHub `owner/repo`, a full git URL or a local path.
- **Housekeeping.** The **Installed** tab lets you disable, update or uninstall, and `claude plugin list` prints the same list from your shell.

## Pitfalls
- An enabled plugin is part of every session. The names and descriptions of its skills and agents sit in context on every turn.
- A plugin can run hooks and MCP servers, and what it runs, it runs as you. Read the details pane before installing.
- Committing a project-scope entry turns the plugin on for collaborators but does not download it. Each runs `claude plugin install <name>@<marketplace> --scope project` once per clone.
- Cloud sessions do not load plugins you installed on your own machine.
- A plugin marketplace is not the Claude Marketplace website, which you cannot add with `/plugin marketplace add`.
- Write git URLs with `https://`. A bare `gitlab.example.com/your-group/your-marketplace.git` is read as GitHub `owner/repo` shorthand and rejected.
