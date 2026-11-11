---
id: api-prompting-best-practices
title: Prompting best practices
surface: platform
group: Prompting
status: stable
level: starter
payoff: 3
effort: 1
jobs: [writing, coding, automation, learning]
tags: [prompting, xml-tags, examples, system-prompt]
summary: The official reference for prompting current Claude models, covering clear instructions, context, examples, XML tags, roles, long documents, output format, tool use and agentic work.
when: Reach for it when a prompt in a script gives vague, wordy or inconsistent results. Read the page for your model first, then the general techniques.
replaces: Trial-and-error prompt tweaking and rules carried over from older models.
example_kind: command
docs:
  - title: Prompting best practices
    url: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
verified: 2026-11-11
---
## Try it in a minute
1. Set a role in the `system` prompt. The page says even a single sentence makes a difference.
2. Say exactly what output you want, as numbered steps when order matters, and explain why a constraint exists.
3. Wrap each kind of content in its own XML tag, such as `<instructions>`, `<context>` and `<input>`.
4. Put long documents at the top of the prompt and your question at the end.
5. Add 3 to 5 relevant, varied examples inside `<example>` tags when format or tone matters.

## Example
```bash
curl https://api.anthropic.com/v1/messages \
  -H "content-type: application/json" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-10-21" \
  -d '{
    "model": "claude-opus-5-5",
    "max_tokens": 1024,
    "system": "You are a senior storage engineer reviewing a design document for a colleague.",
    "messages": [
      {"role": "user", "content": "<documents><document index=\"1\"><source>snapshot-retention-design.md</source><document_content>PASTE THE DESIGN DOC HERE</document_content></document></documents>\n\n<instructions>Find quotes from the document that describe failure handling and place them in <quotes> tags. Then list the failure cases the design does not cover, most serious first. The list goes into a Confluence comment, so use short bullet points and no preamble.</instructions>"}
    ]
  }'
```

## At work
- **Design doc and code review prompts**: asking Claude to quote the relevant passages first helps it focus on the right part of a long document.
- **Status reports and incident summaries**: stating the audience and format, and the reason for them, gives a result you can paste without editing.
- **Agents that should act**: write "Change this function" rather than "Can you suggest some changes", or Claude may only suggest.

## Pitfalls
- Prefilled assistant responses on the last turn return a 400 error from Claude 4.6 models onward. Use structured outputs or a direct instruction such as "Respond directly without preamble".
- Setting `budget_tokens` returns a 400 error on Claude 4.7 and later models. Use effort to control thinking depth.
- Instructions written to push older models, such as "If in doubt, use the tool", can cause overtriggering now. Remove them.
- Tell Claude what to do instead of what not to do.
- Each current model has its own prompting page with measured differences. Re-check a technique against your own evals before applying it to another model.
