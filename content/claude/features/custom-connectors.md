---
id: custom-connectors
title: Custom connectors (remote MCP)
surface: apps
group: Extend
status: stable
level: power
payoff: 3
effort: 3
jobs: [automation, coding, analysis]
tags: [mcp, connectors, internal-tools, oauth]
summary: A custom connector links Claude to any remote MCP server by its URL, including one you build for an internal tool.
when: Use one when the service you need is not in the Connectors Directory, or when you want Claude to reach an internal system through an MCP server your team hosts.
replaces: Writing one-off scripts to dump internal data into files that you then upload to Claude.
example_kind: config
docs:
  - title: Get started with custom connectors using remote MCP
    url: https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp
  - title: Add a connector that isn't in the directory
    url: https://claude.com/docs/connectors/custom/add-unlisted
verified: 2026-11-11
---
## Try it in a minute
1. Go to [Customize > Connectors](https://claude.ai/customize/connectors). Select **Add**, then **Add custom connector**. On Team and Enterprise plans an Owner does this in **Organization settings > Connectors** instead.
2. Enter a name and the remote MCP server URL, then click **Continue**.
3. Keep the authentication options marked **Detected** unless the server's documentation says otherwise, then click **Add**.
4. If the connector shows **Connect**, click it and sign in.
5. In a chat, click **+**, select **Connectors**, and turn the connector on for that conversation.

## Example
```text
Name:            Build Farm
MCP server URL:  https://mcp.example.com/mcp
Authentication:  Sign in now            (or "Sign in when needed" or "No sign-in")
OAuth client:    Use Claude's published identity
Request headers: only for a fixed credential such as an API key, for example
                 x-api-key = the key exactly as your server expects it, marked Required
```

## At work
- **Internal systems.** Put an MCP server in front of your build farm, test results or capacity database and ask questions about them from chat, Cowork or Claude Desktop.
- **Team-wide access.** An Owner adds the connector once and each member clicks **Connect** to authenticate.
- **Service accounts.** Request headers suit services where everyone shares one credential, such as an internal tool.

## Pitfalls
- Claude connects from Anthropic's cloud, not from your machine, on every client. A server behind a VPN or firewall will not connect unless you allowlist Anthropic's IP ranges or use an MCP tunnel.
- Connect only to servers you trust and review the permission scopes requested.
- Malicious servers may include hidden instructions. Only click **Always allow** for trusted servers.
- You cannot change authentication settings after adding. Remove the connector and add it again.
- Request header authentication is in beta for a limited set of organizations, and you can add up to four headers.
- Free accounts are limited to one custom connector.
