---
id: claude-docs
title: Claude Docs
surface: apps
group: Make things
status: new
level: starter
payoff: 3
effort: 1
jobs: [writing, planning, review, meetings]
tags: [docs, artifacts, collaboration, comments, export]
summary: Claude Docs is a rich-text document, saved to your Claude account, that you, your teammates and Claude write and edit together in real time.
when: Ask for a doc when the output is a spec, status report or guide that will go through several rounds of edits and comments. Use file creation when you only need a Word or PDF file to send.
replaces: Drafting in chat, pasting into a document tool, then pasting sections back to Claude for each revision.
example_kind: prompt
docs:
  - title: Get started with Claude Docs
    url: https://support.claude.com/en/articles/16923645-get-started-with-claude-docs
  - title: What are artifacts and how do I use them?
    url: https://support.claude.com/en/articles/17153992-what-are-artifacts-and-how-do-i-use-them
verified: 2026-11-11
---
## Try it in a minute
1. In any conversation, ask Claude for a doc. You can also start your request with `/docs`, or select **Output** then **Docs** from the message box.
2. Answer the few questions Claude asks before it starts, then watch it draft on screen.
3. Click into the doc and type to edit directly, or ask in the conversation for the next pass.
4. Select text and leave a comment. Mention @Claude in a comment to ask for an edit at that spot.
5. Click **Share** to add people, or **Export** for Word, PDF, Markdown or Google Docs.

## Example
```text
Turn the plan we just worked through into a design doc I can share with the team.

Readers are the storage platform engineers. Cover problem and goals, non-goals, proposed design with a diagram, rejected alternatives, rollout plan and open questions. Two to three pages. Leave a comment wherever you made an assumption I should confirm.
```

## At work
- **Design docs and specs.** The plan you worked out in chat becomes a shareable document.
- **From a coding session.** In Claude Code you can ask Claude to turn the session into a spec, runbook or readout.
- **Review in place.** Editors work on the same doc at the same time, and every change is attributed to the person or to Claude.

## Pitfalls
- There is no comment-only access level yet, only viewers and editors.
- Deleting a doc is permanent. There is no trash, and it becomes unavailable to everyone you shared it with.
- Charts and diagrams do not update on their own. Ask Claude to pull the latest data.
- People you share a doc with must sign in to Claude.
- Claude acts with the permissions of the person who asked, so it cannot edit a doc for someone with view access.
