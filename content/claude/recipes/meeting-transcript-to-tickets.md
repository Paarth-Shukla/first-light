---
id: meeting-transcript-to-tickets
title: Turn a meeting transcript into decisions, owners and tickets
job: meetings
level: intermediate
minutes_saved: 25
features: [connectors, prompt-design-basics]
prerequisites: [A meeting transcript as text, A connector for your issue tracker connected in Customize > Connectors]
fields:
  - name: transcript
    label: Transcript
    placeholder: Paste the full transcript
  - name: meeting_name
    label: Meeting
    placeholder: the weekly replication sync on 10 November
  - name: project_key
    label: Tracker project
    placeholder: STOR
  - name: issue_type
    label: Issue type
    placeholder: Task
docs:
  - title: Use connectors to extend Claude's capabilities
    url: https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities
  - title: Get started with connectors
    url: https://claude.com/docs/connectors/getting-started
  - title: Prompting best practices
    url: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
verified: 2026-11-11
---
## Steps
1. In [Customize > Connectors](https://claude.ai/customize/connectors), select **Discover**, search for the service that holds your tickets and connect it. On Team and Enterprise plans an Owner adds it first.
2. In a new chat, click **+**, hover over **Connectors** and toggle the tracker on.
3. Send the prompt below with the transcript pasted in. Claude returns decisions, action items and draft tickets, and creates nothing yet.
4. Correct the drafts in the chat, then say which ones to create.
5. When Claude asks to use a tool, select **Allow once**.

## Prompt
```text
<transcript>
{{transcript}}
</transcript>

This is the transcript of {{meeting_name}}. People who missed it will read your summary instead of the recording, so it has to stand on its own.

First quote the lines where something was decided or someone took on work, inside <quotes> tags. Then, based only on those quotes, write:
1. Decisions, one line each, with who made the call.
2. Action items: owner, what, and due date. Write "no owner named" or "no date given" instead of guessing.
3. Open questions nobody answered.

Then draft one ticket per action item for project {{project_key}}, issue type {{issue_type}}: a summary under 80 characters, a description with the context someone outside the meeting needs, and acceptance criteria. Search the project first and flag likely duplicates. Show me the drafts and wait. Do not create or change any issue until I confirm which ones.
```

## Why it works
The prompting guide puts long material at the top and the request at the end, and recommends asking for relevant quotes first so the answer is grounded in them. Connectors act with your permissions, so the explicit wait keeps a misheard action item from becoming a ticket.
