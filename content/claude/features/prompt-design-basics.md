---
id: prompt-design-basics
title: Prompt design basics
surface: apps
group: Habits
status: stable
level: starter
payoff: 3
effort: 1
jobs: [writing, coding, review, analysis, learning]
tags: [prompting, context, examples, xml-tags, clarity]
summary: A short set of documented prompting habits that make Claude's answers more useful, starting with being clear and direct and giving the context a new colleague would need.
when: Apply these whenever a first answer comes back generic or misses the point. They cost a minute of typing and usually save several rounds of correction.
replaces: One-line prompts followed by a string of corrective follow-ups.
example_kind: prompt
docs:
  - title: Introduction to prompt design
    url: https://support.claude.com/en/articles/7996853-introduction-to-prompt-design
  - title: Prompting best practices
    url: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
verified: 2026-11-11
---
## Try it in a minute
1. Write the request as you would brief a newly hired contractor who has no context about you, your task or your organization.
2. Use numbered steps when the order matters.
3. Say why an instruction matters. Claude can generalize from the explanation.
4. Wrap pasted material in descriptive XML tags, put long documents at the top and your question at the end.
5. Apply the docs' key test. If a colleague with minimal context would be confused by the prompt, Claude will be too.

## Example
```text
<document>
<source>design-doc-tiering-v3.md</source>
<document_content>
[paste the design doc]
</document_content>
</document>

Review this design as a senior storage engineer. I need the five most important concerns, not a full audit.

First quote the passages that worry you inside <quotes> tags. Then give each concern as one sentence of risk plus the question I should ask the author. Write plain prose, because I will paste this into a comment thread.
```

## At work
- **Code and design review.** A one-sentence role focuses Claude's behavior and tone for the task.
- **Consistent write-ups.** The docs call examples one of the most reliable ways to steer format, tone and structure. Include 3 to 5, wrapped in `<example>` tags.
- **Long documents.** Asking Claude to quote the relevant parts first helps it focus on what matters and ignore the rest.

## Pitfalls
- If you want Claude to do more than the task strictly requires, ask for it explicitly.
- Tell Claude what to do instead of what not to do. "Write in flowing prose paragraphs" works better than "do not use markdown".
- Make examples diverse, or Claude picks up unintended patterns.
- The detailed guide is written for API users, so sections such as system prompts do not apply directly to the chat app.
