---
id: triage-a-jira-backlog
title: Triage and summarise a Jira backlog
job: planning
level: intermediate
minutes_saved: 45
features: [connectors, file-creation]
prerequisites: [A connector for your issue tracker connected in Customize > Connectors, Code execution and file creation turned on]
fields:
  - name: project_key
    label: Tracker project
    placeholder: STOR
  - name: filter
    label: Which issues are in scope
    placeholder: open issues not in a sprint that were created more than 30 days ago
  - name: team_context
    label: What the team is focused on
    placeholder: we own replication and snapshots and this quarter is about restore reliability
  - name: capacity
    label: Capacity for the next sprint
    placeholder: 12 issues
  - name: stale_after
    label: When an issue counts as stale
    placeholder: 180 days
docs:
  - title: Use connectors to extend Claude's capabilities
    url: https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities
  - title: Get started with connectors
    url: https://claude.com/docs/connectors/getting-started
  - title: Create and edit files with Claude
    url: https://support.claude.com/en/articles/12111783-create-and-edit-files-with-claude
verified: 2026-11-11
---
## Steps
1. In **Settings > Capabilities**, check that **Code execution and file creation** is on (called **Create and edit files** in the updated Settings layout).
2. In a new chat, click **+**, hover over **Connectors** and toggle on your issue tracker.
3. Send the prompt below.
4. Download the workbook and spot-check a few rows against the tracker.
5. Tell Claude which changes to apply. When it asks to use a tool, select **Allow once**.

## Prompt
```text
Triage the backlog of {{project_key}}. Scope: {{filter}}.

Context: {{team_context}}. We can take on about {{capacity}} next sprint, so I want a short list we will do and an honest list we will not.

For each issue in scope, read the description and the latest comments, then classify it as do next, needs information, duplicate or close as stale. Give a one-line reason and, for a duplicate, the key of the issue it repeats. Call an issue stale only if nothing has changed in {{stale_after}} and nobody has asked about it since.

Create an Excel workbook with one row per issue (key, summary, age in days, reporter, classification, reason, proposed priority) and a second sheet that counts issues per classification with formulas. In the chat, list the ten issues you would do next, in order, and the assumptions behind that order.

This pass is read-only. Do not edit, comment on or close anything. I will say which changes to apply after checking the workbook.
```

## Why it works
A connector lets Claude read the issues with your own access instead of an export, and file creation returns a workbook with working formulas you can audit. Splitting the read-only pass from the write pass matters because connectors can modify data in the service.
