---
id: microsoft-365-connector
title: Microsoft 365 connector
surface: apps
group: Extend
status: stable
level: intermediate
payoff: 2
effort: 2
jobs: [meetings, research, writing, planning]
tags: [outlook, sharepoint, onedrive, teams, connectors]
summary: The Microsoft 365 connector lets Claude search, analyze and act on Outlook email and calendar and OneDrive files, plus SharePoint and Teams with a work or school account.
when: Use it when the context you need is spread across Outlook threads, SharePoint libraries and Teams channels, and you want one question to search all of them.
replaces: Searching Outlook, SharePoint and Teams separately and stitching the results together by hand.
example_kind: prompt
docs:
  - title: Connect to Microsoft 365
    url: https://support.claude.com/en/articles/15183774-connect-to-microsoft-365
verified: 2026-11-11
---
## Try it in a minute
1. Go to [Customize > Connectors](https://claude.ai/customize/connectors) and find **Microsoft 365** in the list.
2. Click **Add** and choose **Work or school account** if asked, then sign in with that account. An admin must have set the connector up first.
3. In a chat, click the **+** button, hover over **Connectors** and toggle **Microsoft 365** on.
4. Ask a question that names where to look, such as a SharePoint site, a date range or a sender.

## Example
```text
Search the Engineering team site in SharePoint for architecture documents about the metadata service, and find emails from the last two weeks about its migration.

Summarize the current plan, list decisions and who made them, and point out where the documents and the emails disagree. Draft a reply to the latest email in the thread with my questions, but don't send it.
```

## At work
- **Catching up on a thread.** Ask for an email thread summary with key points and decisions.
- **Finding the spec.** Claude searches SharePoint sites, document libraries and shared OneDrive folders you can already access.
- **Follow-through.** If your admin has enabled write tools, Claude can draft and send email, manage calendar events, create and update files, and send Teams messages.

## Pitfalls
- Work or school accounts need admin setup, including a one-time consent by a Microsoft Entra Global Administrator.
- Without write tools the integration is read-only. By default Claude asks you to confirm before it sends or changes something.
- Attachments are not supported in write tools, so Claude cannot send, forward or draft emails with attachments.
- Only Word, Excel, PowerPoint, PDF and plain-text formats can be read. OneNote is not supported.
- You cannot scope the connector to specific SharePoint sites. It searches everything you have permission to access.
- A personal account does not include SharePoint or Teams.
