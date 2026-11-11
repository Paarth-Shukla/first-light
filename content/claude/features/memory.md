---
id: memory
title: Memory
surface: apps
group: Context
status: stable
level: starter
payoff: 3
effort: 1
jobs: [writing, planning, coding, meetings]
tags: [memory, personalization, context, settings]
summary: Memory lets Claude save context from your chats as individual topics and carry it into new conversations and cloud Cowork tasks.
when: Rely on memory for stable facts about you, such as your role, your stack, the people you work with and how you like things written. Use a project when the context is a body of documents.
replaces: Opening every chat with the same paragraph about who you are, what you work on and how you want answers formatted.
example_kind: prompt
docs:
  - title: Use Claude's chat search and memory to build on previous context
    url: https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context
verified: 2026-11-11
---
## Try it in a minute
1. Go to **Settings > Your Claude** (or **Settings > Memory** in the older Settings layout) and check that **Generate memory from chats** is on.
2. In a chat, tell Claude to "remember this" along with the facts you want kept.
3. Select **Manage** next to **Your memory** to see what is saved under **Topics**. Open a topic to edit or delete it.
4. Start a new chat and ask for something that depends on those facts.
5. For a chat that should not touch memory, click **+** in the message box and turn off **Memory** before you send the first message.

## Example
```text
Remember this about how I work:
- I am a software engineer on a storage infrastructure team. Most of my code is Go and Python, and I work in VS Code.
- Our tickets live in Jira and our design docs in Confluence.
- For status updates, write three short sections named Done, Next and Risks.
- When you review code, lead with correctness problems and keep style notes to a short list at the end.
```

## At work
- **Consistent output without preamble.** Status reports and review comments come back in your format from the first message.
- **One memory across chat and Cowork.** What Claude learns in chat is available to Cowork tasks that run in the cloud, and the reverse.

## Pitfalls
- By default Claude does not store sensitive topics such as health or politics unless you turn on **Include sensitive topics in memory**. Some information, such as government ID and financial account numbers, is never saved.
- Deleting a conversation does not remove memory entries generated from it. Delete the memory itself.
- **Reset memory** permanently deletes all memories, including project memories.
- On Team and Enterprise plans, owners control whether memory is available.
