---
id: web-search
title: Web search and web fetch
surface: apps
group: Find and reason
status: stable
level: starter
payoff: 2
effort: 1
jobs: [research, learning, debugging]
tags: [web, search, citations, fetch]
summary: Web search lets Claude look things up on the live web and answer with citations, and web fetch lets it read a specific URL you give it.
when: Use it for current facts that one or two lookups can settle, such as a release note, an error message or a changelog entry. Use Research when the question needs a full report.
replaces: Switching to a browser, searching, reading three pages and carrying the answer back into the chat.
example_kind: prompt
docs:
  - title: Enable and use web search
    url: https://support.claude.com/en/articles/10684626-enable-and-use-web-search
  - title: When should I use web search, extended thinking, and research?
    url: https://support.claude.com/en/articles/11095361-when-should-i-use-web-search-extended-thinking-and-research
verified: 2026-11-11
---
## Try it in a minute
1. Click the **+** button in the lower left corner of the chat window.
2. Click **Web search**. A checkmark appears next to it when it is on.
3. Ask something that needs current information, or include "Search the web" in your prompt to make sure Claude searches.
4. Paste a URL and ask about it. With web search on, Claude can retrieve that page directly (web fetch).
5. Check the citations and source links in the answer.

## Example
```text
Search the web. What changed in the latest stable Linux kernel release that affects NVMe over TCP?

Give me the three most relevant changes, each with a link to the primary source (kernel changelog or mailing list), and note anything that needs a configuration change on our side.
```

## At work
- **Debugging.** Paste an unfamiliar error and ask Claude to search for known issues, with links to the tracker entries it found.
- **Reading a long page for you.** Give Claude the URL of a release note or RFC and ask for the parts that affect your system.
- **Steering the search.** The docs suggest it when you want to tell Claude roughly what to look for and let it run the searches and analyze the results.

## Pitfalls
- If you have the new Claude experience there is no web search toggle. Claude searches when it helps.
- On Team and Enterprise plans an Owner or Primary Owner must first enable web search in **Organization settings > Capabilities**.
- Web search and web fetch count toward your usage limits. Fetching a long article pulls the whole thing into the context window.
- Website links occasionally do not work, and Claude may use your location, inferred from your IP address, for localized results.
- Cross-check cited sources and use authoritative ones for important decisions.
