---
id: cc-jetbrains
title: JetBrains IDE plugin
surface: code
group: Surfaces
status: stable
level: starter
payoff: 2
effort: 1
jobs: [coding, review, debugging]
tags: [jetbrains, intellij, pycharm, goland, ide]
summary: The JetBrains plugin connects the Claude Code CLI running in the IDE terminal to IntelliJ-family editors for diff viewing, selection sharing and diagnostics.
when: Use it when you work in IntelliJ IDEA, PyCharm, GoLand or another JetBrains IDE and want Claude's changes shown in the IDE diff viewer rather than as terminal text.
replaces: Reading diffs in the terminal and typing file paths and line ranges into prompts.
example_kind: prompt
docs:
  - title: JetBrains IDEs
    url: https://code.claude.com/docs/en/jetbrains
verified: 2026-11-11
---
## Try it in a minute
1. Install the Claude Code CLI first. The plugin does not bundle its own copy.
2. Install the Claude Code plugin from the JetBrains Marketplace and restart the IDE.
3. Run `claude` in the IDE's integrated terminal, or press `Cmd+Esc` (Mac) or `Ctrl+Esc` (Windows/Linux). From an external terminal, run `/ide` to connect.
4. Select code and press `Cmd+Option+K` (Mac) or `Alt+Ctrl+K` (Linux/Windows) to insert a file reference such as `@src/auth.ts#L1-99`.

## Example
```text
Review @src/main/java/com/acme/replica/SnapshotScheduler.java#L40-120 for thread-safety problems. Check the IDE diagnostics for this file first, then list each issue with its line and a suggested fix. Do not edit yet.
```

## At work
- **Diffs where you already review code.** Claude Code opens changes in the IDE diff viewer. The **Diff tool** setting in `/config` switches between `auto` and `terminal`.
- **Context without typing.** The current selection or tab is shared with Claude Code automatically.
- **Inspection results.** Claude can read the IDE's inspection diagnostics, such as lint and syntax errors, through the `getDiagnostics` tool.

## Pitfalls
- A "Cannot launch Claude Code" notification means `claude` is not on your PATH. Set the full path in the plugin's **Claude command** setting.
- With JetBrains Remote Development, install the plugin on the remote host via **Settings → Plugin (Host)**, not on your local client.
- If `Esc` does not interrupt Claude in the JetBrains terminal, go to **Settings → Tools → Terminal** and uncheck "Move focus to the editor with Escape".
- The docs advise considering Manual mode for edits in JetBrains IDEs, because `acceptEdits` may let Claude modify IDE configuration files that the IDE executes automatically.
- For Claude to see the same files as the IDE, start it from the IDE project root.
