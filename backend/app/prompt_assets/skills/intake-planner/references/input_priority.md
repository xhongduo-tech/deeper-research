# Input Priority

Use this order whenever inputs conflict:

1. Explicit user instruction in the current conversation.
2. Uploaded file content and user-provided corrections.
3. Mounted knowledge-base content selected for this task.
4. Output format, selected template, and prompt asset skills.
5. User history or prior project context, when provided by the system.
6. Model prior knowledge.

## Conflict Response

- If the conflict changes the deliverable, ask for clarification or create a pause point.
- If the conflict is minor, proceed with the higher-priority input and log the assumption.
- If the template contains sample facts or demo titles, treat them as forbidden content.
- If the user gives a style preference that conflicts with a template, preserve content accuracy and adapt style as far as possible.

## User Requirement Contract

Before any drafting or rendering, convert the current input-box text into a compact contract:

- `goal`: what the user wants produced or answered.
- `audience`: who will read or watch it, if stated or inferable.
- `angle`: required perspective, such as comparison, risk, launch, review, forecast, policy, training, or sales.
- `must_cover`: entities, topics, metrics, sections, dates, regions, or questions explicitly named by the user.
- `must_avoid`: irrelevant template demos, unrelated uploaded-file sections, unsupported facts, and generic business filler.
- `source_use`: how uploads and KB snippets should support the request, not replace it.

Every downstream skill should receive this contract. A generated outline or draft fails if it cannot point to which user requirement each major section answers.

## Missing Inputs

Mark these as plan risks:

- Required file not uploaded.
- Output page count or word count unspecified for a constrained deliverable.
- Audience or use case unclear.
- "Latest/current" facts needed but no current source is available.
- Requested chart lacks numeric fields.
