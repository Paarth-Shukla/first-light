---
id: claude-data
title: Claude Data
surface: apps
group: Make things
status: new
level: intermediate
payoff: 3
effort: 2
jobs: [analysis, planning, meetings]
tags: [data, dashboards, sql, warehouse, artifacts]
summary: Claude Data turns plain-language questions about your company's data into dashboards, data stories, narrated short videos and written analyses, with Claude writing the SQL.
when: Use it for quick, exploratory questions against a connected data warehouse or app, where you want a chart whose query you can inspect. For deeper analysis, the docs suggest sending the dashboard on to another tool.
replaces: Hand-writing SQL for a one-off question, exporting the result and building a chart in a spreadsheet.
example_kind: prompt
docs:
  - title: Get started with Claude Data
    url: https://support.claude.com/en/articles/17454700-get-started-with-claude-data
  - title: What are artifacts and how do I use them?
    url: https://support.claude.com/en/articles/17153992-what-are-artifacts-and-how-do-i-use-them
verified: 2026-11-11
---
## Try it in a minute
1. Connect the data you want to ask about. That can be a data warehouse such as BigQuery, Databricks or Snowflake, or another app you have connected to Claude.
2. Ask in any chat, or go to the **Artifacts** tab and select **Data**.
3. Say what you want to know, not only what to chart, and name the table or app if you know it.
4. Open a chart's query to see how Claude got the number. If it is not counting what you meant, tell Claude what to change.
5. Click **Share** when it is ready.

## Example
```text
Build a dashboard from the telemetry tables in our warehouse.

How does this month's rate of drive replacements per 1,000 deployed drives compare with the previous three months, split by drive model and by region? Add a filter for firmware version and a weekly view. Name the tables you used, and flag any model where the sample is too small to trust.
```

## At work
- **In a review.** Each chart shows its query and when its data was last refreshed, so a number can be checked on the spot.
- **Trusted definitions.** Certified queries (beta) are queries your data team has approved. Charts built on them carry a badge.

## Pitfalls
- Without live sharing, a shared dashboard loads data with each viewer's own connections, so a viewer without access sees an error for that part.
- Live sharing (beta) lets people in your organization see results from your connection, so check what a dashboard shows first.
- Data does not refresh on a schedule. It refreshes when someone opens the dashboard and the data is due.
- Editing a certified query removes its certification.
- Claude Data is for paid plans, and on Enterprise plans the beta features are off by default.
