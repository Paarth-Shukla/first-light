---
id: claude-motion
title: Claude Motion
surface: apps
group: Make things
status: beta
level: starter
payoff: 1
effort: 1
jobs: [meetings, writing, learning]
tags: [motion, animation, video, artifacts]
summary: Claude Motion is the artifact template that turns your content into short animations, such as an explainer or an animated chart, built as code and exported as MP4.
when: Use it when a moving explanation will land better than a static slide, for example showing how a process flows or how a number changed. It is not for realistic footage.
replaces: Screen-recording a slide transition, or asking someone with video tools to animate a chart.
example_kind: prompt
docs:
  - title: Get started with Claude Motion
    url: https://support.claude.com/en/articles/17454997-get-started-with-claude-motion
  - title: What are artifacts and how do I use them?
    url: https://support.claude.com/en/articles/17153992-what-are-artifacts-and-how-do-i-use-them
verified: 2026-11-11
---
## Try it in a minute
1. Ask Claude for an animation in any chat, or select **Output** in the message box and choose **Motion**, or select a Motion template in the **Artifacts** tab.
2. Say who will watch it, where it will play and roughly how long it should be.
3. Attach the report, data or images Claude should build from.
4. Ask for changes such as "Slow down the second scene", or adjust the animation yourself in the editor.
5. Click **Export** and choose MP4, or click **Share**.

## Example
```text
Make a 30-second animated explainer for our engineering all-hands showing how a write travels through our storage stack.

Scenes: client request arrives, write lands in the journal, data is acknowledged, background process moves it to its final location, replica catches up. Label each component, show the acknowledgement point clearly, and end on one line of text stating the durability guarantee. It will play on a projector without sound.
```

## At work
- **Explaining a system.** A short walkthrough of a data path or a failover sequence for onboarding or an all-hands.
- **Animated charts.** The docs give an animated chart for a deck as a standard use.
- **Cheap revisions.** Because each animation is code, you can change one word, number or timing and the rest stays as it was.

## Pitfalls
- Claude Motion is in beta on Team and Enterprise plans only, per the docs, and is off by default on Enterprise plans until an owner turns it on.
- It does not use a video generation model, so it does not create realistic footage or people.
- Animations start private to you. Sharing is a separate step.
- Longer or more complex animations use more of your usage limit than a typical message.
