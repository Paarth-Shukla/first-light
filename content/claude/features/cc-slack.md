---
id: cc-slack
title: Claude Code in Slack
surface: code
group: Integrations
status: stable
level: intermediate
payoff: 2
effort: 2
jobs: [coding, debugging, automation]
tags: [slack, delegation, cloud, mentions]
summary: Claude Code in Slack turns an @Claude mention with a coding task into a Claude Code cloud session and reports progress back in the thread.
when: Use it to hand off a bug that is being discussed in a channel without leaving the conversation. Work in the web interface instead when you need to upload files or steer in real time.
replaces: Copying a bug report out of Slack into a new session and pasting the result back.
example_kind: prompt
docs:
  - title: Claude Code in Slack
    url: https://code.claude.com/docs/en/slack
verified: 2026-11-11
---
## Try it in a minute
1. A workspace administrator installs the Claude app from the Slack App Marketplace.
2. Open the Claude app's App Home in Slack and click **Connect Claude account**.
3. At claude.ai/code, connect GitHub and authenticate at least one repository with the same account.
4. Pick a **Routing Mode** in the App Home, then invite the app to a channel with `/invite @Claude`.
5. Mention `@Claude` with a coding request. When it finishes, use **View session** or **Create PR**.

## Example
```text
@Claude in the replicator repo, the nightly job fails with "snapshot lease expired". Stack trace: <paste the trace here>. Find the cause, fix it, add a regression test, and tell me what changed.
```

## At work
- **Bug reports in a channel.** Claude gathers context from your messages in the thread, picks a repository and starts a session, posting status updates as it goes.
- **Asynchronous starts.** Kick off a task from Slack and get a direct message when it completes.

## Pitfalls
- The page marks this as an earlier version. It answers channel mentions only from Pro, Max and Ultra accounts, in a workspace that no organization has connected to Claude Tag. Team and Enterprise organizations are pointed to Claude Tag instead.
- It works in channels only, not direct messages.
- Repositories must be on GitHub, and each session can create one pull request.
- Claude may follow directions from other messages in the conversation context, so use it only in trusted Slack conversations.
- Claude reads your messages and its own, not your teammates'. Paste a colleague's error report into the message where you mention it.
