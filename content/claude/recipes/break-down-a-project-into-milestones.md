---
id: break-down-a-project-into-milestones
title: Estimate a project and break it into milestones
job: planning
level: intermediate
minutes_saved: 60
features: [effort-and-thinking, claude-sheets, connectors]
prerequisites: [The design doc or project brief, A connector for your issue tracker if you want the tickets created]
fields:
  - name: brief
    label: Design doc or brief
    placeholder: Paste the design doc or project brief
  - name: known_risks
    label: What is already known
    placeholder: Paste dependencies on other teams, open unknowns, holidays and on-call load
  - name: team
    label: Team
    placeholder: three backend engineers, one of them half-time on on-call, and a shared QA engineer
  - name: deadline
    label: Constraint
    placeholder: a beta for two design partners by 31 March
  - name: readers
    label: Who uses the plan
    placeholder: my manager and our product partner
docs:
  - title: Change the model, effort, and thinking settings
    url: https://support.claude.com/en/articles/8664678-change-the-model-effort-and-thinking-settings
  - title: Get started with Claude Sheets
    url: https://support.claude.com/en/articles/18324300-get-started-with-claude-sheets
  - title: Use connectors to extend Claude's capabilities
    url: https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities
verified: 2026-11-11
---
## Steps
1. Click the model name next to the send button, click **Effort** and choose a higher level. Expect a slower reply that uses more of your limit.
2. Send the prompt below with the brief pasted in.
3. Ask which milestone is most likely to slip and what must be true for the deadline to hold.
4. Ask for the breakdown as a sheet with formulas summing each milestone, so totals update as you change numbers. Claude Sheets is in beta on paid plans.
5. Once the plan is agreed, turn on your issue tracker under **+** and **Connectors** and ask Claude to create the epics and stories. Read the list before it creates anything.

## Prompt
```text
<brief>
{{brief}}
</brief>

<known_risks>
{{known_risks}}
</known_risks>

Break this project into milestones and estimate it. Team: {{team}}. Constraint: {{deadline}}. The plan goes to {{readers}}, who will use it to decide scope, so an honest range is more useful than a precise number.

1. Milestones: each ends in something we can demonstrate, with a one-line definition of done.
2. Work items under each milestone, sized small (up to 2 days), medium (up to a week) or large (more than a week). Split anything large until it is not.
3. Dependencies between items and on other teams, with the critical path marked.
4. An estimate per milestone as a best case and a likely case in engineer-weeks, listing your assumptions, including time lost to on-call, reviews and integration.
5. The three biggest risks, each with an early warning sign and what we would cut first if it happens.
6. Whether the constraint is achievable, and if not, which scope cut would make it achievable.

Mark the estimates you are least sure of and say what information would firm them up. Keep this as a plan for review; tickets come later.
```

## Why it works
The help center names comprehensive project planning among the tasks that benefit from higher effort. The prompt explains why ranges beat a single number, forces large items apart, and puts assumptions next to each estimate so reviewers argue with the inputs rather than the total. Creating tickets as a separate step means the tracker only receives the agreed plan.
