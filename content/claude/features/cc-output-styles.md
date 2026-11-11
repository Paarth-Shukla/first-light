---
id: cc-output-styles
title: Output styles
surface: code
group: Setup and cost
status: stable
level: starter
payoff: 2
effort: 1
jobs: [learning, coding, writing]
tags: [output-styles, concise, explanatory, tone]
summary: An output style is a set of instructions that sets Claude's role, tone and response format for every response in a session.
when: Switch style when you want every reply shorter, or want the reasoning explained along with each change, instead of repeating that request in each prompt.
replaces: Ending prompts with "keep it short" or "explain why you did that".
example_kind: config
docs:
  - title: Output styles
    url: https://code.claude.com/docs/en/output-styles
verified: 2026-11-11
---
## Try it in a minute
1. Run `/output-style` to list the styles and see the current one.
2. Run `/output-style concise` for responses that lead with the result and skip preamble.
3. Run `/output-style explanatory` while learning a codebase. Claude adds short `Insight` blocks about why it made its choices.
4. For your own style, save a Markdown file in `~/.claude/output-styles` or the project's `.claude/output-styles`, restart Claude Code, then select it.

## Example
`.claude/output-styles/design-reviewer.md`:

```markdown
---
name: Design reviewer
description: Explain changes the way a design review expects
keep-coding-instructions: true
---

When you explain a change, lead with the decision and the alternative
you rejected, then the risk and how to roll back.

Use short paragraphs. Name the file and function for every claim about
existing behaviour. End with open questions for the reviewer.
```

## At work
- **Getting to know a codebase.** Explanatory gives you the reasoning along with the change. Learning also leaves small pieces marked `TODO(human)` for you to write.
- **Routine work.** Concise states what happened in the first sentence while doing the engineering work as thoroughly as the default.
- **Hands-off sessions.** Proactive makes reasonable assumptions on routine decisions instead of stopping to ask.

## Pitfalls
- A style gives Claude instructions. It does not guarantee something always or never happens, so use a hook for that.
- In a settings file the `outputStyle` value is case-sensitive, as in `"Explanatory"`. A value that does not match exactly gives you the Default style. The `/output-style` command ignores case.
- Your choice is saved to `.claude/settings.local.json`. Set `outputStyle` in `~/.claude/settings.json` for a default across projects.
- Leave out `keep-coding-instructions: true` only if Claude will not be doing software engineering in that style.
