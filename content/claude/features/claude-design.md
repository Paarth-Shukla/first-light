---
id: claude-design
title: Claude Design
surface: apps
group: Make things
status: new
level: intermediate
payoff: 2
effort: 2
jobs: [planning, writing, coding]
tags: [design, prototypes, mockups, design-system, artifacts]
summary: Claude Design is the artifact template for designs, interactive prototypes, one-pagers and other visual work, built by chatting with Claude and refined on a canvas with your design system.
when: Use it when you need to show what something should look like, such as an internal tool screen or a one-pager, before anyone writes production code. Hand the result to Claude Code when it is ready to become software.
replaces: Describing a UI in prose in a ticket, or waiting for a designer to mock up an internal tool.
example_kind: prompt
docs:
  - title: Get started with Claude Design
    url: https://support.claude.com/en/articles/14604416-get-started-with-claude-design
  - title: What are artifacts and how do I use them?
    url: https://support.claude.com/en/articles/17153992-what-are-artifacts-and-how-do-i-use-them
verified: 2026-11-11
---
## Try it in a minute
1. Ask Claude for a design in a conversation, or select **Output** > **Design** in the message box, or pick a Design template in the **Artifacts** tab.
2. Describe the goal, the layout, the content and the audience. Attach screenshots or a codebase for context.
3. Review what Claude generates on the canvas.
4. Use chat for structural changes, inline comments for a specific element, and direct editing to drag, resize and align.
5. Use the **Export** button, or click **Share** to choose who can open it.

## Example
```text
Design an internal tool for our ops team to review and approve firmware rollout requests.

Layout: a queue on the left with status filters, and a detail pane on the right showing the target fleet, the risk checklist and Approve and Reject buttons.
Audience: on-call engineers on a laptop.
Show me two alternative layouts for the detail pane.
```

## At work
- **Internal tools.** Agree on a screen with the people who will use it before building, then use **Handoff to Claude Code** so the implementation continues from the design instead of a screenshot.
- **Staying on brand.** With a design system attached, Claude builds with your real components and checks its output against them. In Claude Code, `/design-sync` pulls in your design system.

## Pitfalls
- Claude Design does not have version history yet. Ask Claude to save the current state before trying a different direction.
- Two or more people editing the same design at once is still basic and may not work reliably.
- If inline comments are not picked up, paste the feedback into the chat.
- Design system import is only as good as its source. A messy codebase shows up in the output.
- The standalone version at claude.ai/design closes on December 14, 2026.
