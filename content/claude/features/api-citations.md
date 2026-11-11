---
id: api-citations
title: Citations
surface: platform
group: Documents and output
status: stable
level: intermediate
payoff: 2
effort: 1
jobs: [research, writing, analysis]
tags: [citations, documents, grounding, verification]
summary: Citations make Claude return the exact passages from your supplied documents that support each claim in its answer, with the location of each passage.
when: Reach for it when an answer drawn from a document has to be checkable, such as an incident summary built from logs or a policy question. It is more reliable than asking Claude in the prompt to quote its sources.
replaces: Searching a document by hand to confirm that a quoted sentence is really there.
example_kind: command
docs:
  - title: Citations
    url: https://platform.claude.com/docs/en/build-with-claude/citations
verified: 2026-11-11
---
## Try it in a minute
1. Put your source in a `document` content block. Plain text, PDF and custom content documents are supported.
2. Add `"citations": {"enabled": true}` to every document in the request.
3. Ask your question in a `text` block after the documents.
4. Read the response. It is split into several `text` blocks, and blocks that make a claim carry a `citations` list with `cited_text` and a location.

## Example
```bash
curl https://api.anthropic.com/v1/messages \
  -H "content-type: application/json" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-10-21" \
  -d '{
    "model": "claude-opus-5-5",
    "max_tokens": 1024,
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "type": "document",
            "source": {
              "type": "text",
              "media_type": "text/plain",
              "data": "02:14 Controller B stopped answering heartbeats. 02:15 Failover to controller A started. 02:19 Failover completed. 02:31 Replication to the DR site resumed."
            },
            "title": "Incident timeline",
            "context": "Exported from the on-call channel.",
            "citations": {"enabled": true}
          },
          {
            "type": "text",
            "text": "How long did the failover take, and when did replication resume?"
          }
        ]
      }
    ]
  }'
```

## At work
- **Incident write-ups**: every statement in the summary points back to the timeline or log line it came from.
- **Questions over specs and contracts**: PDF citations include page numbers, so a reviewer can jump to the page.
- **Retrieval pipelines**: put each retrieved chunk in its own document so Claude cites specific sentences.

## Pitfalls
- Citations cannot be combined with structured outputs. Sending `output_config.format` with citations enabled returns a 400 error.
- Enable citations on all documents in a request or on none.
- Only text can be cited. Images, including images inside PDFs, cannot.
- Plain text and PDFs are chunked into sentences. For lists or transcripts, use a custom content document to control granularity.
- `title` and `context` are passed to the model but cannot be cited.
- Enabling citations slightly increases input tokens. `cited_text` does not count toward output tokens.
