---
id: design-doc-with-three-reviews
title: Write a design doc from rough notes and get three reviews
job: writing
level: intermediate
minutes_saved: 60
features: [claude-docs, effort-and-thinking, prompt-design-basics]
prerequisites: [Claude on the web or Claude Desktop, Your rough notes as text]
fields:
  - name: rough_notes
    label: Rough notes
    placeholder: Paste meeting notes and whiteboard photos turned into text
  - name: audience
    label: Who reads the doc
    placeholder: the storage platform engineers and our engineering manager
  - name: decision_needed
    label: What they will decide
    placeholder: whether to build tiering into the replication service this quarter
  - name: length
    label: Target length
    placeholder: two to three pages
  - name: dependent_team
    label: A team that depends on this
    placeholder: the backup team
docs:
  - title: Get started with Claude Docs
    url: https://support.claude.com/en/articles/16923645-get-started-with-claude-docs
  - title: Change the model, effort, and thinking settings
    url: https://support.claude.com/en/articles/8664678-change-the-model-effort-and-thinking-settings
  - title: Prompting best practices
    url: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
verified: 2026-11-11
---
## Steps
1. Click the model name next to the send button, click **Effort** and choose a higher level. The docs recommend this for detailed document analysis.
2. Send the prompt below with your notes pasted in. Claude asks a few questions, then drafts the doc on screen.
3. Read the three reviews and tell Claude which objections to act on.
4. Fix small things by typing in the doc. For a targeted edit, select text, comment and mention @Claude.
5. Click **Share** to add reviewers, or **Export** for Word, PDF, Markdown or Google Docs.

## Prompt
```text
<notes>
{{rough_notes}}
</notes>

Write a design doc from these notes as a doc I can share. Readers are {{audience}}, who will decide {{decision_needed}}. They know our systems but were not in the discussions, so define terms the notes take for granted.

Sections: problem and goals, non-goals, proposed design, alternatives considered with the reason each was rejected, rollout and rollback, risks, open questions. Keep it to {{length}}. Where the notes are silent, leave a comment asking me instead of inventing detail, because a confident guess in a design doc is worse than a visible gap.

When the draft is done, review it three times: as the operator who gets paged for this, as a security reviewer, and as an engineer on {{dependent_team}}. For each, list the three objections most likely to block approval, quote the passage each is about, and say what change would answer it. Do not revise the doc until I choose.
```

## Why it works
The Claude Docs guide says a good request states what the doc is for, who will read it and what it covers. The prompting guide's self-correction pattern is draft, review against criteria, then refine, and stopping before the revision keeps the choice of objections with you.
