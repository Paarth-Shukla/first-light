---
id: api-code-execution-tool
title: Code execution tool
surface: platform
group: Tools
status: stable
level: intermediate
payoff: 3
effort: 1
jobs: [analysis, automation, debugging]
tags: [code-execution, sandbox, data-analysis, server-tools]
summary: The code execution tool lets Claude run Bash commands and write and run code in a sandboxed container on Anthropic's side, then return results and generated files in the same request.
when: Reach for it when the answer needs real computation or file handling, such as statistics over a CSV, parsing a log bundle or drawing a chart, and you do not want to host a sandbox yourself.
replaces: Copying generated code into a local notebook, running it and pasting the output back.
example_kind: command
docs:
  - title: Code execution tool
    url: https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool
verified: 2026-11-11
---
## Try it in a minute
1. Add `{"type": "code_execution_20250825", "name": "code_execution"}` to `tools`. No beta header is required.
2. Ask for something that needs computation. For a borderline request, say so explicitly, for example "run code to verify this".
3. Read the response. `server_tool_use` blocks show the commands Claude ran, followed by their results and Claude's text.
4. To analyse your own file, upload it with the Files API and reference it with a `container_upload` content block.

## Example
```bash
curl --fail-with-body -sS https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-10-21" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-opus-5-5",
    "max_tokens": 4096,
    "messages": [
      {
        "role": "user",
        "content": "Use the code execution tool to calculate the mean, p95 and p99 of these request latencies in ms: [12, 15, 11, 240, 14, 13, 18, 16, 900, 12]"
      }
    ],
    "tools": [
      {
        "type": "code_execution_20250825",
        "name": "code_execution"
      }
    ]
  }'
```

## At work
- **Spreadsheet and CSV analysis**: the container ships with pandas, numpy, matplotlib and openpyxl, so a script can turn a metrics export into numbers and a chart.
- **Reports as files**: files Claude copies into `$OUTPUT_DIR` come back as file ids you download through the Files API. Files written elsewhere stay in the container.
- **Multi-step analysis**: pass the `container` id from one response into the next request to keep created files.

## Pitfalls
- The container has no internet access. Only the pre-installed libraries are available, and nothing can be installed at runtime.
- Each request gets a new container unless you send an earlier container id. Containers expire 30 days after creation.
- Resources are fixed at 5 GiB of RAM, 5 GiB of disk and 1 CPU.
- Billing is by execution time with a 5-minute minimum, after a monthly allowance of free hours. The page says code execution is free when a current web search or web fetch tool is in the same request.
- If you also give Claude your own shell tool, it can confuse the two environments. Tell it in the system prompt that state is not shared.
