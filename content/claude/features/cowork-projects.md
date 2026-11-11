---
id: cowork-projects
title: Projects in Cowork
surface: cowork
group: Delegate
status: stable
level: intermediate
payoff: 2
effort: 2
jobs: [planning, automation, writing]
tags: [cowork, projects, memory, instructions, folders]
summary: Projects in Cowork group related tasks into a workspace with its own files, context, instructions, scheduled tasks and memory.
when: Create one when you run several Cowork tasks against the same folder or body of work, so each new task starts with the same rules and remembers earlier ones.
replaces: Re-attaching the same folder and restating the same instructions at the start of every task.
example_kind: prompt
docs:
  - title: Organize your tasks with projects in Claude Cowork
    url: https://support.claude.com/en/articles/14116274-organize-your-tasks-with-projects-in-claude-cowork
  - title: Get started with Claude Cowork
    url: https://support.claude.com/en/articles/13345190-get-started-with-claude-cowork
verified: 2026-11-11
---
## Try it in a minute
1. Update Claude Desktop to the latest version.
2. Find **Projects** in the left navigation panel and click the **+** button.
3. Choose **Start from scratch**, **Import from project** to bring over the files and instructions of an existing Claude project, or **Use an existing folder**.
4. Name the project, add instructions, attach any additional files and click **Create**.
5. Start a task inside the project. Add a scheduled task there if the work recurs.

## Example
```text
This project prepares the monthly storage platform release notes.

Source material is in the connected folder: merged-changes.csv, the previous notes in /published, and style-guide.md.
Always follow style-guide.md. Group changes under Features, Fixes and Known issues. Never invent a ticket number. If a change has no customer-facing description, list it under "Needs wording" instead of guessing.
Save drafts to /drafts as Markdown and never edit anything in /published.
```

## At work
- **Recurring deliverables.** Release notes, monthly reports or audit evidence keep their rules, source folder and schedule in one place.
- **Continuity.** Claude remembers context from tasks you have run in the project and applies it to future tasks in the same project.
- **Reusing a chat project.** Import an existing Claude project instead of rebuilding its knowledge and instructions.

## Pitfalls
- What Claude learns in one project does not carry over to other projects. A project does share memory with your chats outside projects unless you turn off **Use account memory** on the project's page.
- Importing from a Claude project is one project at a time.
- Archiving removes the project from the interface but does not affect files or folders on your computer.
- On Team and Enterprise plans without **Chat and Cowork unified**, projects created from a local folder stay on that computer.
- Project sharing is for Team and Enterprise plans.
