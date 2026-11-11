---
id: cc-chrome
title: Claude Code with Chrome
surface: code
group: Integrations
status: stable
level: intermediate
payoff: 2
effort: 2
jobs: [debugging, coding, automation]
tags: [chrome, browser, testing, console, automation]
summary: Chrome integration connects Claude Code to the Claude in Chrome browser extension, so Claude can open pages, click, type and read console output from your session.
when: Use it when a change has to be checked in a real browser, or when a task lives in a web app you are already signed into and there is no API connector for it.
replaces: Switching to the browser to click through a flow and copying console errors back into the terminal.
example_kind: prompt
docs:
  - title: Use Claude Code with Chrome
    url: https://code.claude.com/docs/en/chrome
verified: 2026-11-11
---
## Try it in a minute
1. Install the Claude in Chrome extension from the Chrome Web Store, and sign in to Claude Code with `/login`.
2. Start with `claude --chrome`. The first launch shows a one-time dialog about site permissions.
3. Ask for a browser task. Approve the prompt that starts with `Claude in Chrome wants to`.
4. Run `/chrome` to check the connection. It is working when the panel shows "Status: Enabled" and "Extension: Installed".

## Example
```text
I just updated the login form validation. Can you open localhost:3000, try submitting the form with invalid data, and check if the error messages appear correctly? Then check the console for any errors when the page loads.
```

## At work
- **Verify a UI change.** Claude navigates to your local server, interacts with the form and reports what it observes.
- **Debug from console logs.** Tell Claude which patterns to look for rather than asking for all console output, since logs can be verbose.
- **Web apps without connectors.** Because Claude shares your browser's login state, it can work in apps such as Google Docs or Notion that you are signed into.

## Pitfalls
- The docs require a direct Anthropic plan and a `/login` sign-in. It is not available with an API key or through Amazon Bedrock, Google Cloud's Agent Platform or Microsoft Foundry.
- Claude can reach any site you are already signed into. Manage which sites it may use in the extension's settings.
- At a login page or CAPTCHA, Claude pauses and asks you to handle it.
- It works with Chrome, Edge and other Chromium-based browsers, and is not supported in WSL.
- Selecting **Enabled by default** in `/chrome` increases context usage, because the browser tools are always loaded.
