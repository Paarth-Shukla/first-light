---
id: cc-agent-sdk
title: Agent SDK
surface: code
group: Automation
status: stable
level: power
payoff: 2
effort: 3
jobs: [automation, coding]
tags: [agent-sdk, python, typescript, library, agents]
summary: The Agent SDK is a Python and TypeScript library that gives your own program the same tools, agent loop and context management that power Claude Code.
when: Use it when you want to embed an agent in an application or service you operate, with code deciding what to do with each message, rather than shelling out to the CLI.
replaces: Writing your own tool-calling loop, file tools and permission handling around the API.
example_kind: config
docs:
  - title: Agent SDK overview
    url: https://code.claude.com/docs/en/agent-sdk/overview
  - title: Agent SDK quickstart
    url: https://code.claude.com/docs/en/agent-sdk/quickstart
verified: 2026-11-11
---
## Try it in a minute
1. In a new folder, create a virtual environment and run `pip install claude-agent-sdk`. For TypeScript, run `npm install @anthropic-ai/claude-agent-sdk`.
2. Get an API key from the Claude Console and run `export ANTHROPIC_API_KEY=your-api-key`.
3. Save the script below as `agent.py` next to a `utils.py` you want checked.
4. Run `python agent.py`. The run ends with `Done: success`.

## Example
```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage


async def main():
    async for message in query(
        prompt="Review utils.py for bugs that would cause crashes. Fix any issues you find.",
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Edit", "Glob"],
            permission_mode="acceptEdits",
        ),
    ):
        if isinstance(message, ResultMessage):
            print(f"Done: {message.subtype}")


asyncio.run(main())
```

## At work
- **Internal tooling.** Put the agent behind a job or bot your team already uses, with your code filtering the message stream.
- **Same setup as your terminal.** Skills, commands and memory load from the project's `.claude/` and from `~/.claude/`, and hooks, subagents, MCP and permissions are available as options.
- **Other languages.** The docs suggest running the CLI as a subprocess with `-p` and `--output-format json` when you are not using Python or TypeScript.

## Pitfalls
- Authenticate with an API key or a supported cloud provider. Unless previously approved, Anthropic does not allow third-party developers to offer claude.ai login or rate limits in their products.
- The SDK reads the key from the process environment and does not load `.env` files for you.
- The quickstart lists Node.js 18.14+ or Python 3.10+ as prerequisites.
- Both SDKs bundle a native Claude Code binary, but some installs get none, for example `npm ci --omit=optional`.
- A product built on the SDK must keep its own branding and may not present itself as Claude Code.
