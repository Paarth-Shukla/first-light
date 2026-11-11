---
id: cc-sessions
title: Resume, name and branch sessions
surface: code
group: Session
status: stable
level: starter
payoff: 2
effort: 1
jobs: [coding, planning]
tags: [sessions, resume, branch, history]
summary: A session is a saved conversation tied to a project directory, which you can name, resume later and branch to try a different approach.
when: Use it when a task spans several sittings or you want to try another direction without losing the path you were on, instead of starting over and re-explaining.
replaces: Re-explaining yesterday's context to a fresh session.
example_kind: command
docs:
  - title: Manage sessions
    url: https://code.claude.com/docs/en/sessions
  - title: CLI reference
    url: https://code.claude.com/docs/en/cli-reference
  - title: Checkpointing
    url: https://code.claude.com/docs/en/checkpointing
verified: 2026-11-11
---
## Try it in a minute
1. Start a named session with `claude -n auth-refactor`, or name the current one with `/rename auth-refactor`.
2. Exit, then return with `claude --resume auth-refactor`. `claude --continue` reopens the most recent session in the current directory.
3. Run `claude --resume` with no argument to open the session picker. Type to search, press `Space` to preview and `Ctrl+A` to show sessions from all projects.
4. Inside a session, run `/branch try-streaming-approach` to copy the conversation and switch into the copy.

## Example
```bash
claude -n oauth-migration            # start a named session
claude --resume oauth-migration      # pick it up tomorrow
claude --continue --fork-session     # try another approach from a copy
claude --from-pr 1234                # find the sessions linked to a pull request
```

## At work
- **Multi-day work.** A resumed session restores the conversation, the model, the permission mode in most terminal cases and an active goal. Checkpoints come back too.
- **Find the session behind a PR.** Sessions are linked automatically when Claude creates the pull request, and you can also paste a PR URL into the picker's search.
- **Two ideas, one starting point.** `/branch` leaves the original intact, and `/resume <original-name>` returns to it.

## Pitfalls
- Flags from the original launch are not all restored. Pass `--mcp-config`, `--settings`, `--plugin-dir` and `--add-dir` directories again.
- The default display name, such as `my-app-3f`, is not a resume handle. Use a name you set or the generated title.
- If you resume the same session in two terminals without forking, messages from both interleave into one transcript.
- Background Bash commands are not restarted on resume, and a tool that was running when the process ended is not rerun.
