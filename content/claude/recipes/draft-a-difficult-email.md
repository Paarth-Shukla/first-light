---
id: draft-a-difficult-email
title: Draft a difficult email or announcement for a specific audience
job: writing
level: starter
minutes_saved: 20
features: [prompt-design-basics, claude-in-outlook, google-workspace-connectors]
prerequisites: [The facts you need to communicate, Claude for Outlook or the Gmail connector if you want the draft in your mail]
fields:
  - name: audience
    label: Who reads it
    placeholder: the platform leads of the two downstream teams, who pushed back on the original date
  - name: message
    label: What you have to tell them
    placeholder: the v3 API removal moves forward from June to March, so they lose three months of migration time
  - name: relationship
    label: Context on the relationship
    placeholder: we need their help during the migration, and they escalated the last change
  - name: goal
    label: What you want them to do
    placeholder: agree a migration plan in a 30-minute meeting next week
  - name: facts
    label: Facts and limits
    placeholder: Paste the dates, numbers and reasons that must appear, and anything you cannot promise
docs:
  - title: Prompting best practices
    url: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
  - title: Introduction to prompt design
    url: https://support.claude.com/en/articles/7996853-introduction-to-prompt-design
  - title: Use Claude for Outlook
    url: https://claude.com/docs/office-agents/outlook
  - title: Use Google Workspace connectors
    url: https://support.claude.com/en/articles/10166901-use-google-workspace-connectors
verified: 2026-11-11
---
## Steps
1. Write down the facts first, including what you cannot promise.
2. Send the prompt below in a new chat.
3. Read the critique, then ask Claude to revise the draft you prefer.
4. In Outlook, ask the Claude for Outlook add-in to draft it in the thread. The draft lands unsent in the compose pane, in a tone learned from your sent folder. With Gmail connected, Claude asks for approval before sending.
5. Check the final text and the recipient list yourself.

## Prompt
```text
I need to write to {{audience}}. The news: {{message}}. Context on the relationship: {{relationship}}. What I want them to do after reading: {{goal}}.

<facts>
{{facts}}
</facts>

Use only the facts above. State the bad news plainly in one sentence and promise only what the facts support, because the readers will hold us to every sentence.

Write two drafts, each under 200 words in plain sentences, with one clear ask and a date: one that gives the news in the first sentence, and one that opens with the shared goal and gives the news in the second paragraph.

Then read both as the recipients would. For each draft, list the sentences most likely to get a defensive reply, the questions they will ask that the draft does not answer, and anything that could read as blame. Recommend one draft and say why.
```

## Why it works
The prompting guide says to give the reason behind an instruction; here, that readers will hold you to every sentence keeps the draft from overpromising. It also recommends saying what to do rather than what not to do, and a draft, review and refine loop for checking output against criteria. Two openings let you choose the tone yourself.
