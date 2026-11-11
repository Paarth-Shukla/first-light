---
id: automate-a-recurring-chore
title: Automate a recurring engineering chore with a scheduled task
job: automation
level: intermediate
minutes_saved: 30
features: [cc-routines, cc-scheduled-tasks]
prerequisites: ["A Pro, Max, Ultra, Team or Enterprise plan", GitHub access for the repository, Connectors for the services the task reads or writes]
fields:
  - name: repository
    label: Repository
    placeholder: storage-platform/replicator
  - name: chore
    label: The chore
    placeholder: find feature flags past their removal date and TODO comments that reference closed tickets
  - name: tracker_project
    label: Tracker project
    placeholder: STOR
  - name: output
    label: What a run should produce
    placeholder: one draft pull request that removes the dead flags, plus a list of everything else found
  - name: notify
    label: Where to report
    placeholder: a direct message to me in Slack
docs:
  - title: Automate work with scheduled tasks
    url: https://code.claude.com/docs/en/routines
  - title: Run prompts on a schedule
    url: https://code.claude.com/docs/en/scheduled-tasks
verified: 2026-11-11
---
## Steps
1. Do the chore once with Claude in a normal session and note every instruction you had to add.
2. Run `/schedule every Monday at 9:07am` and give Claude the prompt below when it asks. A run set exactly on the hour can start several minutes late, hence 9:07.
3. Open the task at [claude.ai/code/routines](https://claude.ai/code/routines) and remove connectors it does not need. All are included by default, and Claude can use them for writes.
4. Click **Run now**, then open the run from the **History** list to see what Claude did.
5. Tighten the prompt wherever the run had to guess.

## Prompt
```text
This prompt runs unattended every week as a scheduled task in {{repository}}. Nobody will answer questions during the run, so when something is ambiguous, take the conservative option and note it in the report.

The chore: {{chore}}.

For each candidate, check its status in {{tracker_project}} and confirm in the code that removing it is safe. Act only where both checks agree, and list the rest with the reason you skipped each one.

Output: {{output}}. Keep the pull request to these removals only. Run the repository's tests before opening it and put the test command and its result in the description. If the tests fail, open nothing and report the failure instead.

When you finish, send {{notify}} saying what you changed, what you skipped and why, and anything that needs a human decision. If there was nothing to do, say so in one line.
```

## Why it works
The scheduled tasks guide calls the prompt the most important part: the run is autonomous, so the prompt must be self-contained and say what success looks like. Runs start from a fresh clone and act as you, so commits, pull requests and Slack messages carry your identity. Hence the limits on the pull request and the stop on failing tests. For polling inside an open session, `/loop` is lighter.
