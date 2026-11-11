---
id: cc-computer-use
title: Computer use from the CLI
surface: code
group: Integrations
status: beta
level: power
payoff: 1
effort: 2
jobs: [debugging, coding, automation]
tags: [computer-use, gui, macos, testing, research-preview]
summary: Computer use lets Claude open apps, click, type and see your screen on macOS, so it can test native apps and drive tools that only have a graphical interface.
when: Reach for it only when nothing more precise applies, such as a native app, a simulator or a tool without a CLI or API. Claude prefers an MCP server, Bash or Chrome when one fits.
replaces: Clicking through a native app by hand to check a build, then describing what you saw.
example_kind: prompt
docs:
  - title: Let Claude use your computer from the CLI
    url: https://code.claude.com/docs/en/computer-use
verified: 2026-11-11
---
## Try it in a minute
1. In an interactive session on macOS, run `/mcp`, select `computer-use` and choose **Enable**. The setting persists per project.
2. Ask for something that needs the GUI.
3. Grant the two macOS permissions when prompted, **Accessibility** and **Screen Recording**, then select **Try again**.
4. When Claude asks to control a specific app, choose **Allow for this session** or **Deny**.
5. Press `Esc` at any time to stop.

## Example
```text
Build the app target, launch it, and click through each tab to make sure nothing crashes. Screenshot any error states you find.
```

## At work
- **Validate a native build.** Claude compiles, launches the app, clicks through the controls and reports what it finds.
- **Reproduce a layout bug.** Claude resizes the window, reproduces the bug, screenshots it, patches the CSS and verifies the fix.
- **GUI-only tools.** Design tools, hardware control panels or the iOS Simulator can be driven without a test harness.

## Pitfalls
- The page describes it as a research preview on macOS that requires a Pro, Max or Ultra plan and is not available on Team or Enterprise plans.
- It needs an interactive session, so it does not work with `-p`.
- Unlike the sandboxed Bash tool, it runs on your actual desktop with access to the apps you approve.
- Only one session at a time can use your computer. The lock is released when that session exits.
- Other visible apps are hidden while Claude works and restored when the turn ends.
- Terminals and IDEs are click-only and browsers are view-only. Approving a terminal or Finder shows an extra warning because of what it grants.
- It is the broadest and slowest way for Claude to interact with something.
