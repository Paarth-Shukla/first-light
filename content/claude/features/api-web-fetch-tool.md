---
id: api-web-fetch-tool
title: Web fetch tool
surface: platform
group: Tools
status: stable
level: starter
payoff: 2
effort: 1
jobs: [research, automation, learning]
tags: [web-fetch, urls, pdf, server-tools]
summary: The web fetch tool is a server tool that retrieves the full content of a specific web page or PDF during a request so Claude can read it.
when: Reach for it when you already know the URL, such as a changelog, a README or an RFC, and want Claude to read the page itself. Use web search when Claude first has to find the page.
replaces: Downloading a page, stripping the HTML and pasting the text into a prompt.
example_kind: command
docs:
  - title: Web fetch tool
    url: https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool
verified: 2026-11-11
---
## Try it in a minute
1. Add `{"type": "web_fetch_20250910", "name": "web_fetch"}` to `tools` in a Messages request.
2. Put the URL in the user message. Claude can only fetch URLs that already appeared in the conversation.
3. Set `max_uses` to cap fetches and `max_content_tokens` to cap how much of a large page enters the context.
4. Set `"citations": {"enabled": true}` if you want cited passages. Citations are off by default for web fetch.

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
        "content": "Read https://example.com/docs/upgrade-guide and list every breaking change that affects a client still on the v1 API."
      }
    ],
    "tools": [{
      "type": "web_fetch_20250910",
      "name": "web_fetch",
      "max_uses": 5,
      "max_content_tokens": 100000,
      "citations": {"enabled": true}
    }]
  }'
```

## At work
- **Upgrade planning**: point Claude at a vendor upgrade guide or changelog and get the breaking changes that apply to you, with cited passages.
- **Reading specs and papers**: fetched PDFs are processed like an attached PDF document, so a script can summarise an RFC from its URL.
- **Token control**: with `web_fetch_20260209` or later, Claude can filter fetched content in code before it reaches the context window.

## Pitfalls
- Claude cannot fetch a URL that appears only in its own output or only in the system prompt. Put the URL in a user message.
- Pages rendered dynamically with JavaScript are not supported.
- The docs warn of data exfiltration risk when Claude handles untrusted input alongside sensitive data. Limit `max_uses`, set `allowed_domains`, or leave the tool off.
- Only text, HTML and PDF content is supported, and a URL longer than 250 characters is rejected.
- Errors arrive inside a 200 response as a `web_fetch_tool_result_error`, for example `url_not_accessible`.
- There is no extra charge beyond tokens, but a large page is many tokens. The page gives about 25,000 tokens for a 100 kB documentation page.
