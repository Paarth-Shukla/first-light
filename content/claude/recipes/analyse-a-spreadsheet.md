---
id: analyse-a-spreadsheet
title: Analyse a CSV export and get charts and findings
job: analysis
level: starter
minutes_saved: 45
features: [file-creation, claude-sheets]
prerequisites: [Code execution and file creation turned on, A CSV or TSV export of 30MB or less]
fields:
  - name: what_it_is
    label: What the file contains
    placeholder: one row per support ticket for the last two quarters, exported from Jira
  - name: question
    label: The question to answer
    placeholder: which components drive the rise in P1 tickets, and whether time to resolve is getting worse
  - name: audience
    label: Who the findings are for
    placeholder: the engineering managers at Thursday's planning meeting
  - name: decision
    label: What they will decide
    placeholder: where to put two extra engineers next quarter
docs:
  - title: Create and edit files with Claude
    url: https://support.claude.com/en/articles/12111783-create-and-edit-files-with-claude
  - title: Get started with Claude Sheets
    url: https://support.claude.com/en/articles/18324300-get-started-with-claude-sheets
verified: 2026-11-11
---
## Steps
1. Check that **Code execution and file creation** is on in **Settings > Capabilities** (called **Create and edit files** in the updated Settings layout). On Team and Enterprise plans an owner controls it.
2. Attach the CSV to a new chat. Uploads are limited to 30MB per file.
3. Send the prompt below. Claude writes and runs Python and returns charts as PNG files.
4. Read the profiling step first. If a cleaning decision is wrong, say so and ask Claude to rerun.
5. For a version the team can edit, ask for a Claude Sheets sheet built from the cleaned data. Sheets is in beta on paid plans.

## Prompt
```text
The attached file is {{what_it_is}}. I need to answer this question: {{question}}. The findings go to {{audience}}, who will use them to decide {{decision}}, so every number has to survive someone checking it.

Work in this order:
1. Profile the data: row count, columns and types, date range, missing values, duplicates, and values that look like parsing or unit errors. Tell me what you will clean and why, then clean it.
2. Write and run Python to answer the question. Make at most four charts as PNG files, each answering one sub-question, with labelled axes and units.
3. For each finding, give the number, how you computed it, and how far the sample size lets us trust it. Say when a pattern is a correlation this data cannot explain.
4. Create an Excel workbook with the cleaned data on one sheet and a summary sheet built with formulas, so each number in the findings traces back to cells.
```

## Why it works
The file creation guide says to describe the structure, content and formatting you want, and to review the output. Profiling first shows you the cleaning decisions while a wrong one is cheap to fix. A workbook with working formulas lets the audience audit each figure, and naming the decision tells Claude which numbers matter.
