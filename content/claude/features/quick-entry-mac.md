---
id: quick-entry-mac
title: Quick entry on Mac
surface: apps
group: Input
status: stable
level: starter
payoff: 2
effort: 1
jobs: [debugging, coding, research, writing]
tags: [desktop, mac, shortcut, screenshot, dictation]
summary: Quick entry in Claude Desktop on Mac opens Claude from any app with a keyboard shortcut, and lets you attach a screenshot or an application window or dictate your message.
when: Use it when you are in the middle of something and want to ask about what is on your screen without switching windows, copying text or saving a screenshot first.
replaces: Taking a screenshot, finding the file, switching to Claude and dragging it into a new chat.
example_kind: prompt
docs:
  - title: Use quick entry with Claude Desktop on Mac
    url: https://support.claude.com/en/articles/12626668-use-quick-entry-with-claude-desktop-on-mac
verified: 2026-11-11
---
## Try it in a minute
1. Open Claude Desktop on your Mac. In the quick entry prompt, check **Turn on shortcut** and click **Continue**.
2. From any application, double-tap the Option key. A text box appears.
3. Click and drag to select an area of the screen, or click an application window to attach its contents.
4. Type your question and press Enter.
5. Optional. Enable the voice shortcut, then press Caps Lock once to start dictating and again to stop.

## Example
After double-tapping Option and clicking your terminal window:

```text
This is the output of the failing integration test run. Which assertion failed first, and what does the stack trace say about where the nil pointer comes from? Give me the two most likely causes and the command to rerun only that test with verbose logging.
```

## At work
- **Debugging in flow.** The docs list sharing error messages or application windows directly with Claude for debugging assistance.
- **Reading dashboards and diagrams.** Capture part of a monitoring graph or an architecture diagram and ask a question about it without leaving the page.
- **Hands-free notes.** Dictate a thought with real-time transcription, review it, then send.

## Pitfalls
- Quick entry is only available on macOS. Claude Desktop must be running, though it can be in the background.
- It needs macOS 12 or later, and voice dictation needs macOS 14 or later.
- The voice shortcut is disabled by default because it takes over your Caps Lock key.
- It requires macOS permissions for screen recording and accessibility, plus speech recognition for dictation. Review them in System Settings > Privacy & Security.
- If double-tap Option conflicts with another app, change **Quick access shortcut** in **Settings > Desktop app** to Option + Space or a custom shortcut.
