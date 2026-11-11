---
id: cc-headless
title: Non-interactive mode
surface: code
group: Automation
status: stable
level: intermediate
payoff: 3
effort: 2
jobs: [automation, review, debugging, analysis]
tags: [headless, scripting, ci, pipes, json]
summary: Non-interactive mode runs Claude Code from a script or pipeline with claude -p, reading stdin and printing the result like any command-line tool.
when: Use it when a task should run inside a script, a CI job or a shell pipe rather than in a conversation you watch.
replaces: Opening a session to paste a log or diff and copying the answer back out.
example_kind: command
docs:
  - title: Run Claude Code programmatically
    url: https://code.claude.com/docs/en/headless
  - title: CLI reference
    url: https://code.claude.com/docs/en/cli-reference
verified: 2026-11-11
---
## Try it in a minute
1. Run `claude -p "What does the auth module do?"` in a project.
2. Pipe data in and redirect the answer out with `cat build-error.txt | claude -p 'concisely explain the root cause of this build error' > output.txt`.
3. Add `--output-format json` to get a JSON object with `result`, `session_id` and `total_cost_usd`.
4. Let it act by listing tools, for example `--allowedTools "Bash,Read,Edit"`.
5. Follow up on the same conversation with `claude -p "Now focus on the database queries" --continue`.

## Example
Save as `review.sh` and run `bash review.sh 123` to review pull request 123:

```bash
gh pr diff "$1" | claude -p \
  --append-system-prompt "You are a security engineer. Review for vulnerabilities." \
  --output-format json
```

## At work
- **A project-specific linter.** Pipe `git diff main` into `claude -p` from a build script and have it report issues as `filename:line`.
- **Log triage in a pipeline.** Pipe the tail of a log in and write the explanation to a file your on-call notes can link to.
- **Structured extraction.** `--output-format json` with `--json-schema` returns data matching your schema in `structured_output`, ready for `jq`.

## Pitfalls
- In a Manual mode `-p` run, a tool call that needs approval is denied unless something approves it. Pass `--allowedTools` or a `--permission-mode`.
- Without `--bare`, a `-p` run loads the project's hooks and connects its `.mcp.json` servers with no trust dialog, even in a folder you never trusted.
- `--bare` skips `CLAUDE.md`, hooks, skills, plugins and MCP discovery, and it does not use your subscription login, so set `ANTHROPIC_API_KEY`.
- Piped stdin is capped at 10MB. Reference a file path in the prompt for larger inputs.
- Cap runs with `--max-turns` and `--max-budget-usd`. The cost figures are client-side estimates.
