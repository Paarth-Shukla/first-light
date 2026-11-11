---
id: claude-in-google-workspace
title: Claude for Google Workspace
surface: integrations
group: Google Workspace
status: beta
level: starter
payoff: 3
effort: 1
jobs: [writing, analysis, review, meetings]
tags: [google-docs, google-sheets, google-slides, sidebar, add-on]
summary: Claude for Google Workspace adds a Claude sidebar to Google Docs, Sheets and Slides that reads the file you have open and edits it in place.
when: Use it when you are already in a Google file and want Claude to work on that file. The Google Workspace connectors work the other way round, bringing Drive, Gmail and Calendar into a chat at claude.ai.
replaces: Copying a document or a range of cells into chat and pasting the rewritten version back.
example_kind: prompt
docs:
  - title: Use Claude in Google Docs, Sheets, and Slides
    url: https://support.claude.com/en/articles/16951679-use-claude-in-google-docs-sheets-and-slides
verified: 2026-11-11
---
## Try it in a minute
1. Install Claude from the [Google Workspace Marketplace listing](https://workspace.google.com/marketplace/app/claude/12459801340) by clicking **Install**. One install covers Docs, Sheets and Slides.
2. Open or reload a Google Docs, Sheets or Slides file and go to Extensions > Claude > **Open Claude**.
3. Allow the two permissions Google asks for, then sign in with your Claude account in the sidebar.
4. Select text, cells or a slide to point Claude at a specific part, and ask for the outcome you want.
5. Leave the mode selector on **Ask before edits** to approve each change, and keep the sidebar open until Claude finishes.

## Example
```text
Column D has dates in three different formats. Normalize them to YYYY-MM-DD.

Then add a tab called Summary that counts open issues per component using formulas, and a chart of issues opened per week. Walk me through how each total is calculated and flag anything hardcoded.
```

## At work
- **Tightening a design doc.** In Docs, ask Claude to cut a long brief without losing its numbered requirements.
- **Fixing spreadsheets.** In Sheets, ask why a VLOOKUP returns #N/A for some rows and have it fixed.

## Pitfalls
- It is in beta, and your Google account must be allowed to install Google Workspace Marketplace apps.
- Edits are recorded under your name in version history. Undo, or restore an earlier version, to revert.
- Claude only sees the open file, plus any connectors you turn on.
- In Docs it cannot read, reply to or resolve comments, and its edits are direct edits, not suggestions.
- Charts Claude creates in Slides are images that do not update when numbers change.
- It does not work in Word, Excel or PowerPoint files opened in Google, or in Firefox.
- Review proposed actions in files from outside your organization.
