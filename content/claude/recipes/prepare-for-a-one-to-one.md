---
id: prepare-for-a-one-to-one
title: Prepare for a one-to-one or performance review from your own work log
job: meetings
level: starter
minutes_saved: 30
features: [chat-search, connectors, claude-docs]
prerequisites: [A paid plan for searching past chats, A connector for your issue tracker, A terminal in your repositories]
fields:
  - name: git_log
    label: Your commits for the period
    placeholder: Paste the output of the git log command from step 1
  - name: goals
    label: Your goals for the period
    placeholder: Paste your goals or the role expectations you are measured against
  - name: meeting
    label: Which conversation
    placeholder: my mid-year review
  - name: reader
    label: Who it is with
    placeholder: my manager
  - name: tracker_project
    label: Tracker project
    placeholder: STOR
  - name: since
    label: Start of the period
    placeholder: 1 May 2026
docs:
  - title: Use Claude's chat search and memory to build on previous context
    url: https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context
  - title: Use connectors to extend Claude's capabilities
    url: https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities
  - title: Get started with Claude Docs
    url: https://support.claude.com/en/articles/16923645-get-started-with-claude-docs
verified: 2026-11-11
---
## Steps
1. In each repository you worked in, run `git log --since="2026-05-01" --author="$(git config user.email)" --oneline` with your own start date, and copy the output.
2. Start a new chat outside any project, so chat search covers all your chats outside projects rather than one project's.
3. Select **+**, then **Connectors**, turn on your issue tracker and send the prompt below. Searches of past chats show up as tool calls.
4. Follow the citations back to the original chats and tickets, and correct anything overstated.
5. For a written self-review, ask Claude to turn the result into a doc.

## Prompt
```text
<commits>
{{git_log}}
</commits>

<goals>
{{goals}}
</goals>

I am preparing for {{meeting}} with {{reader}}. I want to walk in with evidence rather than whatever I happen to remember, and I want the conversation to cover what I need from them as well as what I did.

Sources, besides the commits above: issues in {{tracker_project}} that I resolved, reviewed or commented on since {{since}}, and my past chats with you from the same period about designs, incidents and debugging.

Produce:
1. Impact: three to five outcomes, each with its evidence (ticket keys, commit hashes, links to the chats) and who benefited.
2. Progress against each goal above. Where the evidence is thin, say so.
3. What to raise: blockers, decisions or support I need, and one area I want to grow in, each with a concrete ask.
4. Two questions to ask {{reader}}.

Write in the first person and in plain language. Where the evidence only shows I took part, write "contributed to" rather than "led", because the reader will check.
```

## Why it works
Chat search finds and cites earlier conversations, so design and debugging work that never reached a ticket still counts as evidence. The prompt says why the summary is needed and who reads it, which the prompting guide says helps Claude target its answer. The "contributed to" rule keeps the draft honest.
