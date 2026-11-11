---
id: api-computer-use-tool
title: Computer use tool
surface: platform
group: Tools
status: stable
level: power
payoff: 2
effort: 3
jobs: [automation, debugging]
tags: [computer-use, desktop, screenshots, client-tools]
summary: The computer use tool gives Claude screenshot, mouse and keyboard control of a desktop environment that you host, through one toolset entry in the tools array.
when: Reach for it only when a task needs a real desktop and there is no API or command line for the job, such as driving a legacy admin GUI in a test rig. For work that stays inside web pages the docs point to the browser use tool instead.
replaces: Clicking through a GUI by hand for repetitive checks that have no scriptable interface.
example_kind: command
docs:
  - title: Computer use tool
    url: https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool
verified: 2026-11-11
---
## Try it in a minute
1. Start a sandboxed desktop. The docs link a reference implementation that runs a virtual display, a lightweight Linux desktop and the agent loop inside a Docker container.
2. Add `{"type": "computer_toolset_20260801"}` to `tools`. The request needs no beta header.
3. Send a prompt that requires desktop interaction. Claude replies with `tool_use` blocks such as `screenshot`, `left_click` and `type`, each carrying `"toolset_name": "computer"`.
4. Run every call in order in your environment and return one `tool_result` per call, each echoing `"toolset_name": "computer"`. Return an image for `screenshot` and `zoom`; a short text such as `OK` is enough for the rest.
5. Repeat until Claude answers in text.

## Example
```bash
curl https://api.anthropic.com/v1/messages \
  -H "content-type: application/json" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-10-21" \
  -d '{
    "model": "claude-opus-5-5",
    "max_tokens": 1024,
    "tools": [
      {
        "type": "computer_toolset_20260801"
      },
      {
        "type": "text_editor_20250728",
        "name": "str_replace_based_edit_tool"
      },
      {
        "type": "bash_20250124",
        "name": "bash"
      }
    ],
    "messages": [
      {
        "role": "user",
        "content": "Open the storage admin console in Firefox, go to the Volumes page and save a screenshot of the capacity chart to the desktop."
      }
    ]
  }'
```

## At work
- **Automated UI testing** of a management console that has no API. The docs name automated software testing as a fitting use, because speed is not critical.
- **Background information gathering** from desktop applications in a trusted, isolated VM.

## Pitfalls
- It is a client tool. Claude never connects to your machine; your application performs every action and stores every screenshot.
- Use a dedicated VM or container with minimal privileges, keep credentials out of it and limit internet access to an allowlist. Instructions on web pages or in images can override yours.
- Ask a human to confirm actions with real-world consequences.
- Claude can click wrong coordinates or pick the wrong action. Set `display: "summarized"` on thinking to see its reasoning, and review the logs.
- The toolset definition adds about 4,500 input tokens per request, and screenshots are billed as image input.
- Current models return a 400 error for older tool versions such as `computer_20251124`.
