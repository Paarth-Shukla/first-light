---
id: cc-artifacts
title: Artifacts from a session
surface: code
group: Workflows
status: new
since: 2026-06
level: intermediate
payoff: 2
effort: 1
jobs: [review, analysis, writing, planning]
tags: [artifacts, sharing, dashboards, reports, visual]
summary: An artifact is a live, interactive web page that Claude Code publishes from your session to a private URL on claude.ai and updates in place as the work continues.
when: Ask for one when terminal text is the wrong medium, such as an annotated diff walk-through, a chart or options to compare, and when you would otherwise paste output into a chat for a teammate.
replaces: Screenshots of terminal output and long pasted summaries in Slack.
example_kind: prompt
docs:
  - title: Share session output as artifacts
    url: https://code.claude.com/docs/en/artifacts
  - title: What's new
    url: https://code.claude.com/docs/en/whats-new
verified: 2026-11-11
---
## Try it in a minute
1. In a session signed in with `/login`, ask for an artifact, as in the example below.
2. Claude prints the URL and your browser opens the page. It is private to you.
3. Ask Claude to revise it, for example `Add a per-region breakdown below the summary chart and republish`. The same URL updates.
4. Use the **Share** control in the page header when you want someone else to see it.

## Example
```text
Make an artifact that walks a reviewer through this branch. Show the three riskiest changes with the diff annotated inline, a table of tests added per module, and the open questions. Keep it updated as you address review comments.
```

## At work
- **Pull request walk-throughs.** Reviewers get annotated diffs on one page instead of a long description.
- **Investigations.** A timeline or dashboard fills in while a long task runs, and anyone with the page open sees each update.
- **Status boards.** A published page can pull fresh data through each viewer's MCP connectors when it is opened.

## Pitfalls
- The docs list artifacts for Pro, Max, Ultra, Team and Enterprise plans, with a claude.ai sign-in. Sessions using an API key or a cloud provider cannot publish.
- An artifact is one self-contained static page with no backend. It cannot serve multiple routes or authenticate viewers itself.
- The rendered page must be 16 MiB or smaller.
- A styled page uses more output tokens than the same content as terminal text.
- Sharing within your organization is for Team and Enterprise plans, and public sharing there is off until an Owner enables it.
- Artifacts are off by default in `-p` runs, the Agent SDK and the GitHub Action.
