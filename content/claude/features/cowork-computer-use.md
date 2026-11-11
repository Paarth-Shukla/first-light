---
id: cowork-computer-use
title: Computer use in Cowork
surface: cowork
group: Delegate
status: beta
level: power
payoff: 2
effort: 3
jobs: [automation, debugging, analysis]
tags: [cowork, computer-use, desktop, apps, permissions]
summary: Computer use lets Claude interact directly with your screen in the Claude Desktop app, clicking, typing and opening apps, when no connector or tool exists for what you need.
when: Reach for it only for apps with no connector and no usable web interface, such as an internal dashboard or a simulator. Connectors and the browser are faster and more reliable, and Claude tries them first.
replaces: Clicking through a GUI-only tool yourself to collect information or repeat the same steps.
example_kind: prompt
docs:
  - title: Let Claude use your computer in Cowork
    url: https://support.claude.com/en/articles/14128542-let-claude-use-your-computer-in-cowork
  - title: Use Claude Cowork safely
    url: https://support.claude.com/en/articles/13364135-use-claude-cowork-safely
verified: 2026-11-11
---
## Try it in a minute
1. Update Claude Desktop to the latest version.
2. Go to **Settings > Capabilities**. If there is no **Computer use** section there, go to **Settings > System**, under **This computer**.
3. Turn on the **Enable computer use** toggle.
4. Open Cowork in the desktop app, start a session and ask for something that involves an app on your computer.
5. Approve the permission prompt for each application Claude needs.

## Example
```text
Open the iOS simulator that is already running our field-service app.

Walk through the "replace failed drive" flow from the alert screen to confirmation. Note every place where the next step is unclear or a label is truncated. Do not change any settings or data. List the findings.
```

## At work
- **GUI-only internal tools.** Navigate apps without connectors, such as an internal dashboard or a specialized tool your team uses.
- **App walkthroughs.** Have Claude open a phone simulator, interact with the app you developed and find UX issues.
- **Keep working meanwhile.** On macOS 15 or later Claude works in background windows and does not take over your pointer or keyboard.

## Pitfalls
- Computer use is in beta for Pro, Max and Ultra plans. Team and Enterprise plans do not have access at this time.
- There is no sandbox between Claude and your applications. Claude takes screenshots and can see anything visible in the apps you allow, so close sensitive files first.
- Your computer must be awake and the Claude Desktop app open.
- Screen interaction is slower and more error-prone than connectors, and complex multi-step workflows sometimes need a second try.
- Do not give it access to banking, healthcare or other sensitive apps. Use the app blocklist to deny specific apps.
- Actions in one app can affect another, such as a link in mail opening in a browser.
