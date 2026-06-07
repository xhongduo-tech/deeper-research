# QA Report Schema

Use a compact report that supports repair.

## Fields

- `overall_status`: pass | pass_with_risks | repair_required | blocked
- `artifact_type`
- `checked_scope`
- `issues`
- `repair_plan`
- `residual_risks`
- `final_handoff_notes`

## Issue Object

- `id`
- `severity`: P0 | P1 | P2 | P3
- `location`: slide/section/sheet/page/cell when available
- `category`: fact | logic | calculation | structure | format | export | instruction
- `problem`
- `evidence`
- `recommended_fix`
- `owner_skill`

## Status Rules

- `blocked`: missing required artifact, unreadable export, or no evidence for core requested claims.
- `repair_required`: P0 or unresolved P1 exists.
- `pass_with_risks`: no P0/P1, but assumptions or source gaps remain.
- `pass`: no material issues and required outputs are complete.

## Repair Loop

1. Fix P0 and P1 first.
2. Re-run the checks that found the issue.
3. Update residual risks only for issues that cannot be fixed with available inputs.
4. Do not expand scope during QA unless required to satisfy the user's original request.
