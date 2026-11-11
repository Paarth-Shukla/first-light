---
id: weekly-status-report
title: Write the weekly status report from commits, tickets and chat
job: writing
level: starter
minutes_saved: 30
features: [claude-docs, connectors, slack-connector]
prerequisites: [A connector for your issue tracker turned on, The Slack connector if your plan includes it, A terminal in your repository]
fields:
  - name: git_log
    label: This week's commits
    placeholder: Paste the output of the git log command from step 1
  - name: week
    label: Week
    placeholder: 9 November 2026
  - name: reader
    label: Who reads it
    placeholder: my manager and the program lead
  - name: tracker_project
    label: Tracker project
    placeholder: STOR
  - name: slack_channels
    label: Slack channels
    placeholder: storage-platform and oncall
docs:
  - title: Get started with Claude Docs
    url: https://support.claude.com/en/articles/16923645-get-started-with-claude-docs
  - title: Use connectors to extend Claude's capabilities
    url: https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities
  - title: Slack integration
    url: https://claude.com/docs/connectors/slack/index
verified: 2026-11-11
---
## Steps
1. In your repository, run `git log --since="7 days ago" --author="$(git config user.email)" --oneline` and copy the output.
2. In a new chat, click **+**, hover over **Connectors** and toggle on your issue tracker and Slack.
3. Send the prompt below with the commits pasted in. Claude drafts the report as a doc.
4. Check each bullet against the linked ticket, then edit the doc directly.
5. Click **Share**, or **Export** for Word, PDF, Markdown or Google Docs.

## Prompt
```text
<commits>
{{git_log}}
</commits>

Draft my status report for the week of {{week}} as a doc. The reader is {{reader}}, who has two minutes and wants to know what changed, what is next and where they need to act.

Sources, besides the commits above: issues assigned to me in {{tracker_project}} that changed status this week, and my messages in the Slack channels {{slack_channels}} from the same period. Group related commits and tickets into outcomes instead of listing them, and link each outcome to its ticket.

Format: three sections named Done, Next and Risks, at most five bullets each, in plain sentences. Under Risks include anything blocked for more than two days and say what would unblock it. Report only what the sources show. If something looks finished but you cannot find evidence, put it under a final heading "To confirm" instead of Done.
```

## Why it works
Drafting a status report is one of the Claude Docs guide's own examples, and the guide says to name the connected app Claude should use. Naming the reader and their two minutes sets the length, and the "To confirm" heading gives uncertain items somewhere to go other than Done.
