---
id: projects
title: Projects
surface: apps
group: Context
status: stable
level: starter
payoff: 3
effort: 1
jobs: [writing, research, coding, planning]
tags: [context, knowledge, instructions, rag]
summary: A project is a self-contained workspace with its own chats, uploaded knowledge and standing instructions.
when: Reach for a project when you keep pasting the same design doc, runbook or style rules into fresh chats. Set it up once and every chat in it starts with that background.
replaces: Re-uploading the same files and retyping the same ground rules at the top of every conversation.
example_kind: prompt
docs:
  - title: What are projects?
    url: https://support.claude.com/en/articles/9517075-what-are-projects
  - title: How can I create and manage projects?
    url: https://support.claude.com/en/articles/9519177-how-can-i-create-and-manage-projects
  - title: Retrieval augmented generation (RAG) for projects
    url: https://support.claude.com/en/articles/11473015-retrieval-augmented-generation-rag-for-projects
  - title: Usage limit best practices
    url: https://support.claude.com/en/articles/9797557-usage-limit-best-practices
verified: 2026-11-11
---
## Try it in a minute
1. Open [claude.ai/projects](https://claude.ai/projects) and click **+ New Project**. Give it a name and description.
2. On the project page, click **+** in the project knowledge area and upload the documents, text files or code you keep referring to.
3. Click **Set project instructions**, say how Claude should behave in this project, and click **Save instructions**.
4. Start a chat inside the project and ask about the uploaded files.

## Example
```text
This project covers the replication service for our block storage product.

Treat the uploaded design doc, runbook and API reference as the source of truth. Name the file you relied on for each claim. If the files do not answer a question, say so instead of guessing.

When I ask for a write-up, use short paragraphs and end with open questions.
```

## At work
- **One project per service.** With the design doc and runbook in project knowledge, "what does the failover path do?" is answered from your documents.
- **Onboarding.** On Team and Enterprise plans you can share a project with **Can view** or **Can edit** access, so a new teammate can question the same knowledge base.
- **Cheaper repeat questions.** Project content is cached, so reusing the same documents counts less against your usage limits than uploading them each time.

## Pitfalls
- Context is not shared across chats in a project unless it is in the project knowledge base.
- Claude does not see the project name or description.
- Free accounts can create at most five projects, and the expanded RAG knowledge capacity is for paid plans.
- Each project has its own memory. Turn off **Use account memory** on the project page to keep it fully separate.
- A new version of projects is rolling out in beta, starting with Claude Code, so yours may look different.
