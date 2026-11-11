---
id: cc-subagents
title: Subagents
surface: code
group: Parallel work
status: stable
level: intermediate
payoff: 3
effort: 2
jobs: [coding, review, debugging, research]
tags: [subagents, delegation, context, agents]
summary: A subagent is a specialised worker that runs a side task in its own context window and returns only a summary to your conversation.
when: Delegate when a side task would flood your conversation with search results, logs or file contents you will not look at again, or when you keep spawning the same kind of worker.
replaces: Scrolling past pages of exploration output and re-typing the same reviewer instructions in each session.
example_kind: config
docs:
  - title: Create custom subagents
    url: https://code.claude.com/docs/en/sub-agents
  - title: Run agents in parallel
    url: https://code.claude.com/docs/en/agents
  - title: Checkpointing
    url: https://code.claude.com/docs/en/checkpointing
verified: 2026-11-11
---
## Try it in a minute
1. Ask Claude to create one, saying what it does, where to save it, which tools it may use and which model.
2. Open the generated file and check the `name`, `description`, `tools` and `model` frontmatter.
3. Delegate by name, `Use the log-triage agent on the last test run`, or type `@` and pick the agent to guarantee it runs.
4. Move the file to the project's `.claude/agents/` directory and commit it to share it with the team.

## Example
`.claude/agents/log-triage.md`:

```markdown
---
name: log-triage
description: Reads test and service logs and reports the failing step with evidence. Use proactively after a failed test run.
tools: Read, Grep, Glob, Bash
model: haiku
---

You triage failures. Read the logs you are pointed at, find the first
real error, and report the failing step, the relevant log lines with
file paths, and the most likely cause. Do not edit files.
```

## At work
- **Log and test triage.** Thousands of log lines stay in the subagent's context and you get a short report.
- **Independent review.** A reviewer subagent starts fresh, so it has not seen the reasoning that produced the code.
- **A side task with full context.** `/subtask draft unit tests for the parser changes so far` starts a fork that inherits the whole conversation and reports back when done.

## Pitfalls
- Each subagent sends its own requests, which count toward the same usage limits as your main conversation.
- A non-fork subagent starts fresh. It gets its own system prompt and the task Claude writes for it, not your conversation.
- Keep descriptions short. Claude Code warns at startup when the combined descriptions pass 15,000 tokens.
- `/rewind` usually does not restore a subagent's edits. Use git for those.
