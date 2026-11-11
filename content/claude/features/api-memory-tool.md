---
id: api-memory-tool
title: Memory tool
surface: platform
group: Context
status: stable
level: intermediate
payoff: 2
effort: 2
jobs: [automation, coding, planning]
tags: [memory, persistence, agents, client-tools]
summary: The memory tool lets Claude create, read, update and delete files under a /memories directory that your application stores, so knowledge persists between conversations.
when: Reach for it when a script or agent runs repeatedly on the same project and should pick up where the last run stopped. For a one-off call, put the context in the prompt instead.
replaces: Re-sending the same background notes, decisions and progress log at the start of every run.
example_kind: command
docs:
  - title: Memory tool
    url: https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool
verified: 2026-11-11
---
## Try it in a minute
1. Add `{"type": "memory_20250818", "name": "memory"}` to `tools`. That entry is the whole configuration, and the name must be `memory`.
2. Handle the memory commands in your application. In Python the SDK ships `BetaLocalFilesystemMemoryTool`, which stores files on local disk.
3. Run a task and tell Claude something worth keeping.
4. Start a new conversation with the same tool and the same store. Claude checks its memory directory before starting work.

## Example
```python
import anthropic
from anthropic.tools import BetaLocalFilesystemMemoryTool

client = anthropic.Anthropic()
memory = BetaLocalFilesystemMemoryTool(base_path="./memory")

runner = client.beta.messages.tool_runner(
    model="claude-opus-5-5",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": "Remember that the storage team freezes releases on Thursdays and that flaky test reports go to the QA channel, not to Jira.",
        }
    ],
    tools=[memory],
)

final_message = runner.until_done()
print(final_message.content)
```

## At work
- **Multi-session coding agents**: the docs describe a pattern where the first session writes a progress log and a feature checklist, each later session reads them first, and each session updates the log before it ends.
- **A weekly status script** that remembers last week's decisions and open items instead of being told again.
- **Long-running agents**: pair memory with compaction, so that what must survive summarisation is written to files.

## Pitfalls
- It is client-side. Claude only requests operations; your code runs them and decides where the data lives.
- Validate every path. A path such as `/memories/../../secrets.env` can escape the directory unless your handler rejects it.
- Cap file sizes and periodically delete memory files that have not been accessed for a long time.
- Claude usually refuses to write sensitive information to memory, but add your own validation if you need a guarantee.
- The API adds its own memory instruction to the system prompt when the tool is present, so you do not need to send one.
- The SDK helpers live in the beta namespace, although the tool itself needs no beta header.
