---
id: api-agent-skills
title: Agent Skills in the API
surface: platform
group: Agents
status: stable
level: intermediate
payoff: 3
effort: 2
jobs: [automation, writing, analysis]
tags: [skills, documents, pptx, xlsx, code-execution]
summary: Agent Skills are folders of instructions, scripts and resources that Claude loads on demand inside the code execution container, including pre-built skills that create PowerPoint, Excel, Word and PDF files.
when: Reach for a pre-built skill when a script should hand back a real .xlsx, .pptx, .docx or .pdf file. Reach for a custom skill when you keep repeating the same procedure or house rules in prompts.
replaces: Pasting the same how-we-do-it instructions into every prompt, and converting Claude's text output into office files by hand.
example_kind: command
docs:
  - title: Agent Skills
    url: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
  - title: Using Agent Skills with the API
    url: https://platform.claude.com/docs/en/build-with-claude/skills-guide
verified: 2026-11-11
---
## Try it in a minute
1. Add the code execution tool to `tools`. Skills run in its container.
2. List skills in the `container` parameter. A pre-built skill uses `"type": "anthropic"` and a `skill_id` of `pptx`, `xlsx`, `docx` or `pdf`.
3. Ask for the document you want.
4. Find the `file_id` of each created file in the code execution tool result blocks and download it with the Files API.
5. For your own skill, write a directory with a `SKILL.md` that has `name` and `description` frontmatter, and upload it to `/v1/skills`.

## Example
```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-10-21" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-opus-5-5",
    "max_tokens": 4096,
    "container": {
      "skills": [
        {
          "type": "anthropic",
          "skill_id": "xlsx",
          "version": "latest"
        }
      ]
    },
    "messages": [{
      "role": "user",
      "content": "Create a spreadsheet for a weekly on-call report with one sheet for incidents (date, severity, component, time to resolve) and one sheet that totals incidents by component with a chart."
    }],
    "tools": [{
      "type": "code_execution_20250825",
      "name": "code_execution"
    }]
  }'
```

## At work
- **Status reports as files**: a weekly job produces the spreadsheet or slide deck itself, not text you then format.
- **Team procedures**: package your incident write-up template or release checklist as a custom skill, and Claude uses it when a request matches the description.

## Pitfalls
- The `description` must say both what the skill does and when to use it. Claude matches requests against it.
- Skills in the API have no network access and cannot install packages at runtime.
- A request can include up to 20 skills, and a skill upload is limited to 30 MB.
- Custom skills are shared with the whole workspace. Any API key with access to the workspace can read, use and delete them.
- Custom skills do not sync between claude.ai, Claude Code and the API. Upload separately for each.
- Use skills only from trusted sources, and audit every bundled file. A malicious skill can misuse tools or leak data.
- Agent Skills are not covered by zero data retention arrangements.
