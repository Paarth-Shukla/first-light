---
id: api-choosing-a-model
title: Choosing a model
surface: platform
group: Models and reasoning
status: stable
level: starter
payoff: 3
effort: 1
jobs: [automation, planning]
tags: [models, cost, latency, api]
summary: The current lineup (Fable 5.2, Opus 5.5, Sonnet 5.5, Haiku 5.5) trades capability against speed and price, and the docs name a starting model for each kind of work.
when: Reach for this before you write the first line of a script, and again when a job turns out too slow, too costly or not good enough. Try tuning effort before you switch models.
replaces: Typing a model id from memory, or defaulting to the largest model for every job.
example_kind: command
docs:
  - title: Models overview
    url: https://platform.claude.com/docs/en/models/overview
  - title: Choosing the right model
    url: https://platform.claude.com/docs/en/about-claude/models/choosing-a-model
  - title: Get started with Claude
    url: https://platform.claude.com/docs/en/get-started
verified: 2026-11-11
---
## Try it in a minute
1. Open the Models overview and copy the Claude API ID you need. At the time of writing the current ids are `claude-fable-5-2`, `claude-opus-5-5`, `claude-sonnet-5-5` and `claude-haiku-5-5`.
2. If you are unsure, start with Claude Opus 5.5, which the docs recommend for most workloads.
3. For high-volume, latency-sensitive work (classification, extraction, routing), start with Claude Haiku 5.5 and upgrade only if testing shows a capability gap.
4. Run your real prompts and data through two candidates and compare accuracy, quality and edge cases before you settle.

## Example
```bash
curl https://api.anthropic.com/v1/messages \
  -H "content-type: application/json" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-10-21" \
  -d '{
    "model": "claude-haiku-5-5",
    "max_tokens": 1000,
    "messages": [
      {
        "role": "user",
        "content": "Classify this ticket as bug, feature or question. Answer with one word. Ticket: Snapshot replication stalls at 80 percent after the upgrade."
      }
    ]
  }'
```

## At work
- **Ticket triage and log labelling**: Haiku 5.5 is listed as the fastest model and is aimed at classification, extraction and routing, so a nightly pass over a backlog stays quick.
- **Design reviews and large refactors**: Opus 5.5 is the documented starting point for complex agentic coding and enterprise work.
- **Hours-long agent runs and multistep research**: move to Fable 5.2 only when your evals on Opus 5.5 at higher effort still fall short.

## Pitfalls
- Every model id is a pinned snapshot, so moving to a new model means changing the string and re-testing.
- The docs call effort tuning "often a better lever than switching models". Try a different effort level first.
- If your integration forces tool use, turns thinking off or edits earlier messages in a conversation, read the breaking changes page for Opus 5.5 or Fable 5.2 before you switch.
- Take context window, max output and price from the comparison table, not from memory. You can also read limits programmatically from the Models API.
