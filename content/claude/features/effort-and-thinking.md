---
id: effort-and-thinking
title: Model, effort and thinking settings
surface: apps
group: Find and reason
status: stable
level: starter
payoff: 2
effort: 1
jobs: [debugging, analysis, planning, coding]
tags: [thinking, effort, models, reasoning]
summary: The model menu next to the send button sets which Claude model you chat with, how much effort it puts into each response, and whether it shows its thinking.
when: Raise effort or turn on thinking for multi-step technical problems, detailed document analysis and project planning. Leave the defaults, or go lower, for everyday questions.
replaces: Re-asking the same hard question several times hoping for a more careful answer.
example_kind: prompt
docs:
  - title: Change the model, effort, and thinking settings
    url: https://support.claude.com/en/articles/8664678-change-the-model-effort-and-thinking-settings
  - title: When should I use web search, extended thinking, and research?
    url: https://support.claude.com/en/articles/11095361-when-should-i-use-web-search-extended-thinking-and-research
verified: 2026-11-11
---
## Try it in a minute
1. Click the model name next to the send button.
2. Click **Effort** and choose a level. The recommended level for each model is marked **Default**.
3. On models that offer it, mouse over **Effort** and switch the **Thinking** (or **Extended**) toggle on or off.
4. Send a hard problem, then click the expandable **Thinking** section above the reply to see how Claude approached it.

## Example
```text
Here is our lease-based leader election code and the failure report from last night.

Work through every interleaving in which two nodes could both believe they hold the lease, given clock drift of up to 500 ms and a network partition during renewal. For each one, say whether the code allows it and which line is responsible. Then propose the smallest fix.
```

## At work
- **Hard technical problems.** Higher effort means more thorough responses, which the docs recommend for multi-step technical problems and detailed document analysis.
- **Stretching your usage.** The docs say Low and Medium work well for routine tasks and stretch your usage further.
- **Checking the reasoning.** Reading the thinking summary helps you verify how Claude reached its conclusion before you rely on it.

## Pitfalls
- Higher effort takes longer and uses more tokens, so you reach usage limits faster.
- Effort and thinking are separate settings. Effort controls how thorough every response is. The toggle controls whether Claude works through its reasoning in an expandable section first.
- On some models thinking is always on and the toggle does not appear. To make Claude think less on these, choose a lower effort level.
- The effort selector is only available on some models, and on Enterprise plans an administrator may have turned off a model or effort level for your role.
- Changes apply from Claude's next response, not retroactively.
