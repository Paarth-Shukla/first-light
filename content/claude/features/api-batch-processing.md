---
id: api-batch-processing
title: Message Batches API
surface: platform
group: Cost and scale
status: stable
level: intermediate
payoff: 3
effort: 2
jobs: [automation, analysis]
tags: [batch, cost, async, evaluation]
summary: The Message Batches API takes many Messages requests at once, processes them asynchronously and, according to the docs, reduces costs by 50 percent.
when: Reach for it when you have a pile of independent requests and nobody is waiting on the answer, such as nightly ticket summaries or an evaluation run. Use the normal Messages API when a person needs the reply now.
replaces: A loop of synchronous calls with hand-written rate-limit handling, paid at full price.
example_kind: command
docs:
  - title: Batch processing
    url: https://platform.claude.com/docs/en/build-with-claude/batch-processing
verified: 2026-11-11
---
## Try it in a minute
1. Build a `requests` list. Each entry has a unique `custom_id` and a `params` object holding ordinary Messages API parameters.
2. POST it to `/v1/messages/batches` and keep the returned batch `id`.
3. Poll `/v1/messages/batches/$MESSAGE_BATCH_ID` until `processing_status` is `ended`.
4. Fetch `/v1/messages/batches/$MESSAGE_BATCH_ID/results`. It is a `.jsonl` stream with one result per line.
5. Match each line to its request by `custom_id`.

## Example
```bash
curl https://api.anthropic.com/v1/messages/batches \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-10-21" \
  -H "content-type: application/json" \
  -d '{
    "requests": [
      {
        "custom_id": "ticket-STOR-1412",
        "params": {
          "model": "claude-opus-5-5",
          "max_tokens": 1024,
          "messages": [
            {"role": "user", "content": "Summarize this ticket in two sentences and name the likely component: Volume resize fails with ENOSPC although the pool reports 40 percent free."}
          ]
        }
      },
      {
        "custom_id": "ticket-STOR-1413",
        "params": {
          "model": "claude-opus-5-5",
          "max_tokens": 1024,
          "messages": [
            {"role": "user", "content": "Summarize this ticket in two sentences and name the likely component: Snapshot schedule skips runs after a controller failover."}
          ]
        }
      }
    ]
  }'
```

## At work
- **Nightly backlog digests**: summarise or label every ticket updated that day and read the results in the morning.
- **Evaluations**: run thousands of test cases against a prompt change as one job, at half the standard price.

## Pitfalls
- Results can come back in any order. Always match on `custom_id`.
- Most batches finish in under an hour, but a batch can take up to 24 hours and unprocessed requests then expire.
- A batch holds at most 100,000 requests or 256 MB, whichever comes first.
- Results stay downloadable for 29 days after the batch was created.
- `stream: true`, `speed` and `max_tokens: 0` are rejected inside a batch.
- A batch can take longer than the 5-minute cache lifetime, so use the 1-hour cache duration for shared context.
- Dry run one request shape through the Messages API first to catch validation errors.
