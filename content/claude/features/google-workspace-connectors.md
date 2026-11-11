---
id: google-workspace-connectors
title: Google Workspace connectors
surface: apps
group: Extend
status: stable
level: starter
payoff: 3
effort: 1
jobs: [meetings, writing, planning, research]
tags: [gmail, calendar, drive, google-docs, connectors]
summary: The Google Workspace connectors link Gmail, Google Calendar and Google Drive to Claude, and let it edit Google Docs, Sheets and Slides live in a pane beside the chat.
when: Use them when the answer lives in your mail, calendar or Drive, or when you want Claude to edit a Google file in place instead of producing a download.
replaces: Pasting email threads and document text into chat, and copying Claude's edits back into the Google file.
example_kind: prompt
docs:
  - title: Use Google Workspace connectors
    url: https://support.claude.com/en/articles/10166901-use-google-workspace-connectors
verified: 2026-11-11
---
## Try it in a minute
1. Connect Gmail, Google Calendar and Google Drive from [Customize > Connectors](https://claude.ai/customize/connectors) and authenticate with your Google account.
2. In a chat, click the plus sign, hover over **Connectors** and toggle on the ones you need, including the separate Docs, Sheets and Slides connectors for live editing.
3. Ask a question that needs your mail, calendar or Drive. By default Claude asks for approval before actions such as sending email or sharing files.
4. To edit live, paste a Google Docs, Sheets or Slides link, or ask for a Google file by name.

## Example
```text
Look at my calendar for next week and the email threads with each meeting's attendees from the last 14 days.

For every meeting I am hosting, give me: the open questions from the threads and a three-line agenda. Then make a Google doc called "Week prep" with one section per meeting.
```

## At work
- **Meeting prep.** Claude cites which emails, calendar events and documents it used, with links to the originals when available.
- **Scheduling.** The Calendar connector can find mutual availability across attendees and create, update or delete events.
- **Editing in place.** You and Claude can work in the same Google file at the same time.

## Pitfalls
- Asking for a generic "doc" or "deck" without naming Google creates a local file instead.
- Claude extracts text only from Drive files, and sees Gmail attachment metadata but not content.
- Claude cannot add charts to Google Slides, and Slides edits may not appear live in the pane.
- The live pane works on Claude on the web in Chrome, and on Claude Desktop with the built-in browser turned on. Otherwise select **Open in Google** on the file card.
- On Team and Enterprise plans an Owner must enable the connectors first.
