---
id: chat-search
title: Search past chats
surface: apps
group: Context
status: stable
level: starter
payoff: 2
effort: 1
jobs: [research, writing, planning]
tags: [search, history, context, rag]
summary: Chat search lets you ask Claude to find and reference what you discussed in previous conversations.
when: Use it when you know you worked something out with Claude before and want to continue from there, instead of scrolling the sidebar or explaining it again.
replaces: Hunting through old chats for the one where you settled a design question, then copy-pasting the relevant part.
example_kind: prompt
docs:
  - title: Use Claude's chat search and memory to build on previous context
    url: https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context
  - title: Usage limit best practices
    url: https://support.claude.com/en/articles/9797557-usage-limit-best-practices
verified: 2026-11-11
---
## Try it in a minute
1. Open a new chat. Once the feature has rolled out to your account it is on by default.
2. Ask naturally, for example "What did we discuss about [topic]?" or "Let's continue where we left off with [project]."
3. Watch for the tool call in the chat. That is Claude searching your previous conversations.
4. Follow the citations in the answer back to the original chats to confirm the details.

## Example
```text
Find our earlier conversation about the snapshot retention policy for the backup service.

Summarize what we decided, list the open questions we left, and then draft the "Decision" section of the design doc from it. Link the chats you used.
```

## At work
- **Picking up a design thread.** Resume a multi-day discussion without re-explaining the constraints you already worked through.
- **Writing from your own history.** Turn several past debugging chats into one incident write-up or a runbook entry, with links to the conversations it came from.
- **Less repetition, less usage.** The usage best-practice guide points out that letting Claude pull prior context saves you from providing the same information repeatedly.

## Pitfalls
- Searching past chats is for paid plans, per the docs.
- Scope is limited. From a chat outside projects Claude searches all chats outside projects. Inside a project it searches only that project's conversations.
- Incognito chats are never searched, and a chat started with memory turned off does not search your past chats.
- You can switch it off with the **Search and reference chats** toggle in **Settings > Your Claude** (or **Settings > Memory** in the older Settings layout).
- It is not available if your organization uses customer-managed encryption keys on an Enterprise plan.
- Citations include an option to delete the referenced conversation. Deleting is separate from memory, which keeps entries generated from deleted chats.
