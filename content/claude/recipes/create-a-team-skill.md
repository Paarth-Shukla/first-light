---
id: create-a-team-skill
title: Turn a repeated team procedure into a skill
job: automation
level: intermediate
minutes_saved: 20
features: [cc-skills, cc-best-practices]
prerequisites: [Claude Code in the team repository, The procedure written down once even roughly]
fields:
  - name: skill_name
    label: Skill name (lowercase and hyphens)
    placeholder: oncall-handoff
  - name: procedure
    label: The procedure
    placeholder: Paste the runbook, checklist or the steps you followed last time
  - name: triggers
    label: When people will want it
    placeholder: when someone asks for an on-call handoff, a shift summary or what happened on call this week
  - name: side_effects
    label: What it changes outside the repo
    placeholder: nothing, it only reads logs and tickets and drafts a summary
docs:
  - title: Extend Claude with skills
    url: https://code.claude.com/docs/en/skills
  - title: Best practices for Claude Code
    url: https://code.claude.com/docs/en/best-practices
verified: 2026-11-11
---
## Steps
1. Do the procedure once with Claude, so the steps and your corrections are fresh.
2. Send the prompt below. Claude writes `.claude/skills/<name>/SKILL.md`.
3. In a fresh session, ask `What skills are available?`, then try a matching request and the direct command `/<name>`.
4. Commit `.claude/skills/` so everyone in the repository gets the skill.
5. To measure it, run `/plugin install skill-creator@claude-plugins-official` and ask Claude to evaluate the skill against runs without it.

## Prompt
```text
Write a project skill named {{skill_name}} at .claude/skills/{{skill_name}}/SKILL.md from the procedure below. The whole team will use it, including people who have never done this procedure, so it has to work without me in the room.

<procedure>
{{procedure}}
</procedure>

Description: say what the skill does and when to use it, key use case first, in words people actually type. People will want it {{triggers}}.

Body: numbered steps, with the most important instructions at the top. Where a step needs live data such as a diff or a log, use dynamic context injection so the command output is in the skill before Claude reads it. Word each rule so it applies to the whole task ("run the tests after every edit", not "run the tests"). Leave out anything Claude can find by reading the code.

Side effects: {{side_effects}}. If the procedure posts, deploys or sends anything, add disable-model-invocation: true so only a person can start it.

Keep SKILL.md under 500 lines and move long reference material into separate files that it links to. Afterwards, tell me which parts of my procedure you left out and why.
```

## Why it works
The best practices guide puts team procedures in skills, because Claude sees only the name and description until a task needs the rest. The skills guide explains the prompt's rules: the description decides when the skill loads and is cut at 1,536 characters with `when_to_use`, Claude Code does not re-read the file on later turns and may keep only its start after compaction, and `disable-model-invocation: true` keeps side effects under your control.
