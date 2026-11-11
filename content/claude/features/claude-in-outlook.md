---
id: claude-in-outlook
title: Claude for Outlook
surface: integrations
group: Microsoft 365
status: beta
level: starter
payoff: 2
effort: 2
jobs: [meetings, writing, planning]
tags: [outlook, add-in, email, calendar, microsoft-365]
summary: Claude for Outlook is an add-in that triages your inbox, drafts replies in your voice, summarizes threads with per-email citations and finds meeting times, always leaving drafts unsent.
when: Use it when your mail runs through Outlook on Exchange Online and you want help inside the inbox itself. The Microsoft 365 connector is the route when you want mail and files as context in a Claude chat instead.
replaces: Reading a 40-message thread end to end to work out what was decided and who owes what.
example_kind: prompt
docs:
  - title: Use Claude for Outlook
    url: https://claude.com/docs/office-agents/outlook
  - title: Claude for M365 overview
    url: https://claude.com/docs/office-agents/overview
verified: 2026-11-11
---
## Try it in a minute
1. Go to the Claude for Outlook listing on Microsoft AppSource and select **Get it now**. Your organization may need an admin to grant Microsoft Graph consent.
2. Open Outlook, open any email, select the Claude button in the message ribbon and sign in with your Claude account.
3. Ask "What needs me?" to sort unread mail into action items, items Claude can handle and noise.
4. Open a long thread and ask what has been decided and what is still open.
5. Ask for a reply. The draft lands unsent in Outlook's compose pane for you to review and send.

## Example
```text
Summarize this thread: what has been decided, what is still open, and who owes what. Cite the email for each point.

Then draft a reply-all confirming the two decisions, asking the storage team for the benchmark results by Thursday, and proposing a 30-minute follow-up next week. Warn me before adding anyone who was not on the thread.
```

## At work
- **Thread catch-up.** Summaries cite the specific email for each point, and a citation opens that message.
- **Meeting prep.** "Prep me for my 2pm" pulls the last thread with each attendee and any attached documents into a one-page brief.
- **Scheduling.** Claude checks free/busy for calendars you can see and drafts the invite into Outlook's appointment form.

## Pitfalls
- It is in beta. Claude never sends mail or invites on its own.
- Not supported on Outlook for iOS or Android, perpetual-license Outlook, or mailboxes hosted on Exchange on-premises.
- PDF attachments are not read inline. Save the file and upload it through the sidebar.
- Email bodies and attachments may contain instructions meant to manipulate Claude. Review every draft and recipient list.
- During the beta it is not recommended for client-facing correspondence without reading the draft.
