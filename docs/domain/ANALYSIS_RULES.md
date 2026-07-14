# Analysis Rules

## Statement types
Every analysis item must be one of:

- `observation`: directly supported by data;
- `hypothesis`: plausible interpretation requiring review;
- `limitation`: missing or unreliable context;
- `replay_question`: what the user should verify;
- optional `practice_suggestion`: a bounded experiment based on evidence.

## Evidence
Factual claims should reference:
- match ID;
- event or episode ID;
- time or time range;
- source fields;
- rule/feature version;
- confidence or completeness.

## Causality
Use:
- “occurred after”;
- “was associated with”;
- “was followed by”;
- “review whether”.

Avoid:
- “caused”;
- “threw the game”;
- “ignored the call”;
- “made a bad decision” without replay or human review.

## Unknowns
Return `unknown`, `insufficient_data`, or `needs_replay_review` when:
- key timeline frames are missing;
- positions are unavailable;
- event grouping is ambiguous;
- intent or communication is required;
- confidence is below the active rule threshold.

## Episode principles
- Group related kills, deaths, fights, and objectives.
- One objective loss must not be assigned independently to every death in one fight.
- Separate pre-event state, immediate exchange, and later follow-up.
- Use explicit follow-up windows such as 30/60/90 seconds.
- Use an explicit objective-analyzable denominator, not all deaths.

## Profile language
A per-match score is performance in that match, not permanent skill.

Long-term claims must expose:
- role and comparison cohort;
- sample size;
- recency range;
- confidence/uncertainty;
- supporting matches.

## Match selection language
- Representative: closest to the long-term feature profile.
- Best-performance: strongest context-adjusted positive performance.
- Profile-deviation: furthest from the profile, not necessarily worst.
