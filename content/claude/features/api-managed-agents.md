---
id: api-managed-agents
title: Claude Managed Agents
surface: platform
group: Agents
status: beta
level: power
payoff: 3
effort: 3
jobs: [automation, coding, research]
tags: [agents, sandbox, sessions, long-running, beta]
summary: Claude Managed Agents is a pre-built agent harness on managed infrastructure, where Claude reads files, runs commands, browses the web and runs code in a sandbox while you send and receive events.
when: Reach for it for long-running or asynchronous tasks when you do not want to build your own agent loop, sandbox and tool execution. Use the Messages API when you need a custom loop and fine-grained control.
replaces: Building and operating your own agent loop, tool runner and sandboxed runtime.
example_kind: command
docs:
  - title: Claude Managed Agents overview
    url: https://platform.claude.com/docs/en/managed-agents/overview
  - title: Get started with Claude Managed Agents
    url: https://platform.claude.com/docs/en/managed-agents/quickstart
verified: 2026-11-11
---
## Try it in a minute
1. Create an agent with a POST to `/v1/agents`, giving its model, system prompt and tools. Save the returned agent id.
2. Create an environment with a POST to `/v1/environments`. It defines the sandbox and its networking. Save the environment id.
3. Start a session with a POST to `/v1/sessions` that references both ids.
4. Open the event stream with the SDK, send a `user.message` event and read events until `session.status_idle`.
5. Send more user events to steer the agent while it runs, or interrupt it.

## Example
```bash
curl -sS --fail-with-body https://api.anthropic.com/v1/agents \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-10-21" \
  -H "anthropic-beta: managed-agents-2026-04-01" \
  -H "content-type: application/json" \
  -d '{
    "name": "Coding Assistant",
    "model": "claude-opus-5-5",
    "system": "You are a helpful coding assistant. Write clean, well-documented code.",
    "tools": [
      {
        "type": "agent_toolset_20260401",
        "configs": [
          {"name": "web_search", "enabled": false},
          {"name": "web_fetch", "enabled": false}
        ]
      }
    ]
  }'
```

## At work
- **Tasks that run for minutes or hours**, such as reproducing a bug across several test runs. The session keeps its filesystem and conversation history between interactions.
- **Recurring jobs**: the overview lists scheduled deployments that run an agent on a cron schedule.
- **Less plumbing**: prompt caching and compaction are built into the harness, so you do not wire them up yourself.

## Pitfalls
- It is in beta. Every endpoint needs the `managed-agents-2026-04-01` beta header, which the SDK sets automatically.
- Sessions are stateful and stored server-side until you delete them. The overview says Managed Agents is not eligible for zero data retention or HIPAA coverage.
- With `limited` networking, the environment's `allowed_hosts` list also applies to web search and web fetch. With no hosts listed they return nothing.
- Sending a message and streaming the reply takes SDK code. The quickstart gives no single curl command for that step.
- The quickstart also offers a Claude Code command, `/claude-api managed-agents-onboard`, that sets an agent up for you.
