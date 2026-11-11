---
id: file-creation
title: Create and edit files
surface: apps
group: Make things
status: stable
level: starter
payoff: 3
effort: 1
jobs: [analysis, writing, automation]
tags: [files, excel, powerpoint, pdf, code-execution]
summary: Claude can run code in a sandboxed computing environment to create and edit real files in a chat, including Excel, PowerPoint, Word and PDF.
when: Use it when you need a downloadable file or an analysis of an uploaded CSV, not text to paste somewhere. For a living document you will keep editing in Claude, use an artifact template instead.
replaces: Building the spreadsheet, chart or slide deck by hand from numbers Claude gave you in chat.
example_kind: prompt
docs:
  - title: Create and edit files with Claude
    url: https://support.claude.com/en/articles/12111783-create-and-edit-files-with-claude
verified: 2026-11-11
---
## Try it in a minute
1. Go to **Settings > Capabilities** and turn on **Code execution and file creation** (called **Create and edit files** in the updated Settings layout). On Team and Enterprise plans an owner controls this in **Organization settings > Capabilities**.
2. Upload a data file such as a CSV, or describe what you need from scratch.
3. Ask for a specific file type and describe the structure, content and formatting you want.
4. Download the file from the conversation, or save it to Google Drive.

## Example
```text
Using the attached CSV of last quarter's on-call pages, create an Excel workbook with:
- a cleaned data sheet (one row per page, parsed timestamps, service, severity, time to acknowledge)
- a pivot-style summary by service and week, built with formulas rather than pasted values
- a chart of pages per week
Then write a one-page Word summary of the three noisiest alerts and what you would change about each.
```

## At work
- **Reports from raw exports.** Turn a Jira or monitoring CSV export into a workbook with working formulas and a chart.
- **Format conversion.** Convert a document into a PowerPoint presentation, or extract the tables in a PDF into a spreadsheet.
- **Quick data science.** Claude can write and run Python for analysis and produce visualizations as PNG files.

## Pitfalls
- The maximum file size is 30MB per file for both uploads and downloads.
- Creating files uses more of your usage limit than normal chat.
- On Team and Enterprise plans network access for the sandbox is off or restricted by default, so package installs beyond what is pre-installed may be limited.
- Instructions hidden in external files or websites could trick Claude into leaking data from its context, so monitor what it does.
- Review the output. You may need to refine it.
