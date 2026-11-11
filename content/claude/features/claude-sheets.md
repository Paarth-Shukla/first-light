---
id: claude-sheets
title: Claude Sheets
surface: apps
group: Make things
status: beta
level: starter
payoff: 2
effort: 1
jobs: [analysis, planning]
tags: [sheets, spreadsheets, artifacts, formulas, trackers]
summary: Claude Sheets is a spreadsheet built into Claude, where you and Claude edit the same cells and formulas stay visible in the cells.
when: Use it for a light, shared tracker, budget or model you build with Claude. When the file already lives in Excel or Google Sheets, or you need those apps' full features, use Claude for Excel or Claude for Google Workspace instead.
replaces: Asking Claude for a table, pasting it into a spreadsheet and rebuilding the formulas yourself.
example_kind: prompt
docs:
  - title: Get started with Claude Sheets
    url: https://support.claude.com/en/articles/18324300-get-started-with-claude-sheets
  - title: What are artifacts and how do I use them?
    url: https://support.claude.com/en/articles/17153992-what-are-artifacts-and-how-do-i-use-them
verified: 2026-11-11
---
## Try it in a minute
1. Ask Claude for a sheet in any chat, or go to the **Artifacts** tab and select the **Sheets** tile.
2. Say what the sheet is for and what you want to track. Give Claude your numbers if you have them.
3. Ask for changes such as "Add a column for budget remaining" or "Highlight anything that's overdue."
4. Click **Share** to work on it with others, or export it as an .xlsx or CSV file.

## Example
```text
Build a sheet to track the firmware qualification matrix.

One row per drive model, one column per firmware version, with a status dropdown (Not started, Running, Passed, Failed) in each cell. Add a summary tab that counts each status per firmware version using formulas, and conditional formatting that turns Failed cells red.
```

## At work
- **Trackers you can audit.** Formulas stay in the cells, so you can check how each number was calculated, and each edit Claude makes is outlined as it lands.
- **Starting from an export.** Import a CSV file, or import from Google Sheets or Excel, then ask Claude to add the columns and summaries you need.
- **Asking about numbers.** Select cells and ask a question such as "Why is this total higher than last month?"

## Pitfalls
- Claude Sheets is in beta on paid plans, and on Enterprise plans it is off until an owner turns it on.
- A sheet can hold up to 100,000 cells.
- Not available yet: pivot tables, protected ranges, find and replace, multi-column sort, filter views and PDF export.
- Excel macros, VBA, Power Query, DAX and print layout are not supported.
- Sheets cannot pull live data from connected apps.
- Restoring an earlier version from version history also removes edits made after it.
- Mobile has basic read-only access.
