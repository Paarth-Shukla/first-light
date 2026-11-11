---
id: cc-keybindings
title: Keyboard shortcuts and keybindings
surface: code
group: Setup and cost
status: stable
level: starter
payoff: 2
effort: 1
jobs: [coding]
tags: [keybindings, shortcuts, terminal, productivity]
summary: Claude Code has built-in keyboard shortcuts for common session actions, and a keybindings.json file where you can rebind them or bind a key to any command.
when: Learn the defaults first, then customize when a shortcut clashes with your terminal or you run the same command many times a day.
replaces: Typing out commands like /compact or reaching for the mouse to open an editor.
example_kind: config
docs:
  - title: Customize keyboard shortcuts
    url: https://code.claude.com/docs/en/keybindings
  - title: Interactive mode
    url: https://code.claude.com/docs/en/interactive-mode
verified: 2026-11-11
---
## Try it in a minute
1. Run `/keybindings` to create or open `~/.claude/keybindings.json`.
2. Paste the block below and save. Changes are detected and applied without restarting.
3. Press the new key in the chat input to check it works.
4. If nothing happens, start Claude Code with `--debug`. Validation warnings go to the debug log.

## Example
```json
{
  "$schema": "https://www.schemastore.org/claude-code-keybindings.json",
  "bindings": [
    {
      "context": "Chat",
      "bindings": {
        "meta+g": "command:compact",
        "ctrl+e": "chat:externalEditor"
      }
    }
  ]
}
```

## At work
- **Defaults worth memorizing.** `Shift+Tab` cycles permission modes, `Esc` interrupts Claude, `Esc` twice on an empty prompt opens the rewind menu, `Ctrl+B` backgrounds a running command, `Ctrl+O` toggles the transcript viewer and `Ctrl+R` searches history.
- **Long prompts.** `Ctrl+G` opens the prompt in your default text editor, and `Ctrl+S` stashes a draft and restores it later.
- **One key for a command.** `command:<name>` runs `/<name>`, so `meta+g` above runs `/compact`.

## Pitfalls
- `Ctrl+C`, `Ctrl+D`, `Ctrl+M`, `Ctrl+I` and a few others are reserved and cannot be rebound.
- `Ctrl+B` is the tmux prefix, so press it twice there. `Ctrl+A` clashes with GNU screen.
- On macOS, Option-key shortcuts need Option configured as Meta in your terminal.
- Each keystroke of a chord must follow the previous one within 3 seconds.
- A misspelled modifier such as `ctl+k` is dropped and the binding applies to the remaining key. A space next to `+` makes the binding never fire.
- An unknown action name is skipped and any default binding for that key stays in effect.
- To unbind a default, set its keystroke to `null`, as in `"ctrl+s": null`.
