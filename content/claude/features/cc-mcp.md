---
id: cc-mcp
title: MCP servers
surface: code
group: Extend
status: stable
level: intermediate
payoff: 3
effort: 2
jobs: [coding, debugging, planning, automation]
tags: [mcp, connectors, jira, integrations, tools]
summary: MCP servers give Claude Code tools beyond its built-in set, such as searching an issue tracker, querying a database or reading a monitoring dashboard.
when: Connect a server when you find yourself copying data into the chat from another tool, so Claude can read and act on that system directly.
replaces: Pasting ticket text, stack traces and query results into the prompt.
example_kind: command
docs:
  - title: Connect to MCP servers
    url: https://code.claude.com/docs/en/mcp-quickstart
  - title: Connect Claude Code to tools via MCP
    url: https://code.claude.com/docs/en/mcp
verified: 2026-11-11
---
## Try it in a minute
1. In your terminal, not inside a session, run `claude mcp add --transport http claude-code-docs https://code.claude.com/docs/mcp`. This hosted docs server needs no sign-in.
2. Run `claude mcp list` and look for `Connected`.
3. Start `claude` and ask `Use the claude-code-docs server to look up what MCP_TIMEOUT does`.
4. Remove it with `claude mcp remove claude-code-docs` when you are done.

## Example
A hosted service with browser sign-in, using the docs' Sentry example:

```bash
claude mcp add --transport http sentry https://mcp.sentry.dev/mcp
claude mcp list        # shows "! Needs authentication" until you sign in
claude                 # then run /mcp, select sentry, choose Authenticate
```

## At work
- **Tickets to code.** With an issue tracker connected, the docs example prompt is `Add the feature described in JIRA issue ENG-4521 and create a PR on GitHub.`
- **Connectors you already have.** If you log in with a claude.ai account, connectors added at claude.ai/customize/connectors appear in `/mcp` automatically.
- **One config for the team.** `claude mcp add --scope project ...` writes `.mcp.json` in the project root. Commit it, and teammates are prompted to approve the server.

## Pitfalls
- Verify that you trust a server before connecting it. Servers that fetch external content can expose you to prompt injection.
- By default a server is added at `local` scope, which is only you in this project. Use `--scope user` for all your projects. Changing scope means removing and re-adding.
- Each connected server takes context space for its tool names and instructions. Remove or disable ones you do not use.
- claude.ai connectors are not loaded when an API key or a third-party provider is the active authentication.
- On Team and Enterprise plans, only admins can add connectors in claude.ai.
