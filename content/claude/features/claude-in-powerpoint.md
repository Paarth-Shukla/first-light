---
id: claude-in-powerpoint
title: Claude for PowerPoint
surface: integrations
group: Microsoft 365
status: stable
level: starter
payoff: 2
effort: 1
jobs: [writing, meetings, planning]
tags: [powerpoint, add-in, slides, templates, microsoft-365]
summary: Claude for PowerPoint is an add-in that builds and edits slides inside PowerPoint using the layouts, fonts and colors of the template already in your deck.
when: Use it when the deck has to follow a corporate template or when you want to change specific slides without regenerating the whole deck. For a quick deck with no template constraints, Claude Slides in the app is simpler.
replaces: Reformatting generated slides by hand to match the company template.
example_kind: prompt
docs:
  - title: Use Claude for PowerPoint
    url: https://claude.com/docs/office-agents/powerpoint
  - title: Work across M365 apps
    url: https://claude.com/docs/office-agents/work-across-apps
verified: 2026-11-11
---
## Try it in a minute
1. Install the Claude for Microsoft 365 add-in from Microsoft AppSource by selecting **Get it now**.
2. Open PowerPoint with your template already applied, activate the add-in and sign in with your Claude account.
3. Describe the slides you need, or select a slide and say what to change.
4. Ask Claude to turn a bulleted slide into a diagram or a native chart you can edit.
5. Review every change before you present or send the deck.

## Example
```text
Build an internal project update presentation for the metadata service migration with timeline and next steps.

Six slides using this deck's layouts: status at a glance, what shipped this month, timeline, risks, asks, next steps. Turn the timeline into a process flow diagram and the latency numbers in my notes below into a bar chart comparing before and after. Use one-line bullets.

[paste notes]
```

## At work
- **Recurring review decks.** Generate the draft from your notes in the team template, then make pinpoint edits to individual slides.
- **Bullets into visuals.** Claude produces diagrams, process flows and native PowerPoint charts that stay editable, not static images.
- **From workbook to slide.** With **Let Claude work across files** turned on in each add-in, Claude can update a chart in PowerPoint from figures in an open Excel workbook.

## Pitfalls
- It does not run on PowerPoint 2016 or 2019 perpetual licenses, PowerPoint on iPad or PowerPoint on Android.
- Only use it with trusted files. External files can contain hidden instructions that try to manipulate the add-in.
- Working across apps only reaches files that are currently open, and Claude cannot open, close or switch files itself. The setting is off by default on Team and Enterprise plans.
- It does not replace your judgment on design and narrative flow.
