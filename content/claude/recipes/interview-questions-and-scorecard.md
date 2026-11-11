---
id: interview-questions-and-scorecard
title: Prepare interview questions and a scorecard from a job description
job: meetings
level: starter
minutes_saved: 45
features: [projects, claude-docs, claude-sheets]
prerequisites: [The job description, Your team's leveling guide or interview rubric if you have one]
fields:
  - name: role
    label: Role
    placeholder: senior software engineer, distributed storage
  - name: interview
    label: Your round
    placeholder: the 60-minute system design round
  - name: must_test
    label: What this round must test
    placeholder: reasoning about consistency and failure modes, and making trade-offs explicit
docs:
  - title: What are projects?
    url: https://support.claude.com/en/articles/9517075-what-are-projects
  - title: How can I create and manage projects?
    url: https://support.claude.com/en/articles/9519177-how-can-i-create-and-manage-projects
  - title: Get started with Claude Docs
    url: https://support.claude.com/en/articles/16923645-get-started-with-claude-docs
  - title: Get started with Claude Sheets
    url: https://support.claude.com/en/articles/18324300-get-started-with-claude-sheets
verified: 2026-11-11
---
## Steps
1. Create a project for the hiring loop and upload the job description and leveling guide to its knowledge. On Team and Enterprise plans you can share it with the panel with **Can view** access.
2. In a chat in the project, send the prompt below.
3. Ask Claude to put the questions in a doc and share it so the panel can comment.
4. Ask for the scorecard as a sheet with a formula for the weighted total. Claude Sheets is in beta on paid plans.
5. Have another interviewer answer the questions and score them with the anchors. Where you disagree, tighten the anchor.

## Prompt
```text
Using the job description and leveling guide in this project, prepare my part of the interview loop for {{role}}. I run {{interview}}, and it must test {{must_test}}.

The goal is a fair and consistent loop: every candidate gets the same core questions and is scored against the same written anchors, so two interviewers would give the same score for the same answer.

Produce:
1. Two core questions grounded in problems this role actually works on, each with three follow-ups that go deeper depending on the answer.
2. For each competency, what a strong, an adequate and a weak answer sound like at this level, tied to the wording in the leveling guide.
3. Signals that should not move the score, such as confidence or familiarity with our particular tools, and how to note them separately.
4. A scorecard: competencies, weights, the anchors from item 2 as a 1 to 4 scale, and space for quoted evidence.

Keep every question about the work: what the candidate has done or would do. Flag anything in the job description vague enough that interviewers might read it differently.
```

## Why it works
Project knowledge applies to every chat in the project, so each interviewer works from the same job description and rubric. Stating the goal, consistent scoring, gives Claude the reason behind the anchors, which the prompting guide says improves targeting. A sheet keeps formulas in the cells, so anyone can check the weighted score.
