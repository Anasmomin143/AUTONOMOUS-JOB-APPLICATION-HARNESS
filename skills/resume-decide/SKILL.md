---
name: resume-decide
description: For a scored job, decide whether to use the master resume as-is or build a tailored one. Never invents facts — tailoring reweights and reorders content that already exists in the master profile.
---

# resume-decide

Backing modules:
- `harness.resume.decide.decide(job, score, cfg, profile)` — returns `("master"|"tailored", rationale)`.
- `harness.resume.tailor.tailor(job, profile)` — builds tailored Markdown.
- `harness.resume.validate.validate(md, profile)` — rejects fabricated tokens.
- `harness.resume.render.render(md, out_pdf)` — renders to PDF (WeasyPrint).

Rule (spec §9): use master when the score is already high AND the JD's
tech is a subset of what the master emphasizes. Otherwise tailor.
