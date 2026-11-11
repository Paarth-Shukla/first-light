---
id: cc-code-intelligence
title: Code intelligence plugins
surface: code
group: Extend
status: stable
level: intermediate
payoff: 2
effort: 2
jobs: [coding, debugging, review]
tags: [lsp, language-server, diagnostics, navigation, plugins]
summary: A code intelligence plugin connects Claude Code to a language server so Claude sees type errors after its edits and finds definitions and references by symbol.
when: Install one for a typed language in a large codebase, where text search returns too many candidates and you want errors caught before a build.
replaces: Waiting for the compiler to reveal a type error Claude introduced, and grep-then-read searches for a definition.
example_kind: command
docs:
  - title: Code intelligence plugins
    url: https://code.claude.com/docs/en/plugins/code-intelligence
  - title: Manage costs effectively
    url: https://code.claude.com/docs/en/costs
verified: 2026-11-11
---
## Try it in a minute
1. Install the language server binary for your language. The docs table pairs each plugin with its binary, for example `gopls` for Go, `clangd` for C/C++, `pyright-langserver` for Python and `rust-analyzer` for Rust. Each plugin's README has the install command.
2. Check the binary is on the `PATH` of the shell you start `claude` from, for example with `which gopls`.
3. In a session, install the matching plugin with the command below.
4. Ask Claude to introduce a type error in a file of that language and then fix it. A line such as `Found N new diagnostic issues in M files (ctrl+o to expand)` means the server started.

## Example
```text
/plugin install gopls-lsp@claude-plugins-official
```

## At work
- **Errors caught at edit time.** Each time Claude edits a file the server handles, it gets the server's errors and warnings, so a missing import shows up without running a compiler.
- **Navigation in big repositories.** Claude gets a read-only `LSP` tool that looks up symbols through the server. The costs guide notes that one go-to-definition call can replace a grep followed by reading several candidate files.

## Pitfalls
- The plugin does not include the language server. Without the binary, `/plugin` shows `Executable not found in $PATH` on its **Errors** tab.
- Code intelligence plugins work in terminal sessions. In cloud sessions Claude Code does not start plugin language servers.
- The server starts the first time Claude edits a file with one of the plugin's extensions, not when the session opens.
- If you installed the binary somewhere that is not on the `PATH` of the shell that launched `claude`, start a new session from a shell where it is.
