---
id: confluence-docs-from-code
title: Draft and maintain Confluence documentation from code
job: writing
level: intermediate
minutes_saved: 40
features: [cc-mcp, cc-common-workflows, cc-routines]
prerequisites: [Claude Code signed in with your claude.ai account, A connector for your wiki added at claude.ai/customize/connectors]
fields:
  - name: component
    label: Component to document
    placeholder: the snapshot scheduler
  - name: readers
    label: Who reads the page
    placeholder: on-call engineers from other teams
  - name: reader_goal
    label: What they need to do
    placeholder: diagnose a stuck schedule
  - name: code_paths
    label: Where the code lives
    placeholder: pkg/scheduler and cmd/snapshotd
  - name: page_reference
    label: Existing page
    placeholder: the page titled Snapshot scheduler in the STOR space or none
docs:
  - title: Connect Claude Code to tools via MCP
    url: https://code.claude.com/docs/en/mcp
  - title: Common workflows
    url: https://code.claude.com/docs/en/common-workflows
  - title: Automate work with scheduled tasks
    url: https://code.claude.com/docs/en/routines
  - title: Prompting best practices
    url: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
verified: 2026-11-11
---
## Steps
1. Add your wiki's connector at [claude.ai/customize/connectors](https://claude.ai/customize/connectors). In Claude Code, run `/mcp`. Servers from claude.ai appear in the list.
2. In the repository, send the prompt below.
3. Review the draft in the session and correct it.
4. Tell Claude to create or update the page.
5. To keep it current, describe a weekly check to `/schedule`. The docs' "docs drift" example scans merged pull requests and flags documentation that references changed APIs.

## Prompt
```text
Write the wiki page for {{component}} from the code in this repository. Readers are {{readers}}, who need to {{reader_goal}} without reading the source.

Read the code under {{code_paths}} first and base every statement on it. Do not describe behavior in a file you have not opened. Existing page: {{page_reference}}. Fetch it through the wiki connector and keep its structure where it still fits. If the code and the page disagree, the code wins, and I want a list of the differences.

Sections: what the component does, how a request flows through it, configuration options with defaults and where each is read, how to run and test it locally, failure modes and what the logs show, owners and links. Add a line at the top with the commit the page was generated from.

Show me the draft as markdown in this session first. Do not create or update any wiki page until I say so, because other teams read that space.
```

## Why it works
Connectors added in claude.ai are available in Claude Code when you log in with that account, so one session can read the code and the page. The prompting guide's advice to investigate before answering keeps the page tied to files Claude opened.
