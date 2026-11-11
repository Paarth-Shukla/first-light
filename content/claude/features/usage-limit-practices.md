---
id: usage-limit-practices
title: Working within usage limits
surface: apps
group: Habits
status: stable
level: starter
payoff: 2
effort: 1
jobs: [planning, coding, writing, research]
tags: [limits, usage, caching, context]
summary: A set of documented habits for getting more work out of your plan's session and weekly usage limits.
when: Apply these when you keep hitting your limit mid-task, or before a long working session where running out would hurt.
replaces: Firing off many short follow-up messages and re-uploading the same files until the limit cuts you off.
example_kind: prompt
docs:
  - title: Usage limit best practices
    url: https://support.claude.com/en/articles/9797557-usage-limit-best-practices
  - title: How do usage and length limits work?
    url: https://support.claude.com/en/articles/11647753-how-do-usage-and-length-limits-work
verified: 2026-11-11
---
## Try it in a minute
1. Open [Settings > Usage](https://claude.ai/settings/usage) and look at **Current session** and **Weekly limits** to see where you stand.
2. Put documents you reference repeatedly into a project. Project content is cached and counts less when reused.
3. Combine related questions into a single message with all the background up front.
4. Lower the effort level for routine tasks, and turn off connected apps a conversation does not need.
5. Start a new conversation when a long chat is close to your limit.

## Example
```text
Context: Go 1.22 service, PostgreSQL 15, running on Kubernetes. Full handler and its test are pasted below.

In one reply, please:
1. Explain why TestRetryBackoff fails intermittently.
2. Give the smallest fix as a diff.
3. List any other place in this file with the same bug.
4. Suggest one extra test that would have caught it.

[paste handler.go and handler_test.go]
```

## At work
- **Code review and debugging.** Give complete context about your environment in the first message and include entire relevant snippets.
- **Editing documents.** Send the whole text for editing in one message rather than in pieces.
- **Pacing.** The session limit resets five hours after your first message and the weekly limit at a fixed time assigned to your account.

## Pitfalls
- Usage across claude.ai, Claude Code and Claude Desktop counts toward the same limit.
- Tools and connectors are token-intensive. Research, web search, file creation, higher effort and model choice all affect how fast you use your limit.
- Project caches expire after a period of inactivity. Your first message after a long break counts that content in full again.
- Long conversations that trigger automatic context management consume more of your limit.
- Usage limits and length limits are different. Hitting a length limit means starting a new conversation, not waiting.
