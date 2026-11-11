---
id: review-a-pull-request
title: Review a pull request before a human does
job: review
level: intermediate
minutes_saved: 20
features: [cc-code-review, cc-subagents, cc-best-practices]
prerequisites: [Claude Code running in the repository, A branch or pull request with changes to review]
fields:
  - name: target
    label: What to review
    placeholder: the changes on this branch compared with main
  - name: intent
    label: What the change is supposed to do
    placeholder: Paste the ticket text or the pull request description
  - name: risk_areas
    label: Where a mistake would hurt most
    placeholder: retry and timeout handling in pkg/replication and the on-disk format
docs:
  - title: Review locally with /code-review
    url: https://code.claude.com/docs/en/code-review-local
  - title: Best practices for Claude Code
    url: https://code.claude.com/docs/en/best-practices
  - title: Create custom subagents
    url: https://code.claude.com/docs/en/sub-agents
verified: 2026-11-11
---
## Steps
1. In a Claude Code session, run `/code-review high 1234` for a pull request, or `/code-review main...my-feature` for a branch. In a terminal session the review runs as a background subagent and reports when it completes.
2. While it runs, send the prompt below. It adds a second pass against the intent of the change, which the bundled review cannot know.
3. Compare the two sets of findings and ask Claude to fix the ones you agree with.
4. To hand findings to the author, run `/code-review --comment 1234`. It posts them on the GitHub pull request as inline comments.

## Prompt
```text
Use a subagent to review {{target}} against what the change is supposed to do. The subagent has not seen how the code was written, which is the point.

<intent>
{{intent}}
</intent>

Check that every requirement in the intent is implemented and that the edge cases it implies have tests. Then look for anything that would break existing callers, especially in {{risk_areas}}.

Report only gaps that affect correctness and skip style. A person reviews this next and I want their attention on design. For each finding give the file and line, the failure scenario in one sentence, and how confident you are. Open the surrounding code before reporting a finding, and say so if you could not verify one. Do not edit any files.
```

## Why it works
The best practices guide notes that a fresh subagent is not swayed by the reasoning that produced the code, and that a reviewer asked to find problems will always find something, which is why the prompt keeps "skip style". Pasting the intent gives Claude the one thing it cannot read from the diff.
