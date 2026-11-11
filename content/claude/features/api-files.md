---
id: api-files
title: Files API
surface: platform
group: Documents and output
status: stable
level: starter
payoff: 2
effort: 1
jobs: [automation, analysis]
tags: [files, upload, file-id, documents]
summary: The Files API stores a file once and gives you a file_id you can reference in later Messages requests, and it is how you download files that skills or the code execution tool create.
when: Reach for it when the same PDF, image or dataset is used in several requests, or when Claude generates a file you need to fetch. For a single small document, sending it inline is simpler.
replaces: Base64-encoding and re-uploading the same document with every request.
example_kind: command
docs:
  - title: Files API
    url: https://platform.claude.com/docs/en/build-with-claude/files
verified: 2026-11-11
---
## Try it in a minute
1. Upload a file with a POST to `/v1/files` and note the `id` in the response.
2. Reference it in a message. Use a `document` block for PDFs and plain text, an `image` block for images, and a `container_upload` block for data the code execution tool should open.
3. Ask your question in a `text` block next to it.
4. Delete the file with `DELETE /v1/files/{file_id}` when you are done, or set `expires_in_seconds` at upload.

## Example
```bash
# Upload once
curl -X POST https://api.anthropic.com/v1/files \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-10-21" \
  -F "file=@/path/to/design-doc.pdf"

# Reference it by id: FILE_ID is the id from the upload response
curl -X POST https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-10-21" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-opus-5-5",
    "max_tokens": 1024,
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "List the open questions and unstated assumptions in this design doc."
          },
          {
            "type": "document",
            "source": {
              "type": "file",
              "file_id": "'"$FILE_ID"'"
            }
          }
        ]
      }
    ]
  }'
```

## At work
- **A design doc or spec under review**: upload it once, then ask several separate questions without re-sending it.
- **Data analysis**: upload a metrics export, hand it to code execution with `container_upload`, and download the chart Claude produces.

## Pitfalls
- Files are scoped to the workspace, not to a user or conversation. Any API key with access to the workspace can read them, so never accept a `file_id` from an untrusted source.
- You cannot download a file you uploaded. Only files created by skills or the code execution tool are downloadable.
- A `document` block does not support .docx or .xlsx. Convert them to plain text, or use `container_upload` with code execution.
- Files cannot be modified or renamed, and deleted files cannot be recovered.
- Limits on the page are 500 MB per file and 1 TB per organization.
- File operations are free, but file content used in a message is billed as input tokens.
- The page marks the Files API as not eligible for zero data retention.
