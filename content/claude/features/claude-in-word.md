---
id: claude-in-word
title: Claude for Word
surface: integrations
group: Microsoft 365
status: stable
level: starter
payoff: 2
effort: 1
jobs: [writing, review]
tags: [word, add-in, tracked-changes, comments, microsoft-365]
summary: Claude for Word is an add-in that answers questions about the open document with clickable section citations and edits it in place, including as tracked changes and through comment threads.
when: Use it for documents that must stay in Word and go through formal review, where every edit should be a revision someone can accept or reject. For a living document inside Claude, use Claude Docs.
replaces: Pasting sections into chat, then re-applying the edits and formatting in Word by hand.
example_kind: prompt
docs:
  - title: Use Claude for Word
    url: https://claude.com/docs/office-agents/word
  - title: Claude for M365 overview
    url: https://claude.com/docs/office-agents/overview
verified: 2026-11-11
---
## Try it in a minute
1. Install the Claude for Microsoft 365 add-in from Microsoft AppSource by selecting **Get it now**.
2. Open a `.docx` document in Word, activate the add-in and sign in with your Claude account.
3. Ask a question about the document and click a citation to jump to the section.
4. Select a passage and tell Claude what to change. Only the selection is edited.
5. Enter tracked changes mode so Claude's edits land as revisions, then accept or reject them in Word's review pane.

## Example
```text
Work through my open comments as tracked changes.

For each comment, edit the anchored text and reply in the thread with what you changed. Then check the whole document for inconsistent defined terms, broken cross-references and gaps in the numbering scheme, and list what you find without changing it.
```

## At work
- **Addressing review comments.** Claude reads each comment thread, edits the anchored passage and replies with a note explaining what it did.
- **Consistency checks.** The docs list flagging inconsistent defined terms and broken cross-references, and proofreading, as standard prompts.
- **Filling a template.** New sections inherit the document's heading and paragraph styles, and tables populate in place without reflowing the layout.

## Pitfalls
- Legacy `.doc` files are not supported. Save as `.docx` first.
- It does not run on Word 2016 or 2019 perpetual licenses, Word on iPad or Word on Android.
- Only use it with trusted documents. Hidden instructions can sit in text, comments, tracked changes, headers and footers.
- Review tracked changes before accepting them. The docs say it is not recommended for final deliverables without human review.
- Instructions set in Word apply only to Word, and chat history is stored locally in your browser.
- Usage counts against the same limits as your Claude account.
