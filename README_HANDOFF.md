# Claude Code Fable Handoff Pack

## Files

```text
CLAUDE.md
docs/
  PRODUCT_ANALYSIS_SPEC.md
  FABLE_EXECUTION_PLAN.md
  IMPLEMENTATION_STATUS.md
START_FABLE_PROMPT.md
NEXT_PHASE_PROMPT_TEMPLATE.md
.claude/
  agents/
    domain-reviewer.md
```

## Placement

Copy the contents of this pack into the root of the existing project.

- Merge carefully if the repository already has a `CLAUDE.md`.
- Do not overwrite existing project instructions without reviewing them.
- Keep `PRODUCT_ANALYSIS_SPEC.md` in `docs/`.
- Run Claude Code from the repository root.

## Recommended start

1. Update Claude Code to a version that supports Fable.
2. Select Fable in Claude Code.
3. Start in plan mode for the first repository review if desired.
4. Paste `START_FABLE_PROMPT.md`.
5. Review Phase 0/1 output before continuing.
6. Use `NEXT_PHASE_PROMPT_TEMPLATE.md` for later phases.

## Why the pack is split

- `CLAUDE.md` stays concise so it can guide every session.
- The full product plan loads only when needed.
- The execution plan provides stable phase boundaries.
- The status file prevents context loss between sessions.
- The optional domain reviewer checks analysis language without editing code.

## Important

The pack intentionally does not prescribe exact repository file paths, frameworks, commands, or database technology. Claude must discover and reuse the existing architecture during Phase 0.
