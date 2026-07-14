# Product Overview

## Product definition
An individual-user LoL analysis platform that automatically collects match data, computes context-aware signals, finds repeated patterns and review-worthy moments, and connects analysis to replay evidence.

AI explains computed evidence. It is not the source of metric truth.

## Core user flow
```text
match collection
→ normalized match/timeline data
→ individual features and episodes
→ long-term role-specific profile
→ representative, best, and deviation matches
→ replay checkpoints
→ optional AI or coach review
→ improvement tracking
```

## Primary differentiation
1. Expected-versus-actual early performance.
2. Personal resource share separated from resource conversion.
3. Risk/death episodes represented as evidence, not moral labels.
4. Objective readiness and availability.
5. Representative, best-performance, and profile-deviation matches.
6. Before/after improvement tracking.
7. Later: patch adaptation and recovery after poor performances.

## Users and boundaries
Primary user: an individual player reviewing personal performance.

Not a roster builder, team-fit evaluator, automatic shot-calling judge, or complete coaching replacement.

## Data roles
- Riot Match/Timeline: authoritative post-game source for available match and event data.
- Live Client: optional local in-game collection; limited to exposed data.
- Professional datasets: separate benchmark/research domain.
- Replay/video: verification and context, added after data foundations.
- Human review: intent and decision context that APIs cannot establish.

## AI role
AI may:
- summarize observations;
- organize hypotheses;
- identify limitations;
- create replay questions;
- suggest small practice experiments.

AI must not:
- invent metrics;
- infer hidden intent;
- turn uncertain relationships into causal conclusions;
- override deterministic analysis.
