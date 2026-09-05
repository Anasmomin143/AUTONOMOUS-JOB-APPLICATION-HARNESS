---
name: application-preparation
description: Take a qualified job through to READY_FOR_APPROVAL — resume decision, tailoring, validation, PDF render, screening-answer preflight, application record creation. Never submits.
---

# application-preparation

Backing CLI: `python -m harness.cli prepare --job-id <id>`.

Produces a full `applications.json` record with:

- resume decision + file path,
- screening-answer preflight (unresolved ones become STOP conditions),
- status `READY_FOR_APPROVAL`,
- activity-log entry.

Prep is the last automatic step before the human gate in the default
supervised flow (spec §14).
