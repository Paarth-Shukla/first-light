---
id: cc-voice-dictation
title: Voice dictation
surface: code
group: Session
status: stable
level: starter
payoff: 1
effort: 1
jobs: [coding, writing]
tags: [voice, dictation, input, accessibility]
summary: Voice dictation transcribes your speech live into the Claude Code prompt, using hold-to-record or tap-to-record, so you can mix speaking and typing in one message.
when: Use it for long, descriptive prompts such as a bug report or design intent that are quicker to say than to type.
replaces: Typing out a paragraph of context for every larger request.
example_kind: config
docs:
  - title: Voice dictation
    url: https://code.claude.com/docs/en/voice-dictation
verified: 2026-11-11
---
## Try it in a minute
1. In a local CLI session, run `/voice`. Claude Code runs a microphone check, and macOS may ask for microphone permission for your terminal.
2. Hold `Space`. After a brief warmup the footer shows `listening…`. Speak, then release to insert the text at the cursor.
3. Edit the text if needed and press `Enter` to send.
4. Run `/voice tap` to switch to tapping once to start and again to send, or `/voice off` to disable.

## Example
To keep dictation on in tap mode across sessions, add this to your user settings file:

```json
{
  "voice": {
    "enabled": true,
    "mode": "tap"
  }
}
```

## At work
- **Describing a bug.** Say what you saw, what you expected and what you already tried, then type the file path where precision matters.
- **Coding vocabulary.** Transcription is tuned for terms like `regex`, `OAuth`, `JSON` and `localhost`, and your project name and git branch are added as recognition hints.
- **Background sessions.** In hold mode, dictation also works in agent view, in the dispatch input and peek replies.

## Pitfalls
- Audio is streamed to Anthropic's servers for transcription. It is not processed locally.
- It needs a Claude.ai account and is not available with an API key, Amazon Bedrock, Google Cloud's Agent Platform or Microsoft Foundry.
- It needs a local microphone, so it does not work in cloud sessions or over SSH. The VS Code extension has the same limit in Remote sessions.
- In hold mode there is a short warmup before recording starts. Tap mode or a rebound modifier key avoids it.
- The `hold space to speak` hint does not appear if you have a custom status line.
- Transcription does not consume Claude messages or tokens.
