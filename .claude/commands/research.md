---
description: Produce a short brief on a company.
argument-hint: <company>
allowed-tools:
  - Bash(python -m harness.cli research *)
  - WebSearch
  - WebFetch
  - Read
---

# /research

```bash
cd "$CLAUDE_PROJECT_DIR" && PYTHONPATH="$CLAUDE_PROJECT_DIR/scripts" python -m harness.cli research "$1"
```

The Python side returns an offline stub. Enrich it by:

1. `WebSearch` for the company's engineering blog + latest news.
2. `WebFetch` one authoritative source (careers page, latest press
   release, or engineering post).
3. Summarize: products, current tech stack signals, recent shifts,
   possible interview themes. Keep it under 250 words.

Save the enriched brief to `applications/<APP-ID>/research.md` if the
user asks; otherwise print it inline.
