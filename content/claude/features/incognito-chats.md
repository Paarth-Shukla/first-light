---
id: incognito-chats
title: Incognito chats
surface: apps
group: Context
status: stable
level: starter
payoff: 1
effort: 1
jobs: [writing, research, learning]
tags: [privacy, memory, history]
summary: An incognito chat is a temporary conversation that is not saved to your chat history or to Claude's memory.
when: Use one for a one-off question you do not want shaping future answers or cluttering your history. If you want to keep the chat but skip memory, turn off Memory for that chat instead.
replaces: Deleting a chat afterwards and then pruning what it added to memory.
example_kind: prompt
docs:
  - title: Use incognito chats
    url: https://support.claude.com/en/articles/12260368-use-incognito-chats
  - title: Use Claude's chat search and memory to build on previous context
    url: https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context
verified: 2026-11-11
---
## Try it in a minute
1. Start a new chat outside of a project.
2. Click the ghost icon in the upper right corner of the screen.
3. Check for the black border and the **Incognito chat** label in the upper left corner.
4. Have your conversation, and copy out anything you need to keep.
5. Click the **x** in the upper right corner to close it.

## Example
```text
I am preparing for a difficult conversation with a colleague about missed handoffs during on-call.

Play the colleague. Push back the way a defensive but reasonable engineer would. After five exchanges, stop and tell me which of my phrasings made things worse and how to say them better.
```

## At work
- **Practice and personal topics.** Rehearse a hard conversation or think through a career question without it appearing in memory or in your monthly recap.
- **Clean-slate answers.** An incognito chat does not use Claude's existing memory, so it is a quick way to see how Claude answers without your saved context.
- **Unrelated side quests.** Keep a one-off question about a hobby from influencing work chats.

## Pitfalls
- Incognito is not the same as deleted. Chats are retained for 30 days by default, or longer under an organization's data retention setting.
- On Team and Enterprise plans, incognito chats are included in organizational data exports available to Owners.
- Claude can still access your profile information, such as personal preferences, in an incognito chat.
- An incognito chat cannot be converted to a regular chat, and once closed it cannot be reopened.
- It is only available outside projects. Inside a project, turn off **Memory** in the **+** menu before your first message.
- If you have the new Claude experience, incognito chats open in the previous chat experience, so Claude cannot create files or run code in them.
