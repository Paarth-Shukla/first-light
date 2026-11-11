---
id: skills-in-claude
title: Skills in Claude
surface: apps
group: Extend
status: stable
level: starter
payoff: 3
effort: 1
jobs: [writing, analysis, automation, planning]
tags: [skills, workflows, customize, consistency]
summary: Skills are folders of instructions, scripts and resources that Claude loads only when a task calls for them, so it does that task the same way every time.
when: Turn on a skill when you want Claude to follow a specific procedure for a recurring task. Use a project for background knowledge that should always be loaded in its chats.
replaces: Pasting the same checklist or template into a chat every time you ask for that kind of output.
example_kind: prompt
docs:
  - title: What are skills?
    url: https://support.claude.com/en/articles/12512176-what-are-skills
  - title: Use skills in Claude
    url: https://support.claude.com/en/articles/12512180-use-skills-in-claude
  - title: Skills overview
    url: https://claude.com/docs/skills/overview
verified: 2026-11-11
---
## Try it in a minute
1. Make sure **Code execution and file creation** is on under **Settings > Capabilities**. Skills run in Claude's code sandbox.
2. Open [Customize > Skills](https://claude.ai/customize/skills). **Your skills** lists what you have and **Discover** lists skills you can add.
3. Select **Turn on** on a skill's row, or open the skill and use the switch at the top of its page.
4. In a chat, describe your task. Claude loads a turned-on skill when the task matches its description.
5. To pick one yourself, type `/` in the message box and select the skill.

## Example
```text
Create a PowerPoint presentation for Thursday's architecture review of the tiering service.

Six slides: problem, current design, proposed design, migration plan, risks, decisions needed. Use the attached design doc as the only source. Put the detail in speaker notes and keep each slide to four bullets or fewer.
```

## At work
- **Documents that come out right.** The Anthropic skills for Excel, Word, PowerPoint and PDF are available to all users and are invoked automatically.
- **Team conventions.** Custom skills can create tasks in tools such as JIRA following team conventions, or structure meeting notes in a company format.
- **Everywhere you work.** Enabled skills are also available in the Claude add-ins for Excel, PowerPoint, Word and Outlook, and sync to Claude Code.

## Pitfalls
- A skill's description is the only part Claude sees before deciding to use it. If Claude is not using a skill, check that it is toggled on and be explicit, for example "Use my brand guidelines skill to...".
- Skills that someone shares with you or that you upload are not reviewed by Anthropic. Read the `SKILL.md` and bundled files before turning one on.
- If skills are greyed out, code execution may be disabled for you or your organization.
