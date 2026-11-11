---
id: cc-best-practices
title: Best practices that still matter
surface: code
group: Workflows
status: stable
level: starter
payoff: 3
effort: 1
jobs: [coding, planning, review]
tags: [best-practices, prompting, verification, steering]
summary: The best practices guide boils down to three habits, which are telling Claude what it cannot see, giving it a check to run, and enforcing the rules that cannot have exceptions.
when: Read it when sessions build the wrong thing, claim to be done too early or take more corrections than the task deserves.
replaces: Longer and louder prompts, and being the test suite yourself.
example_kind: prompt
docs:
  - title: Best practices for Claude Code
    url: https://code.claude.com/docs/en/best-practices
verified: 2026-11-11
---
## Try it in a minute
1. Write a specific prompt. Name the file, describe the symptom and say what fixed looks like.
2. Give Claude a pass or fail check, for example `run the auth tests after, and keep going until they pass`.
3. Ask for evidence, meaning the command it ran and its output.
4. Watch the first minute. Press `Esc` the moment Claude drifts.
5. After two failed corrections, run `/clear` and write one better prompt instead of a third correction.

## Example
```text
users report login fails after the session times out. look at token refresh in src/auth/, write a failing test that reproduces it, then fix it. run the auth tests after and keep going until they pass. show me the command you ran and its output.
```

## At work
- **Unclear requirements.** Ask Claude to interview you until it could write the spec, then have it write `SPEC.md` and build from that in a fresh session.
- **Review against the spec.** Have a subagent review the diff against `SPEC.md` for gaps that affect correctness, and tell it to skip style. The guide notes that a reviewer asked to find problems will always find something.
- **Unattended runs.** First make sure the task knows what done looks like, can check its own work, can only touch what it should, and has a cap on turns or spend.

## Pitfalls
- The guide retires some old advice, such as ALL CAPS emphasis and describing your file layout in `CLAUDE.md`.
- "think hard" and "be thorough" are ordinary prompt text. Effort level is the control, and `ultrathink` works for a single turn.
- A rule that must hold every time belongs in a hook, a deny rule or a managed setting, not `CLAUDE.md`.
