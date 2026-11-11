---
id: claude-slides
title: Claude Slides
surface: apps
group: Make things
status: new
level: starter
payoff: 2
effort: 1
jobs: [writing, meetings, planning]
tags: [slides, presentations, artifacts, export]
summary: Claude Slides is the artifact template for presentations, built from your notes, reports or the work already in your chat, that you can edit, present from Claude and export.
when: Use it when you need a deck from material you already have and expect to revise it with Claude. Use Claude for PowerPoint when the deck must live in an existing PowerPoint file or template.
replaces: Rebuilding the content of a document slide by slide in a presentation tool.
example_kind: prompt
docs:
  - title: What are artifacts and how do I use them?
    url: https://support.claude.com/en/articles/17153992-what-are-artifacts-and-how-do-i-use-them
  - title: Get started with Claude Docs
    url: https://support.claude.com/en/articles/16923645-get-started-with-claude-docs
verified: 2026-11-11
---
## Try it in a minute
1. Ask for a deck in any chat, or select **Output** in the message box and choose the Slides template, or pick it in the **Artifacts** tab.
2. Give Claude the notes, report or chat content the deck should be built from.
3. Edit any slide directly, or ask Claude to change it.
4. Open the **Present** menu in the toolbar and select **Present**. Use the Right arrow key or Space for the next slide and Escape to end.
5. Click **Export** for PowerPoint or PDF, or send the deck to Google Slides as an editable file.

## Example
```text
Make a deck from the incident review doc in this chat for Friday's operations review.

Audience: engineering managers who were not on the call. Eight slides at most: what happened, customer impact, timeline, root cause, what we fixed, what is still open, asks. One idea per slide.
```

## At work
- **Doc to deck.** You can ask Claude to turn a Claude Doc into a presentation, so the review deck starts from the design doc.
- **Presenting without exporting.** Present directly from Claude, with number keys 1 to 9 jumping to a slide and F toggling full screen.
- **House style.** Decks can use a design system so new work picks up your colors, fonts and components.

## Pitfalls
- Delete or Backspace on a slide thumbnail deletes that slide right away. Cmd+Z (Ctrl+Z on Windows) brings it back.
- An object that is part of the slide's layout cannot be moved with the arrow keys. Ask Claude to move it.
- Artifacts start private. Sharing is a separate step, and sharing settings cannot be changed in the mobile apps.
- Artifacts need **Cloud code execution and file creation** turned on in **Settings > Capabilities**.
