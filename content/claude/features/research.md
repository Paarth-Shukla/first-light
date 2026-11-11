---
id: research
title: Research
surface: apps
group: Find and reason
status: stable
level: starter
payoff: 3
effort: 1
jobs: [research, analysis, planning]
tags: [research, citations, web, connectors]
summary: Research makes Claude investigate a question in depth, running many searches that build on each other across the web and your connected tools, then writing a cited report.
when: Use it for comprehensive information gathering that needs five or more lookups, such as a vendor comparison or a technology survey. For a quick fact, plain web search is enough.
replaces: An afternoon of opening tabs, skimming sources and pasting notes into a comparison document.
example_kind: prompt
docs:
  - title: Use research on Claude
    url: https://support.claude.com/en/articles/11088861-use-research-on-claude
  - title: When should I use web search, extended thinking, and research?
    url: https://support.claude.com/en/articles/11095361-when-should-i-use-web-search-extended-thinking-and-research
verified: 2026-11-11
---
## Try it in a minute
1. Make sure web search is turned on. Research does not work without it.
2. Click the **+** button at the bottom left of the chat box, then **Research**. A blue indicator appears at the bottom of the chat window.
3. Ask your question and say what the report should cover.
4. Read the report and open the citations for anything you will act on.
5. Click the indicator again to turn research off.

## Example
```text
Use the research tool to compare erasure coding and three-way replication for an object store serving mostly cold data.

Cover: storage overhead, rebuild time after a disk failure, read latency, and operational complexity.
Prefer vendor engineering blogs, conference papers and official documentation from the last three years.
Pull relevant context from our design docs in Google Docs.
End with a one-page recommendation and a table of sources.
```

## At work
- **Design doc background.** Get a cited survey of prior art before you write the "alternatives considered" section.
- **Internal plus external.** On the web or Claude Desktop, research also searches connectors you have turned on for the chat, such as Google Workspace.
- **Refreshing stale pages.** The docs give updating outdated internal documents with information from the web as a fit.

## Pitfalls
- Research is for paid plans.
- Started from Claude Mobile, research only searches the web and skips your connectors with no error or warning.
- It cannot use tools from local MCP servers configured in Claude Desktop.
- During research Claude uses connector tools automatically, without asking for approval each time.
- It can use up your usage limits faster than normal chats.
- Research runs on its own model no matter which model you picked for the chat.
- If Claude does not start researching, say "please use the research tool to..." in your prompt.
