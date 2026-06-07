# SlideSpec Schema

Each generated deck should be representable as a list of SlideSpec objects.

## Required Fields

- `id`
- `role`: cover | agenda | takeaway | evidence | metric | comparison | timeline | table | recommendation | closing | appendix
- `title`
- `core_message`
- `evidence_refs`
- `visual_object`: none | metric | chart | table | diagram | image | timeline | comparison
- `layout_family`: executive | technical | editorial | sketch | clean
- `density`: low | medium | high
- `bullets`
- `speaker_note`
- `qa_checks`

## Optional Fields

- `audience_question`
- `source_labels`
- `chart_spec`
- `table_spec`
- `image_prompt_or_asset`
- `appendix_link`
- `assumption_flags`

## Validation Rules

- `core_message` is the reason the slide exists.
- `title` should express the message unless the slide is cover or appendix.
- `bullets` support the message and must not become a paragraph dump.
- `visual_object` should be native/editable when exported to PPTX.
- `density` controls whether to split, compress, or move content into notes.
- `qa_checks` should include evidence, logic, fit, and export checks.
