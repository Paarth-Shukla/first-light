---
id: find-the-root-cause-of-a-failure
title: Find the root cause of a failing test or production bug
job: debugging
level: intermediate
minutes_saved: 30
features: [cc-common-workflows, cc-best-practices, cc-subagents, cc-checkpointing-and-rewind]
prerequisites: [Claude Code running in the repository, A command that reproduces the failure or the logs from when it happened]
fields:
  - name: symptom
    label: What is going wrong
    placeholder: test_backoff_resets fails on CI but passes on my laptop
  - name: repro_command
    label: Command that reproduces it
    placeholder: pytest tests/replication/test_scheduler.py -k backoff -x
  - name: frequency
    label: Consistent or intermittent
    placeholder: about one run in five
  - name: stack_trace
    label: Stack trace or log excerpt
    placeholder: Paste the trace and the 50 log lines before it
  - name: check_command
    label: Command that must pass when fixed
    placeholder: pytest tests/replication -q
docs:
  - title: Common workflows
    url: https://code.claude.com/docs/en/common-workflows
  - title: Best practices for Claude Code
    url: https://code.claude.com/docs/en/best-practices
  - title: Create custom subagents
    url: https://code.claude.com/docs/en/sub-agents
  - title: Checkpointing
    url: https://code.claude.com/docs/en/checkpointing
verified: 2026-11-11
---
## Steps
1. Start `claude` in the repository. Hand over evidence instead of describing it. Type `@` and a path to include a log file, or paste a screenshot of the error.
2. Send the prompt below with the reproduce command and whether the failure is intermittent or consistent.
3. Read the diagnosis and the failing test before you let Claude apply a fix.
4. If the session goes down a wrong path, run `/rewind`, pick the prompt to return to and choose **Restore code and conversation**.

## Prompt
```text
{{symptom}}

Reproduce it with: {{repro_command}}
It fails {{frequency}}.

<stack_trace>
{{stack_trace}}
</stack_trace>

Find the root cause before changing anything. Read the code on the failing path and check recent commits that touched it. List the two or three most likely causes with the evidence for and against each, then confirm one by writing a failing test that isolates it. If the logs are long, use a subagent to read them and report only the lines that matter.

Then make the smallest fix for the underlying cause, not the symptom, and run {{check_command}} until it passes. Show me the commands you ran and their output. If the test itself is wrong, or you cannot reproduce the failure, stop and tell me instead of working around it.
```

## Why it works
The docs' bug-fixing tips are to give Claude the reproduce command and say whether the error is intermittent. The best practices guide adds a failing test and a pass or fail check, so Claude can close the loop itself, and asks for the command and its output as evidence.
