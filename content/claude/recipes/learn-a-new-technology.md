---
id: learn-a-new-technology
title: Learn a new technology with a personal syllabus and exercises
job: learning
level: intermediate
minutes_saved: 60
features: [projects, artifacts, cc-output-styles]
prerequisites: [The official documentation for the technology saved as files, Claude Code in a real repository for the practice step]
fields:
  - name: technology
    label: What you are learning
    placeholder: Kubernetes operators written with controller-runtime
  - name: background
    label: What you already know
    placeholder: eight years of Go and Linux storage, comfortable with Docker, never written a controller
  - name: goal
    label: What you need to be able to do
    placeholder: review and extend our volume-snapshot operator by the end of the month
  - name: time
    label: Time you have
    placeholder: 30 minutes a day for three weeks
docs:
  - title: What are projects?
    url: https://support.claude.com/en/articles/9517075-what-are-projects
  - title: How can I create and manage projects?
    url: https://support.claude.com/en/articles/9519177-how-can-i-create-and-manage-projects
  - title: What are artifacts and how do I use them?
    url: https://support.claude.com/en/articles/17153992-what-are-artifacts-and-how-do-i-use-them
  - title: Output styles
    url: https://code.claude.com/docs/en/output-styles
verified: 2026-11-11
---
## Steps
1. At [claude.ai/projects](https://claude.ai/projects) click **+ New Project**, then upload the official docs and your team's design doc to the project knowledge.
2. Click **Set project instructions**, paste the prompt below and click **Save instructions**.
3. In a project chat, ask for the syllabus and add it to project knowledge. Chats in a project do not share context unless it is in the knowledge base.
4. For each module, ask for an artifact: a quiz that uses Claude to give feedback on your free-text answers. A new artifact asks permission the first time it uses Claude.
5. To practise on real code, run `/output-style learning` in Claude Code. Claude does the routine work and leaves `TODO(human)` markers where there is a real design decision for you to write.

## Prompt
```text
This project is my study plan for {{technology}}.
My background: {{background}}.
My goal: {{goal}}.
Time I have: {{time}}.

Use the uploaded files as the main source and name the file behind each explanation. Where the files do not cover something, say so instead of filling the gap from memory, because this technology changes quickly and I need to be able to check what you tell me.

When I ask for a syllabus, plan modules that fit the time I have, each building on the last. For each module give the concepts, the sections of the uploaded docs to read, one exercise I do myself in a real codebase, and how I will know I have understood it. Spend the time on what is new to someone with my background and skip what it already covers.

When I ask a question, connect the answer to something from my background, then give the precise version. At the end of each module, write a short note of what I got wrong or found hard, so I can add it to the project knowledge for the next module.
```

## Why it works
Project instructions and knowledge apply to every chat in the project, so each session starts with your background and the same sources. The prompt gives the reason for sticking to those files, which the prompting guide says lets Claude generalise the rule. The end-of-module note carries what you learned across chats, and the Learning style makes the practice your real code.
