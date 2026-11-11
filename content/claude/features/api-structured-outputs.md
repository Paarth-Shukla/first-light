---
id: api-structured-outputs
title: Structured outputs
surface: platform
group: Documents and output
status: stable
level: intermediate
payoff: 3
effort: 2
jobs: [automation, analysis]
tags: [json, schema, extraction, structured-outputs]
summary: Structured outputs constrain Claude's response to a JSON schema you supply, so the text block always parses and always has the required fields.
when: Reach for it whenever a script consumes the answer, such as filling Jira fields, writing spreadsheet rows or routing alerts. Plain prose is fine when a person reads the reply.
replaces: Asking for JSON in the prompt, then writing retry and repair code for the times it does not parse.
example_kind: command
docs:
  - title: Structured outputs
    url: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
verified: 2026-11-11
---
## Try it in a minute
1. Describe the result as a JSON schema. Set `"additionalProperties": false` on every object and list the fields you need in `required`.
2. Send it in `output_config.format` with `"type": "json_schema"`. No beta header is required.
3. Parse the response's text content block as JSON.
4. Check `stop_reason` before trusting the result.

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
        "content": "Extract the key information from this bug report: After upgrading to 6.4.2 the nightly snapshot job on cluster east-2 fails with a timeout. Data is safe, but backups are a day old. Reported by Priya from the platform team."
      }
    ],
    "output_config": {
      "format": {
        "type": "json_schema",
        "schema": {
          "type": "object",
          "properties": {
            "summary": {"type": "string"},
            "component": {"type": "string"},
            "severity": {"type": "string", "enum": ["low", "medium", "high"]},
            "data_loss": {"type": "boolean"}
          },
          "required": ["summary", "component", "severity", "data_loss"],
          "additionalProperties": false
        }
      }
    }
  }'
```

## At work
- **Ticket intake**: turn free-text bug reports into fields you can post straight to Jira.
- **Log and document extraction at scale**: the docs list batch processing as compatible, so large extraction jobs can run there.
- **Agent tools**: the companion feature, `strict: true` on a tool, guarantees tool inputs match your schema.

## Pitfalls
- The first request with a new schema is slower while the grammar compiles. It is then cached for 24 hours from last use.
- Not all of JSON Schema is supported. Recursive schemas, `minimum` and `maximum`, `minLength` and `maxLength` return a 400 error.
- Output can still be invalid when `stop_reason` is `"refusal"` or `"max_tokens"`.
- Enum capitalisation is not guaranteed, so compare enum values case-insensitively.
- Incompatible with citations and with message prefilling.
- Changing `output_config.format` invalidates the prompt cache for that conversation.
- A request allows at most 24 optional parameters and 16 union-typed parameters across its strict schemas.
- A property that asks for step-by-step reasoning may trigger a refusal. Ask for a short explanation instead.
