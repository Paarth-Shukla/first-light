---
id: artifacts
title: Artifacts
surface: apps
group: Make things
status: stable
level: starter
payoff: 3
effort: 1
jobs: [writing, analysis, planning, coding]
tags: [artifacts, templates, dashboards, sharing, export]
summary: An artifact is a finished piece of work, such as a document, deck, design, dashboard or small interactive tool, that opens beside the chat where you can edit, share and export it.
when: Ask for an artifact when the answer is something you will put in front of other people or come back to, rather than a reply you read once.
replaces: Copying chat output into a separate editor and reformatting it before anyone else can see it.
example_kind: prompt
docs:
  - title: What are artifacts and how do I use them?
    url: https://support.claude.com/en/articles/17153992-what-are-artifacts-and-how-do-i-use-them
  - title: Share artifacts
    url: https://support.claude.com/en/articles/9547008-share-artifacts
verified: 2026-11-11
---
## Try it in a minute
1. In **Settings > Capabilities**, check that **Cloud code execution and file creation** is on (it is called **Create and edit files** in the updated Settings layout).
2. Ask for an artifact in any chat, or select **Output** in the message box and choose a template, or pick one in the **Artifacts** tab.
3. Change it by asking Claude, or edit directly in an artifact made from a template. In a doc, highlight text, click **Edit with Claude** and type the change.
4. In an artifact made from a template, click **Export** when it is ready. Everything you make is saved in the **Artifacts** tab.

## Example
```text
Build a small interactive tool as an artifact: a capacity calculator for a storage array.

Inputs: raw capacity in TB, RAID overhead percent, expected data reduction ratio, monthly growth percent.
Outputs: usable capacity today, effective capacity after data reduction, and the month we cross 80 percent full.
Chart projected usage over 24 months and update it when I change an input.
```

## At work
- **Small internal tools.** A calculator or a triage checklist is ready in one prompt and, on paid plans, shareable by link.
- **Trackers that keep state.** On paid plans an artifact can store data between sessions, in personal or shared storage.
- **Live views of your tools.** On paid plans an artifact can read from and write to apps you have connected to Claude. Each person who opens it connects their own apps.

## Pitfalls
- Artifacts start private to you until you share them.
- Storage is limited to 20 MB per artifact and text only. Check whether an artifact uses shared storage before entering anything sensitive.
- Connector tools that need approval for each action are not available to artifacts.
- Only build on a published artifact from someone you trust.
