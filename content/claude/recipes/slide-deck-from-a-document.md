---
id: slide-deck-from-a-document
title: Build a slide deck from a document
job: writing
level: starter
minutes_saved: 40
features: [claude-slides, claude-docs, claude-in-powerpoint]
prerequisites: [The source document as a Claude Doc or an upload, Claude for PowerPoint only if the deck must use a company template]
fields:
  - name: source
    label: The document
    placeholder: the replication redesign doc in this chat
  - name: slide_count
    label: Maximum slides
    placeholder: 8
  - name: audience
    label: Audience
    placeholder: directors and product managers who have not read the design doc
  - name: occasion
    label: Where it will be shown
    placeholder: a 15-minute slot in the quarterly planning review
  - name: ask
    label: What you need from them
    placeholder: approval for two engineers for one quarter
docs:
  - title: What are artifacts and how do I use them?
    url: https://support.claude.com/en/articles/17153992-what-are-artifacts-and-how-do-i-use-them
  - title: Get started with Claude Docs
    url: https://support.claude.com/en/articles/16923645-get-started-with-claude-docs
  - title: Use Claude for PowerPoint
    url: https://claude.com/docs/office-agents/powerpoint
verified: 2026-11-11
---
## Steps
1. Open the chat that has the document, or attach it. You can ask Claude to turn a Claude Doc into a presentation with Claude Slides.
2. Send the prompt below, or select **Output** in the message box and choose the Slides template first.
3. Reorder the proposed storyline, then let Claude build. Edit slides directly or ask for changes.
4. Rehearse from the **Present** menu in the toolbar. Right arrow or Space moves on, Escape ends.
5. Click **Export** for PowerPoint or PDF, or send it to Google Slides. If the deck must use the company template, give the same prompt to Claude for PowerPoint in that template; it uses the slide master's layouts, fonts and colors.

## Prompt
```text
Turn {{source}} into a deck of at most {{slide_count}} slides for {{audience}}. It will be shown in {{occasion}}, and its purpose is to get {{ask}}.

The audience has not read the document, so the deck has to stand on its own. Put the ask and the main reason on the first content slide, then include only the evidence that supports the decision. Move everything else to an appendix.

For each slide, write a headline that states the conclusion as a full sentence, add no more than three supporting points, and use a chart or diagram where the document has numbers or a sequence of steps. Use only figures that appear in the document and keep its terminology. Where the document leaves a question open, put it on an "Open questions" slide rather than resolving it.

Before you build the deck, show me the storyline as a numbered list of slide headlines so I can reorder it.
```

## Why it works
Claude Slides builds decks from the reports or work already in your chat, so nothing needs rewriting first. Naming the audience, occasion and ask tells Claude what to cut. The storyline gives you a cheap checkpoint before layout work, and the rule on figures keeps every number traceable to the document.
