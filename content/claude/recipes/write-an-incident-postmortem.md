---
id: write-an-incident-postmortem
title: Write an incident postmortem from the timeline
job: writing
level: starter
minutes_saved: 40
features: [claude-docs, slack-connector, connectors]
prerequisites: [The raw incident timeline, The Slack connector if your plan includes it, A connector for your issue tracker]
fields:
  - name: timeline
    label: Raw timeline
    placeholder: Paste alert times, pages, deploys and commands run, one per line, in UTC
  - name: incident
    label: Incident
    placeholder: the SEV2 on 4 November, replication lag on the eu-west metadata cluster
  - name: readers
    label: Who reads it
    placeholder: the storage platform engineers and their managers
  - name: channel
    label: Incident Slack channel
    placeholder: inc-2026-11-04-replication-lag
  - name: tracker_project
    label: Tracker project
    placeholder: STOR
docs:
  - title: Get started with Claude Docs
    url: https://support.claude.com/en/articles/16923645-get-started-with-claude-docs
  - title: Slack integration
    url: https://claude.com/docs/connectors/slack/index
  - title: Use connectors to extend Claude's capabilities
    url: https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities
  - title: Prompting best practices
    url: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
verified: 2026-11-11
---
## Steps
1. Copy the raw timeline from your paging tool, in UTC.
2. In a new chat, select **+**, then **Connectors**, and turn on **Slack** and your issue tracker.
3. Send the prompt below. Claude asks a few questions first, then drafts the doc and leaves comments explaining its choices.
4. To change a passage, select it and mention @Claude in a comment.
5. Click **Share** to give responders edit access, or **Export** to Word, PDF, Markdown or Google Docs.

## Prompt
```text
<timeline>
{{timeline}}
</timeline>

Write the postmortem for {{incident}} as a doc. It is for {{readers}}, who were not on the call and need to judge whether the follow-up work is enough. We run blameless reviews, so describe what responders saw and did, and refer to roles rather than names.

Besides the timeline above, read the Slack channel {{channel}} for the same period and quote the messages that mark detection, diagnosis and mitigation.

Sections, in order: Summary (under 100 words), Customer impact (duration, scope and how it was measured), Timeline in UTC, Root cause and contributing factors, What went well, Action items.

In the root cause section, keep what the evidence shows apart from what is still a hypothesis, and name the log line or message behind each claim. Where the timeline has a gap of more than 15 minutes, mark the gap instead of filling it. For each action item give an owner role, say whether it prevents a repeat or only speeds up detection, and link a matching open issue in {{tracker_project}} if one exists.
```

## Why it works
The Claude Docs guide says a good request names what the doc is for, who reads it, what it covers and which connected app to use. The timeline goes first and the instructions last, as the prompting guide recommends for long inputs. Marking gaps and separating evidence from hypothesis gives uncertainty a visible place instead of a confident sentence.
