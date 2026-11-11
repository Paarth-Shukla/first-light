---
id: api-web-search-tool
title: Web search tool
surface: platform
group: Tools
status: stable
level: starter
payoff: 3
effort: 1
jobs: [research, automation]
tags: [web-search, citations, server-tools]
summary: The web search tool is a server tool that lets Claude search the web during a request and answer with cited sources, with no search code on your side.
when: Reach for it when a script needs information that is current, changing or past the model's knowledge cutoff, such as release notes, advisories or prices. If you already have the URL, use web fetch instead.
replaces: Running searches yourself, pasting snippets into the prompt and tracking which claim came from which page.
example_kind: command
docs:
  - title: Web search tool
    url: https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
verified: 2026-11-11
---
## Try it in a minute
1. Add `{"type": "web_search_20250305", "name": "web_search"}` to `tools` in a Messages request.
2. Cap the number of searches in a turn with `max_uses`, and restrict sources with `allowed_domains` or `blocked_domains`.
3. Ask a question that depends on current information. Claude decides when to search and may search several times.
4. Read the `text` blocks. Each cited claim carries `citations` with `url`, `title` and `cited_text`.
5. For search-heavy work, switch to `web_search_20260318`, where Claude filters results in code before they reach the context window (dynamic filtering).

## Example
```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-10-21" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-opus-5-5",
    "max_tokens": 4096,
    "messages": [
      {
        "role": "user",
        "content": "What changed in the latest stable Linux kernel release that affects NVMe drivers? Cite the sources."
      }
    ],
    "tools": [{
      "type": "web_search_20250305",
      "name": "web_search",
      "max_uses": 5,
      "allowed_domains": ["kernel.org", "lwn.net"]
    }]
  }'
```

## At work
- **Dependency and advisory checks**: a weekly script asks what changed upstream and gets an answer with links you can paste into a ticket.
- **Vendor and standards research for a design doc**: limiting `allowed_domains` to primary sources keeps citations trustworthy.

## Pitfalls
- At the time of writing the page lists web search at $10 per 1,000 searches, plus token costs for the results Claude reads.
- Use `allowed_domains` or `blocked_domains`, not both. Sending both returns a 400 error.
- Tool errors arrive inside a 200 response as a `web_search_tool_result_error` (for example `max_uses_exceeded`), so check the body.
- In multi-turn conversations, send the assistant blocks back exactly as received, including `encrypted_content`. Missing or modified content fails with a 400 error.
- A long turn can stop with `stop_reason: "pause_turn"`. Send the paused assistant message back unchanged to continue.
- An administrator can disable web search for the organization in the Claude Console; requests then fail with a 400 `invalid_request_error`.
- If you show API output directly to end users, citations to the original source must be included.
