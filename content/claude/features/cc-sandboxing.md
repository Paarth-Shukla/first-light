---
id: cc-sandboxing
title: Sandboxed Bash
surface: code
group: Control and safety
status: stable
level: intermediate
payoff: 2
effort: 2
jobs: [coding, automation]
tags: [sandbox, security, network, filesystem, permissions]
summary: The Bash sandbox is an operating-system boundary around the shell commands Claude runs, limiting which files they can write and which network hosts they can reach.
when: Turn it on when you want fewer approval prompts for shell commands without handing decisions to a classifier, or when commands should not touch anything outside the project.
replaces: Approving every build and test command by hand, or trusting that a script stays inside the repository.
example_kind: config
docs:
  - title: Configure the sandboxed Bash tool
    url: https://code.claude.com/docs/en/sandboxing
  - title: Choose a permission mode
    url: https://code.claude.com/docs/en/permission-modes
verified: 2026-11-11
---
## Try it in a minute
1. In a session, run `/sandbox`. On macOS it works out of the box. On Linux and WSL2 the panel tells you if `bubblewrap` or `socat` is missing.
2. On the **Mode** tab, choose auto-allow so sandboxed commands run without prompting, or regular permissions to keep the prompts.
3. Ask Claude to run a build or test suite.
4. The first time a command needs a new network domain, approve or deny it.

## Example
Let sandboxed tools such as `kubectl` write to two extra locations:

```json
{
  "sandbox": {
    "enabled": true,
    "filesystem": {
      "allowWrite": ["~/.kube", "/tmp/build"]
    }
  }
}
```

## At work
- **Fewer prompts in Manual mode.** The docs pair Manual mode with the sandbox in auto-allow mode as a way to iterate locally without a classifier.
- **Contain builds and tests.** By default sandboxed commands can write only to the working directory, a per-user temp directory and directories you have added.
- **Control egress.** Connections go through a local proxy that checks each host against your allowed domains, which start empty.

## Pitfalls
- The sandbox covers shell commands only. Claude's file tools, WebFetch, MCP servers and hooks run outside it.
- It is off by default and runs on macOS, Linux and WSL2. On native Windows, commands run unsandboxed.
- Reads are broad by default, including credential files such as `~/.ssh`. Narrow them with `filesystem.denyRead`.
- When a command fails in the sandbox, Claude may retry it unsandboxed, subject to your permission mode.
- The docs call it risk reduction, not a complete isolation boundary. Allowing broad domains such as `github.com` can create paths for data exfiltration.
- Deny rules still apply in auto-allow mode, and ask rules that name a command, such as `Bash(git push *)`, still prompt.
