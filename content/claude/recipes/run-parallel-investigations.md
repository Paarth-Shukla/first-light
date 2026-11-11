---
id: run-parallel-investigations
title: Run parallel investigations with subagents or a workflow
job: debugging
level: power
minutes_saved: 60
features: [cc-subagents, cc-workflows]
prerequisites: [Claude Code in the repository, A paid plan for dynamic workflows]
fields:
  - name: evidence
    label: What you have so far
    placeholder: Paste the latency numbers, the release diff summary and any relevant logs
  - name: problem
    label: The problem
    placeholder: p99 write latency on the ingest path rose from 4 ms to 11 ms between release 7.2 and 7.3
  - name: hypotheses
    label: Hypotheses, one per line
    placeholder: a lock added in the compaction scheduler; the new checksum library; changed fsync batching; GC pressure from the larger write buffer
  - name: repro
    label: How to measure it
    placeholder: make bench-ingest, which compares the two releases on one node
docs:
  - title: Create custom subagents
    url: https://code.claude.com/docs/en/sub-agents
  - title: Orchestrate subagents at scale with dynamic workflows
    url: https://code.claude.com/docs/en/workflows
  - title: Run agents in parallel
    url: https://code.claude.com/docs/en/agents
  - title: Prompting best practices
    url: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
verified: 2026-11-11
---
## Steps
1. Write down three to five hypotheses that do not depend on each other.
2. Send the prompt below. Each subagent works in its own context and returns a summary. `/tasks` lists background work in the session.
3. If the job is wide rather than deep, such as one check across dozens of services, say `use a workflow` instead, check the planned phases, select **Yes, run it** and watch with `/workflows`. On Pro, turn workflows on in `/config` first.
4. Try a workflow on a small slice first. A run can use meaningfully more tokens than the same task in conversation.
5. Reproduce the leading hypothesis before anyone writes a fix.

## Prompt
```text
<evidence>
{{evidence}}
</evidence>

Problem: {{problem}}

Investigate these hypotheses in parallel, one subagent per hypothesis, because each can be checked on its own:
{{hypotheses}}

Each subagent reads code, git history and logs and does not edit files. Leave running {{repro}} to the main session, so parallel runs do not disturb each other's measurements.

Each subagent reports in under 200 words: evidence for and against, with file paths, commits or log lines; the commands it ran and what they showed; a confidence level; and the measurement that would confirm or rule it out. Ruling a hypothesis out is a useful result, so say so plainly.

When all have reported, compare the findings, point out any that contradict each other, and propose the one experiment that best separates the hypotheses still standing. Hold off on fixes until I have seen that comparison.
```

## Why it works
The subagents guide shows this pattern for independent investigations, and warns that many detailed results can fill your context, hence the word limit. The prompting guide recommends competing hypotheses and tracked confidence for complex research. When a job outgrows a few subagents, a workflow holds the plan in a script and can have agents verify each other's findings.
