---
id: api-pdf-and-vision
title: PDF and image input
surface: platform
group: Documents and output
status: stable
level: starter
payoff: 2
effort: 1
jobs: [analysis, research, debugging]
tags: [pdf, vision, images, documents]
summary: Claude reads PDFs and images sent in a Messages request, including the text, charts, tables and diagrams in them, through document and image content blocks.
when: Reach for it when the source is a PDF spec, a scanned report, a dashboard screenshot or an architecture diagram and retyping it would lose the visual content. For plain text, send text.
replaces: Copying text out of PDFs by hand and describing screenshots in words.
example_kind: command
docs:
  - title: PDF support
    url: https://platform.claude.com/docs/en/build-with-claude/pdf-support
  - title: Vision
    url: https://platform.claude.com/docs/en/build-with-claude/vision
verified: 2026-11-11
---
## Try it in a minute
1. For a PDF, add a `document` content block. Its `source` can be a `url`, `base64` data or a `file_id` from the Files API.
2. For an image, add an `image` content block with the same three source types. JPEG, PNG, GIF and WebP are supported.
3. Put the document or image before your question. The docs say Claude works best with that order.
4. Ask about text, tables, charts or diagrams, and use the page numbers your PDF viewer shows.

## Example
```bash
# Encode a local PDF file
base64 document.pdf | tr -d '\n' > pdf_base64.txt

# Create a JSON request file using the pdf_base64.txt content
jq -n --rawfile PDF_BASE64 pdf_base64.txt '{
  "model": "claude-opus-5-5",
  "max_tokens": 1024,
  "messages": [{
    "role": "user",
    "content": [{
      "type": "document",
      "source": {
        "type": "base64",
        "media_type": "application/pdf",
        "data": $PDF_BASE64
      }
    },
    {
      "type": "text",
      "text": "Summarize the performance results in this benchmark report and list every configuration parameter it mentions, with page numbers."
    }]
  }]
}' > request.json

# Send the API request using the JSON file
curl https://api.anthropic.com/v1/messages \
  -H "content-type: application/json" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-10-21" \
  -d @request.json
```

## At work
- **Vendor specs and benchmark reports**: ask about a chart or table directly, because each page is processed as both extracted text and an image.
- **Dashboard screenshots in an incident**: attach the Grafana screenshot and ask what changed at the time of the alert.

## Pitfalls
- A request can hold up to 600 PDF pages (100 when the context window is under 1M tokens), and the PDF cannot be password protected or encrypted.
- Dense PDFs can fill the context window before the page limit. Split them into sections.
- Each page typically uses 1,500 to 3,000 text tokens, plus image tokens for the page.
- .docx and .xlsx are not supported in document blocks. Convert them to text or PDF first.
- Large images are downscaled, which can make small text unreadable. Resize or crop before sending.
- Counts and coordinates read from images are approximate, low-quality or rotated images raise the error rate, and Claude will not name people in images.
