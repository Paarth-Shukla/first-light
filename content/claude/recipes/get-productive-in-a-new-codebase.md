---
id: get-productive-in-a-new-codebase
title: Get productive in an unfamiliar codebase in an afternoon
job: learning
level: starter
minutes_saved: 60
features: [cc-common-workflows, cc-subagents, cc-code-intelligence]
prerequisites: [Claude Code installed, A local clone of the repository]
fields:
  - name: background
    label: Your background
    placeholder: backend engineer who knows Go and Python but not this storage stack
  - name: first_task
    label: The first thing you need to do here
    placeholder: add a retry budget to the snapshot upload path
  - name: flow_to_trace
    label: One flow to trace end to end
    placeholder: a snapshot create request from the API handler to disk
docs:
  - title: Common workflows
    url: https://code.claude.com/docs/en/common-workflows
  - title: Create custom subagents
    url: https://code.claude.com/docs/en/sub-agents
  - title: Best practices for Claude Code
    url: https://code.claude.com/docs/en/best-practices
verified: 2026-11-11
---
## Steps
1. `cd` to the project root and run `claude`.
2. Send the prompt below. The docs' advice is to start broad, then narrow.
3. Follow up on one area at a time, for example `find the files that handle snapshot retention`, then `how do these files work together?`.
4. For a deep dive, say `use a subagent to investigate how` followed by your question. The subagent reads files in its own context window and reports a summary.
5. For a typed language, install a code intelligence plugin so Claude can jump to definitions and find references.

## Prompt
```text
I am a {{background}} and I have just joined the team that owns this repository. By the end of today I need to be able to {{first_task}}.

Give me an overview of this codebase aimed at that goal. Read the code before answering and name the files you relied on so I can open them. Cover:
1. What the system does and its main components.
2. The main architecture patterns and the key data models.
3. One flow traced end to end: {{flow_to_trace}}. List each file and function on the path.
4. How to build it, run it and run a single test.
5. Coding conventions a reviewer here would expect me to follow.
6. A glossary of project-specific terms.

Then list the five files I should read first for {{first_task}}, in order, with one sentence on why each matters. Mark anything you inferred but could not confirm in the code.
```

## Why it works
The overview, architecture patterns, data models, conventions and glossary are the questions the common workflows page recommends for a new codebase, combined into one pass. Saying what you know and what you must do today turns a generic tour into a reading list for your task.
