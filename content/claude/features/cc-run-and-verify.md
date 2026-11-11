---
id: cc-run-and-verify
title: Run and verify your app
surface: code
group: Workflows
status: stable
level: intermediate
payoff: 3
effort: 2
jobs: [coding, debugging, review]
tags: [verify, run, testing, skills, definition-of-done]
summary: The bundled /run and /verify skills launch your app and confirm a change against the running app, and /run-skill-generator records how to build and launch your project.
when: Use them after Claude says a change is done, to catch the kind of problem that tests and type checks miss, especially for user-facing behavior.
replaces: Building and clicking through the app yourself to see whether the change really works.
example_kind: command
docs:
  - title: Extend Claude with skills
    url: https://code.claude.com/docs/en/skills
  - title: Commands
    url: https://code.claude.com/docs/en/commands
  - title: Best practices for Claude Code
    url: https://code.claude.com/docs/en/best-practices
verified: 2026-11-11
---
## Try it in a minute
1. In your project, run `/run-skill-generator` once. It gets the app running from a clean environment and records the recipe as a skill at `.claude/skills/run-<name>/`.
2. Make a change with Claude as usual.
3. Run `/verify`. Claude builds and runs the app and observes the result, rather than relying on tests or type checks.
4. Run `/run` when you just want the app launched and driven so you can see the change working.

## Example
```text
/run-skill-generator
/verify
```

## At work
- **A real definition of done.** The best practices guide suggests running `/verify` once Claude says it is done, because it catches problems that tests and typechecks miss.
- **Shared launch knowledge.** After the generator runs, `/run`, `/verify` and any other agent in the repo follow the recorded recipe instead of rediscovering how to start the app.
- **A check before each commit.** When a session starts with a project or personal skill named `verify` in place, Claude Code's commit instructions tell Claude to run it before each commit, except for changes to docs or tests.

## Pitfalls
- `/run` and `/verify` work without setup by inferring the launch from your project type and files such as the README, `package.json` or `Makefile`. That inference is unreliable for projects that need a database, an env file, a graphical session or a multi-step build.
- `/verify` runs only when you invoke it. Claude does not start the bundled one on its own.
- When `/verify` has to work out the steps itself, it writes them to `.claude/skills/verify/SKILL.md`. At the repo root, that recorded skill replaces the bundled `/verify`.
- The bundled `/verify` and plugin skills do not count for the before-commit behavior. Only a skill from your project, personal, enterprise or additional-directory location does.
