---
id: custom-skills
title: Create a custom skill
surface: apps
group: Extend
status: stable
level: intermediate
payoff: 3
effort: 2
jobs: [automation, writing, review, planning]
tags: [skills, skill-md, templates, team]
summary: A custom skill is a folder with a SKILL.md file of instructions, and optionally scripts and reference files, that you write once and upload so Claude follows your process.
when: Write one when you find yourself correcting Claude with the same instructions, such as a report format, a review checklist or a multi-step procedure. For a one-off task, just describe it in the conversation.
replaces: Keeping a personal prompt file and pasting from it whenever the task comes up.
example_kind: config
docs:
  - title: Create custom skills
    url: https://claude.com/docs/skills/how-to
  - title: How to create custom skills
    url: https://support.claude.com/en/articles/12512198-how-to-create-custom-skills
  - title: Use skills in Claude
    url: https://support.claude.com/en/articles/12512180-use-skills-in-claude
verified: 2026-11-11
---
## Try it in a minute
1. Create a folder named after the skill, for example `incident-writeup`, containing a `SKILL.md` that starts with `name` and `description` frontmatter.
2. From the parent folder run `zip -r incident-writeup.zip incident-writeup/` so the folder is the top level of the archive.
3. Go to [Customize > Skills](https://claude.ai/customize/skills), click the **+** button, then **+ Create skill**, select **Upload a skill** and upload the ZIP.
4. Turn the skill on and send a prompt that should trigger it.
5. If Claude does not load it when expected, revise the description.

## Example
```markdown
---
name: incident-writeup
description: Write a post-incident review in our team format. Use when asked for an incident write-up, postmortem or PIR.
---

# Incident write-up

1. Build a timeline in UTC from the material provided. Mark gaps instead of guessing.
2. Write these sections in order: Summary, Customer impact, Timeline, Root cause, Action items.
3. Keep the Summary under 100 words and refer to roles, not names.
4. Give every action item an owner role and a due date.
```

## At work
- **Teaching tool conventions.** A skill can tell Claude which project new issues go in and which labels and template to use in your issue tracker.
- **Sharing.** On Team and Enterprise plans you can share a skill with colleagues or use **Publish to org**, if an owner has enabled it.

## Pitfalls
- The directory name must match the `name` field, which allows lowercase letters, numbers and hyphens only. A `SKILL.md` at the root of the ZIP is not recognized.
- Keep `SKILL.md` under 500 lines and move reference material to separate files.
- Do not put API keys or passwords anywhere in a skill. Everyone you share it with receives its files.
- A skill cannot reach an outside service itself. Live data needs a connector.
