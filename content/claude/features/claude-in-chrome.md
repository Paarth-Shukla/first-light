---
id: claude-in-chrome
title: Claude in Chrome
surface: integrations
group: Browser
status: stable
level: intermediate
payoff: 3
effort: 2
jobs: [automation, debugging, research, review]
tags: [chrome, browser, extension, side-panel, console]
summary: Claude in Chrome is a browser extension that lets Claude read, click and navigate websites alongside you, from a side panel in Chrome or from Claude Cowork and Claude Code.
when: Use it when the work is on a page already in front of you, with the accounts you are signed in to, or when you want Claude Code to test what it built in a real browser. Use a connector when one exists for the service.
replaces: Copying page content into a chat, and clicking through repetitive web forms and consoles by hand.
example_kind: prompt
docs:
  - title: Get started with Claude in Chrome
    url: https://support.claude.com/en/articles/12012173-get-started-with-claude-in-chrome
  - title: Use Claude in Chrome safely
    url: https://support.claude.com/en/articles/12902428-use-claude-in-chrome-safely
verified: 2026-11-11
---
## Try it in a minute
1. In Google Chrome, visit the [Chrome Web Store](https://chromewebstore.google.com/detail/claude/fcoeoabgfenejglbffodgkkbkcdhcgfn) page for Claude and click **Add to Chrome**.
2. Sign in with your Claude account when prompted and grant the permissions.
3. Pin the extension by clicking the puzzle piece icon, then the thumbtack next to **Claude**.
4. Click the Claude icon in the Chrome toolbar to open the side panel next to the page you are on.
5. Ask about the page, or ask Claude to carry out a task on it while you watch.

## Example
```text
Open the volume list page in this tab and create a test volume through the form.

Read the browser console and network requests while you do it. Tell me which request fails, its status code and any console errors. Do not touch any volume that already exists.
```

## At work
- **Build, test, verify.** With Claude Code, build in the terminal and then have Claude test in the browser. It can read console errors, network requests and DOM state directly.
- **Across tabs.** Drag tabs into Claude's tab group so it can compile information from all of them at once.
- **Repeatable prompts.** Save a prompt that works as a shortcut and reuse it by typing `/` in the chat.

## Pitfalls
- It is for paid plans and works only in Google Chrome, not other Chromium-based browsers or mobile devices.
- Hidden instructions in web content can trick Claude. Safety classifiers screen for this, but the risk is not zero.
- Claude cannot filter sensitive content out of what it sees. Avoid sensitive sites and consider a separate browser profile.
- The side panel starts in "Automatically approve" mode. Switch modes if you want to approve each action.
- On Team and Enterprise plans an admin controls availability and which sites Claude may access.
