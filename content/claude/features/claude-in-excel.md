---
id: claude-in-excel
title: Claude for Excel
surface: integrations
group: Microsoft 365
status: stable
level: starter
payoff: 3
effort: 1
jobs: [analysis, debugging, planning]
tags: [excel, add-in, formulas, spreadsheets, microsoft-365]
summary: Claude for Excel is an add-in that brings Claude into Excel so it can answer questions about the open workbook with cell-level citations, edit values while keeping formulas intact, and debug errors.
when: Use it when the workbook already lives in Excel and you need Claude to read and change the real cells. For a new light tracker you can build Claude Sheets instead, and for a one-off file the chat can create an .xlsx.
replaces: Tracing precedents cell by cell to find where a number comes from or why a formula returns an error.
example_kind: prompt
docs:
  - title: Use Claude for Excel
    url: https://claude.com/docs/office-agents/excel
  - title: Claude for M365 overview
    url: https://claude.com/docs/office-agents/overview
  - title: Connectors and Skills
    url: https://claude.com/docs/office-agents/connectors-and-skills
verified: 2026-11-11
---
## Try it in a minute
1. Go to the Claude for Microsoft 365 listing on Microsoft AppSource and select **Get it now**.
2. Open Excel, activate the add-in (Tools, Add-ins on Mac or Home, Add-ins on Windows) and sign in with your Claude account.
3. Open a workbook you trust and ask a question about it. Click a cell citation in the answer to jump to that cell.
4. Ask for a specific change and review the result before you save.
5. Open Settings in the add-in sidebar and use the **Instructions** field for conventions that should apply to every conversation in Excel.

## Example
```text
This workbook is our capacity forecast. Walk me through how the "months until 80% full" number on the Summary tab is calculated, citing each cell it depends on.

Then trace why row 14 on the Sites tab returns #DIV/0 and suggest a fix. Finally, change the growth assumption from 3% to 4.5% per month and tell me which summary cells changed and by how much.
```

## At work
- **Understanding an inherited model.** Ask Claude to trace assumptions and explain formulas, with citations you can click.
- **What-if analysis.** Claude updates input values while keeping formula relationships intact, so downstream cells recompute.
- **Clean-up chores.** It can sort, filter, edit pivot tables, apply conditional formatting and create data validation dropdowns on request.

## Pitfalls
- Data tables, macros and VBA operations are not supported.
- It does not run on Excel 2016 or 2019 perpetual licenses, Excel on iPad or Excel on Android.
- Only use it with trusted spreadsheets. Files from external sources can contain hidden instructions.
- It is not recommended for audit-critical calculations without verification.
- Chat history is stored locally in your browser and is not synced across devices.
- Usage counts against the same limits as your Claude account.
