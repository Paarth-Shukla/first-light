---
id: research-a-technical-decision
title: Research a technical decision and write a recommendation memo
job: research
level: intermediate
minutes_saved: 90
features: [research, web-search, claude-docs]
prerequisites: [A paid plan for research, Web search turned on, Connectors for your internal design docs if you want them searched]
fields:
  - name: decision
    label: The decision
    placeholder: which embedded key-value store to use for the new metadata service
  - name: options
    label: Options
    placeholder: bbolt, Pebble, or extending our existing segment format
  - name: constraints
    label: Hard constraints
    placeholder: Go only, crash-consistent on power loss, Apache 2.0 compatible licence, p99 write under 2 ms on NVMe
  - name: criteria
    label: How to weigh the rest
    placeholder: correctness under crashes first, operational maturity second, write throughput third
  - name: reader
    label: Who decides
    placeholder: the architecture review on 20 November
docs:
  - title: Use research on Claude
    url: https://support.claude.com/en/articles/11088861-use-research-on-claude
  - title: Enable and use web search
    url: https://support.claude.com/en/articles/10684626-enable-and-use-web-search
  - title: When should I use web search, extended thinking, and research?
    url: https://support.claude.com/en/articles/11095361-when-should-i-use-web-search-extended-thinking-and-research
  - title: Get started with Claude Docs
    url: https://support.claude.com/en/articles/16923645-get-started-with-claude-docs
  - title: Prompting best practices
    url: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
verified: 2026-11-11
---
## Steps
1. Research needs web search: click **+** in the lower left of the chat box and check **Web search** is on, then select **Research**. A blue indicator appears.
2. Turn on only the connectors Claude should read, such as Google Drive. During research Claude uses connector tools without asking each time. Use the web or Claude Desktop: research started in Claude Mobile skips connectors without warning.
3. Send the prompt below. Its opening words steer Claude to the research tool.
4. Open the citation behind every claim the recommendation depends on.
5. Ask Claude to turn the memo into a doc and share it with the reviewers.

## Prompt
```text
Please use the research tool to help me decide {{decision}}.

Options: {{options}}
Hard constraints: {{constraints}}
How to weigh the rest: {{criteria}}

The result becomes a recommendation memo for {{reader}}, where every claim will be challenged, so the evidence matters more than the prose.

A good answer:
- checks each option against each hard constraint, drops any option that fails one, and names the source that showed it
- prefers primary sources (official documentation, source code, issue trackers, release notes, benchmarks with published method) and checks important claims against a second source
- treats each option as a competing hypothesis and notes where the evidence changed your view
- pulls in relevant context from our internal design docs
- says plainly where evidence is missing or sources disagree

End with a one-page memo: the recommendation, the two strongest reasons, the main risk and how we would spot it early, what would change the recommendation, and a table of sources with one line on what each supports.
```

## Why it works
The help center recommends research when gathering needs five or more tool calls across the web and your tools, as a comparison like this does. The prompting guide's research advice is to define success criteria, ask for verification across sources and work with competing hypotheses, and the "A good answer" list does all three. Research uses your limits faster than a normal chat, so a precise brief avoids a second run.
