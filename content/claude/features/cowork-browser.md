---
id: cowork-browser
title: Built-in browser in Cowork
surface: cowork
group: Delegate
status: stable
level: intermediate
payoff: 2
effort: 2
jobs: [automation, research, analysis]
tags: [cowork, browser, web, forms, desktop]
summary: Cowork has a browser built into the Claude Desktop app, which opens in a side panel so Claude can open sites, read pages, click, type and fill forms as part of a task.
when: Use it to hand off the web part of a task and keep working, with nothing to install and without touching your own tabs or logins. Use Claude in Chrome when the work is on a page already in front of you.
replaces: Clicking through a web console or vendor portal yourself to collect what a task needs.
example_kind: prompt
docs:
  - title: Use the built-in browser in Claude Cowork
    url: https://support.claude.com/en/articles/16607400-use-the-built-in-browser-in-claude-cowork
  - title: Get started with Claude Cowork
    url: https://support.claude.com/en/articles/13345190-get-started-with-claude-cowork
verified: 2026-11-11
---
## Try it in a minute
1. Open the Claude Desktop app and start a Cowork task that involves a website. The browser opens in the side panel next to your task.
2. The first time, decide whether to click **Import cookies** to bring over saved logins site by site, or sign in to sites as you go.
3. Watch Claude work in the panel and stop the task if something looks off.
4. To change the default, go to **Settings > Cowork** and set **Preferred browser** to **Built-in browser** or **Chrome (Claude in Chrome)**.

## Example
```text
Using the built-in browser, go to the public documentation sites for the three NVMe drive vendors listed in vendors.md in my connected folder.

For each drive model in the file, find the firmware release notes page and record the latest version, release date and any fixed issue that mentions power loss. Put the result in a spreadsheet with a link to each source page. Do not sign in anywhere.
```

## At work
- **Sites without a connector.** Gather release notes or status pages into a spreadsheet while you do something else.
- **Steering remotely.** A task started on desktop can be steered from the web or mobile as long as the desktop app stays open.

## Pitfalls
- Claude Desktop must be open and online for Claude to use the built-in browser, even though the session runs in the cloud.
- Anything you sign in to inside the built-in browser is available to Claude in future Cowork sessions on that computer.
- Cookie import is not available from Safari. Banking, email and single sign-on sites stay unchecked by default.
- Web pages can contain hidden instructions (prompt injection). Safeguards reduce the risk but cannot remove it.
- Anthropic strongly advises against using it for financial accounts, medical information or other people's personal data.
