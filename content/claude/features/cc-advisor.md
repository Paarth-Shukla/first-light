---
id: cc-advisor
title: Advisor tool
surface: code
group: Setup and cost
status: beta
level: power
payoff: 2
effort: 1
jobs: [coding, planning, debugging]
tags: [advisor, models, second-opinion, experimental]
summary: The advisor tool pairs your main model with a second, typically stronger model that Claude consults at key moments in a task, such as before committing to an approach.
when: Try it on long, multi-step tasks where most turns are routine but plan quality decides the outcome, instead of running the strongest model for every turn.
replaces: Switching the whole session to a bigger model for the sake of a few hard decisions.
example_kind: command
docs:
  - title: Escalate hard decisions with the advisor tool
    url: https://code.claude.com/docs/en/advisor
  - title: Commands
    url: https://code.claude.com/docs/en/commands
verified: 2026-11-11
---
## Try it in a minute
1. In a session, run `/advisor` to open a picker of available advisor models, or pass one directly as in the example.
2. Look for the confirmation that starts with `Advisor set to`. The choice is saved to `advisorModel` in your user settings.
3. Work as usual. When Claude consults the advisor, the transcript shows an `Advising` line with the advisor model's name.
4. Press `Ctrl+O` to read the guidance when the line says the advisor reviewed the conversation.
5. Run `/advisor off` to stop.

## Example
```text
/advisor opus
```

## At work
- **Large refactors.** A Sonnet main model handles routine work and escalates planning, ambiguous failures and completion checks to Opus.
- **A recurring error.** Claude tends to consult the advisor when an error keeps coming back, and you can ask for it with `consult the advisor before you continue`.
- **An independent check.** The docs describe an Opus main model with an Opus advisor for high-stakes tasks where a second review matters more than cost.

## Pitfalls
- The advisor tool is experimental. Behavior, pricing and availability may change.
- It needs the Anthropic API or Claude Platform on AWS. It is not available on Amazon Bedrock, Google Cloud's Agent Platform or Microsoft Foundry.
- The advisor must rank at or above your main model. A weaker advisor is not attached.
- Each call has the advisor read the full conversation, uncached, at the advisor model's rates. On subscription plans that counts toward your usage limits.
- Claude decides when to consult it. There is no setting to cap or force advisor calls.
- It adds less value on short tasks with little to plan.
- For a switch at the plan boundary instead, use the `opusplan` model alias.
